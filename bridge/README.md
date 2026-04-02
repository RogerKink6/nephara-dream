# Hermes Bridge

HTTP bridge between the Nephara dream simulation (Rust) and Claude API via litellm.

## What it does

The Nephara Rust simulation calls `POST /action` with a perception prompt for a dream agent (e.g., Leeloo). This bridge:

1. Wraps the prompt in a dream-context system prompt
2. Maintains conversation history across ticks (so the agent remembers the dream)
3. Calls Claude via litellm
4. Returns the action JSON that Nephara expects

## Quick start

```bash
# Using the Hermes venv (recommended):
~/.hermes/hermes-agent/venv/bin/python3 hermes_bridge.py

# Or install deps and run directly:
pip install -r requirements.txt
python3 hermes_bridge.py
```

## Configuration

Environment variables:

| Variable | Default | Description |
|---|---|---|
| `HERMES_BRIDGE_PORT` | `7777` | Port to listen on |
| `HERMES_MODEL` | `anthropic/claude-sonnet-4-6` | litellm model string |
| `HERMES_PROVIDER` | `anthropic` | Provider name |
| `ANTHROPIC_API_KEY` | (from `~/.hermes/.env`) | API key for Claude |

## Endpoints

- `POST /action` — Main endpoint. Receives `{"prompt": "...", "agent_name": "Leeloo"}`, returns action JSON.
- `GET /health` — Health check. Returns session stats.
- `POST /reset` — Reset all dream sessions.

## Running with Nephara

```bash
# Terminal 1: Start the bridge
~/.hermes/hermes-agent/venv/bin/python3 bridge/hermes_bridge.py

# Terminal 2: Run the simulation
cargo run -- --backend hermes --hermes-url http://localhost:7777
```

## Testing

```bash
# Run tests (no API key needed):
~/.hermes/hermes-agent/venv/bin/python3 -m pytest bridge/test_bridge.py -v

# Manual test:
curl -X POST http://localhost:7777/action \
  -H "Content-Type: application/json" \
  -d '{"prompt": "You are Leeloo. You see a glowing door.", "agent_name": "Leeloo"}'

curl http://localhost:7777/health
```
