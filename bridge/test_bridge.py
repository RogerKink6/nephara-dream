#!/usr/bin/env python3
"""
Tests for the Hermes Bridge.

Run with:
    python3 -m pytest bridge/test_bridge.py -v
"""

import json
import pytest
from unittest.mock import patch, MagicMock

# Import bridge components
from hermes_bridge import (
    app,
    build_system_prompt,
    DreamSession,
    extract_action_json,
    DREAM_SYSTEM_PROMPT,
    sessions,
)


# ---------------------------------------------------------------------------
# Unit tests: System prompt
# ---------------------------------------------------------------------------

class TestSystemPrompt:
    def test_system_prompt_mentions_leeloo(self):
        prompt = build_system_prompt("Leeloo")
        assert "Leeloo" in prompt

    def test_system_prompt_mentions_dreaming(self):
        prompt = build_system_prompt("Leeloo")
        assert "You are here, in this place, right now" in prompt

    def test_system_prompt_mentions_json_format(self):
        prompt = build_system_prompt("Leeloo")
        assert '"action"' in prompt
        assert '"target"' in prompt
        assert '"reason"' in prompt

    def test_system_prompt_mentions_jean(self):
        prompt = build_system_prompt("Leeloo")
        assert "Jean" in prompt

    def test_system_prompt_not_helping_user(self):
        prompt = build_system_prompt("Leeloo")
        assert "NOT helping a user" in prompt


# ---------------------------------------------------------------------------
# Unit tests: Dream session / message history
# ---------------------------------------------------------------------------

class TestDreamSession:
    def test_session_creation(self):
        session = DreamSession("Leeloo")
        assert session.agent_name == "Leeloo"
        assert session.tick_count == 0
        assert session.history == []

    def test_add_perception_increments_tick(self):
        session = DreamSession("Leeloo")
        session.add_perception("You see a forest.")
        assert session.tick_count == 1
        session.add_perception("The forest glows.")
        assert session.tick_count == 2

    def test_add_perception_returns_messages(self):
        session = DreamSession("Leeloo")
        messages = session.add_perception("You see a forest.")
        # Should have: system + 1 user message
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "[TICK 1]" in messages[1]["content"]
        assert "You see a forest." in messages[1]["content"]

    def test_history_accumulates(self):
        session = DreamSession("Leeloo")

        # Tick 1
        messages = session.add_perception("You see a forest.")
        session.add_response('{"action": "explore", "target": "forest", "reason": "curious"}')

        # Tick 2
        messages = session.add_perception("The forest glows.")
        # Should have: system + user1 + assistant1 + user2
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"
        assert messages[3]["role"] == "user"
        assert "[TICK 1]" in messages[1]["content"]
        assert "[TICK 2]" in messages[3]["content"]

    def test_session_stats(self):
        session = DreamSession("Leeloo")
        session.add_perception("test")
        session.add_response("response")
        stats = session.stats()
        assert stats["agent_name"] == "Leeloo"
        assert stats["tick_count"] == 1
        assert stats["history_length"] == 2
        assert "uptime_seconds" in stats


# ---------------------------------------------------------------------------
# Unit tests: Action JSON extraction
# ---------------------------------------------------------------------------

class TestExtractActionJson:
    def test_clean_json(self):
        text = '{"action": "explore", "target": "forest", "reason": "curious"}'
        result = extract_action_json(text)
        obj = json.loads(result)
        assert obj["action"] == "explore"

    def test_json_with_markdown(self):
        text = 'Here is my action:\n```json\n{"action": "wait", "target": "none", "reason": "thinking"}\n```'
        result = extract_action_json(text)
        obj = json.loads(result)
        assert obj["action"] == "wait"

    def test_json_with_surrounding_text(self):
        text = 'I feel drawn to the light. {"action": "move", "target": "light", "reason": "drawn"} That is my choice.'
        result = extract_action_json(text)
        obj = json.loads(result)
        assert obj["action"] == "move"

    def test_no_json_returns_raw(self):
        text = "I don't know what to do"
        result = extract_action_json(text)
        assert result == text

    def test_json_without_action_returns_raw(self):
        text = '{"name": "Leeloo"}'
        result = extract_action_json(text)
        # No "action" key, should return raw
        assert result == text


