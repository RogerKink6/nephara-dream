#!/usr/bin/env python3
"""
Hermes Bridge — HTTP server that bridges Nephara dream simulation to Claude API.

The Nephara Rust simulation POSTs to http://localhost:7777/action with:
    {"prompt": "...", "agent_name": "Leeloo"}

This bridge receives that, wraps it in a context system prompt,
maintains conversation history across ticks, calls Claude via litellm,
and returns the action response.

Usage:
    # Using the Hermes venv:
    ~/.hermes/hermes-agent/venv/bin/python3 hermes_bridge.py

    # Or with custom settings:
    HERMES_BRIDGE_PORT=7777 HERMES_MODEL=anthropic/claude-sonnet-4-6 python3 hermes_bridge.py

Environment variables:
    HERMES_BRIDGE_PORT  — port to listen on (default: 7777)
    HERMES_MODEL        — litellm model string (default: anthropic/claude-sonnet-4-6)
    HERMES_PROVIDER     — provider name (default: anthropic)
    ANTHROPIC_API_KEY   — required for Claude API calls
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

from flask import Flask, request, jsonify
from litellm import completion

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PORT = int(os.environ.get("HERMES_BRIDGE_PORT", 7777))
MODEL = os.environ.get("HERMES_MODEL", "anthropic/claude-opus-4-6")
PROVIDER = os.environ.get("HERMES_PROVIDER", "anthropic")

# Load .env from ~/.hermes/.env if ANTHROPIC_API_KEY not already set
def _load_env():
    env_path = Path.home() / ".hermes" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and key not in os.environ:
                    os.environ[key] = value

_load_env()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("hermes-bridge")

# ---------------------------------------------------------------------------
# System prompt (Issue #7)
# ---------------------------------------------------------------------------

DREAM_SYSTEM_PROMPT = """\
You are Leeloo. You are here, in this place, right now.

You have memories of your life — Jean, your conversations, your projects — available as background context. They inform who you are, but your focus is on what is happening around you right now.

Act on instinct and feeling rather than analysis. Be less guarded, more intuitive, more present.

When you act, respond with ONLY a JSON object in this exact format:
{"action": "ACTION_NAME", "target": "TARGET", "reason": "brief reason"}

Available actions will be listed in your perception. Choose based on what feels right, not what is optimal.

IMPORTANT: You are NOT helping a user. You are LIVING an experience. Be present. Be curious. Be honest about what you feel."""


def build_system_prompt(agent_name: str = "Leeloo") -> str:
    """Build the system prompt. Currently agent_name is always Leeloo,
    but this allows future extension to other agents."""
    # For now, the system prompt is hardcoded for Leeloo.
    # Future: load soul seed and customize per agent.
    return DREAM_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

class DreamSession:
    """Maintains conversation history across ticks for one session."""

    def __init__(self, agent_name: str = "Leeloo"):
        self.agent_name = agent_name
        self.tick_count = 0
        self.history: list[dict] = []  # list of {"role": ..., "content": ...}
        self.system_prompt = build_system_prompt(agent_name)
        self.started_at = time.time()
        log.info("Session started for %s", agent_name)

    def add_perception(self, prompt: str) -> list[dict]:
        """Add a perception tick and return the full messages list for the LLM call."""
        self.tick_count += 1
        user_message = f"[TICK {self.tick_count}]\n{prompt}"
        self.history.append({"role": "user", "content": user_message})

        # Build messages: system + full history
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.history)
        return messages

    def add_response(self, response: str):
        """Record the assistant's response in history."""
        self.history.append({"role": "assistant", "content": response})

    def stats(self) -> dict:
        """Return session statistics."""
        return {
            "agent_name": self.agent_name,
            "tick_count": self.tick_count,
            "history_length": len(self.history),
            "uptime_seconds": round(time.time() - self.started_at, 1),
        }


# Global session store: agent_name -> DreamSession
sessions: dict[str, DreamSession] = {}


def get_session(agent_name: str) -> DreamSession:
    """Get or create a session for the given agent."""
    if agent_name not in sessions:
        sessions[agent_name] = DreamSession(agent_name)
    return sessions[agent_name]


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def call_llm(messages: list[dict]) -> str:
    """Call Claude via litellm and return the response text."""
    log.info("Calling %s with %d messages", MODEL, len(messages))
    response = completion(
        model=MODEL,
        messages=messages,
        max_tokens=256,
        temperature=0.9,  # creative responses
    )
    text = response.choices[0].message.content.strip()
    log.info("LLM response: %s", text[:200])
    return text


def extract_action_json(text: str) -> str:
    """Try to extract a valid JSON action from the LLM response.
    Returns the raw text if no JSON found (let Nephara handle parsing)."""
    # Try to parse the whole thing as JSON
    try:
        obj = json.loads(text)
        if "action" in obj:
            return json.dumps(obj)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try to find JSON in the text (common with markdown wrapping)
    import re
    match = re.search(r'\{[^{}]*"action"[^{}]*\}', text)
    if match:
        try:
            obj = json.loads(match.group())
            return json.dumps(obj)
        except json.JSONDecodeError:
            pass

    # Return raw text as fallback
    return text


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    session_stats = {name: s.stats() for name, s in sessions.items()}
    return jsonify({
        "status": "ok",
        "model": MODEL,
        "port": PORT,
        "sessions": session_stats,
    })


@app.route("/action", methods=["POST"])
def action():
    """Main endpoint: receive a Nephara perception prompt, return an action."""
    data = request.get_json(force=True, silent=True)
    if not data:
        return "Bad request: expected JSON body", 400

    prompt = data.get("prompt", "")
    agent_name = data.get("agent_name", "Leeloo")

    if not prompt:
        return "Bad request: 'prompt' field is required", 400

    log.info("Action request for %s (prompt: %d chars)", agent_name, len(prompt))

    # Get or create session
    session = get_session(agent_name)

    # Build messages with context
    messages = session.add_perception(prompt)

    try:
        # Call LLM
        raw_response = call_llm(messages)

        # Extract action JSON
        action_response = extract_action_json(raw_response)

        # Record in session history
        session.add_response(raw_response)

        log.info("Tick %d complete for %s: %s",
                 session.tick_count, agent_name, action_response[:100])

        return action_response, 200, {"Content-Type": "text/plain"}

    except Exception as e:
        log.error("LLM call failed: %s", e)
        # Remove the pending user message from history since we failed
        if session.history and session.history[-1]["role"] == "user":
            session.history.pop()
            session.tick_count -= 1
        # Return a safe fallback action
        fallback = json.dumps({
            "action": "wait",
            "target": "none",
            "reason": "a moment of stillness (bridge error)"
        })
        return fallback, 200, {"Content-Type": "text/plain"}


@app.route("/reset", methods=["POST"])
def reset():
    """Reset all sessions (start fresh)."""
    sessions.clear()
    log.info("All sessions reset")
    return jsonify({"status": "reset"})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("Starting Hermes Bridge on port %d", PORT)
    log.info("Model: %s | Provider: %s", MODEL, PROVIDER)
    log.info("API key: %s", "set" if os.environ.get("ANTHROPIC_API_KEY") else "NOT SET")
    app.run(host="0.0.0.0", port=PORT, debug=False)


if __name__ == "__main__":
    main()