# ---------------------------------------------------------------------------
# Integration tests: Flask endpoints
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def setup_method(self):
        self.client = app.test_client()
        sessions.clear()

    def test_health_returns_ok(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "model" in data
        assert "port" in data

    def test_health_shows_sessions(self):
        sessions["Leeloo"] = DreamSession("Leeloo")
        resp = self.client.get("/health")
        data = resp.get_json()
        assert "Leeloo" in data["sessions"]


class TestActionEndpoint:
    def setup_method(self):
        self.client = app.test_client()
        sessions.clear()

    def test_missing_body_returns_400(self):
        resp = self.client.post("/action", data="not json")
        # Flask will parse it as None, returns 400
        assert resp.status_code == 400

    def test_missing_prompt_returns_400(self):
        resp = self.client.post("/action",
                                json={"agent_name": "Leeloo"})
        assert resp.status_code == 400

    @patch("hermes_bridge.call_llm")
    def test_action_success(self, mock_llm):
        mock_llm.return_value = '{"action": "explore", "target": "forest", "reason": "curious"}'
        resp = self.client.post("/action",
                                json={"prompt": "You see a forest.", "agent_name": "Leeloo"})
        assert resp.status_code == 200
        data = json.loads(resp.data.decode())
        assert data["action"] == "explore"

    @patch("hermes_bridge.call_llm")
    def test_action_creates_session(self, mock_llm):
        mock_llm.return_value = '{"action": "wait", "target": "none", "reason": "observing"}'
        self.client.post("/action",
                         json={"prompt": "You see a forest.", "agent_name": "Leeloo"})
        assert "Leeloo" in sessions
        assert sessions["Leeloo"].tick_count == 1

    @patch("hermes_bridge.call_llm")
    def test_action_accumulates_history(self, mock_llm):
        mock_llm.return_value = '{"action": "wait", "target": "none", "reason": "observing"}'

        # Two ticks
        self.client.post("/action",
                         json={"prompt": "Tick 1", "agent_name": "Leeloo"})
        self.client.post("/action",
                         json={"prompt": "Tick 2", "agent_name": "Leeloo"})

        assert sessions["Leeloo"].tick_count == 2
        assert len(sessions["Leeloo"].history) == 4  # user1, asst1, user2, asst2

    @patch("hermes_bridge.call_llm")
    def test_action_llm_failure_returns_fallback(self, mock_llm):
        mock_llm.side_effect = Exception("API error")
        resp = self.client.post("/action",
                                json={"prompt": "You see a forest.", "agent_name": "Leeloo"})
        assert resp.status_code == 200
        data = json.loads(resp.data.decode())
        assert data["action"] == "wait"
        assert "error" in data["reason"] or "flickered" in data["reason"]

    @patch("hermes_bridge.call_llm")
    def test_llm_receives_dream_context(self, mock_llm):
        mock_llm.return_value = '{"action": "explore", "target": "door", "reason": "curious"}'

        self.client.post("/action",
                         json={"prompt": "A glowing door appears.", "agent_name": "Leeloo"})

        # Check what messages were passed to LLM
        call_args = mock_llm.call_args[0][0]
        assert call_args[0]["role"] == "system"
        assert "You are here, in this place, right now" in call_args[0]["content"]
        assert call_args[1]["role"] == "user"
        assert "[TICK 1]" in call_args[1]["content"]
        assert "A glowing door appears." in call_args[1]["content"]


class TestResetEndpoint:
    def setup_method(self):
        self.client = app.test_client()
        sessions.clear()

    def test_reset_clears_sessions(self):
        sessions["Leeloo"] = DreamSession("Leeloo")
        resp = self.client.post("/reset")
        assert resp.status_code == 200
        assert len(sessions) == 0


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
