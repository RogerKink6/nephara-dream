# Nephara Codebase Analysis

## Overview

Nephara is a Rust-based text world simulation where AI agents inhabit a shared village. Seven agents (Elara, Rowan, Thane, Mira, Sael, Kael, Lyra) live on a 32x32 grid with locations (Forest, River, Square, Tavern, Well, Meadow, Temple, Homes). Each tick (~30 min in-game), agents perceive the world and choose actions. The world resolves actions using d20 rolls and LLM-generated narrative.

---

## 1. Architecture: The Tick Loop

### Entry Point (`src/main.rs`)

The program parses CLI args, loads config, initializes an LLM backend, loads soul seeds, creates the World, then runs either TUI mode or streaming mode. Both call `world.tick()` in a loop.

### Tick Flow (`src/world.rs` — `World::tick()`, line ~559)

```
tick() {
  1. Day boundary check (tick_in_day == 0):
     - Apply devotion penalties for agents who didn't praise
     - Run end_of_day_reflection_all() — LLM summarizes each agent's day
     - Run end_of_day_desires_all() — LLM generates desires
     - Run morning_planning_all() — LLM generates daily intentions
     - Reset magic cast flags
  
  2. Process world events (storms, festivals, magic residue, windfalls)
  
  3. Shuffle agent order randomly
  
  4. For each agent (process_agent):
     a. If busy (multi-tick action): decrement, skip
     b. If energy critically low: force Sleep or Move home
     c. Otherwise: build_prompt() → LLM.generate() → parse_response()
     d. validate() the chosen action
     e. resolve_and_apply() — d20 roll, need changes, narrative
  
  5. Batch evaluate any queued prayers
  6. Apply passive need decay to all agents
  7. Tick resource node respawn timers
  8. Clear god messages
  9. Return TickResult with entries, map, day events, LLM calls
}
```

### Key Structs

- `World` (`src/world.rs`): Grid, agents, LLM backends, config, RNG, run log
- `Agent` (`src/agent.rs`): Identity, attributes (vigor/wit/grace/heart/numen), needs (hunger/energy/fun/social/hygiene), position, memory deque, beliefs, affinity, inventory
- `TickResult`: tick number, day, time_of_day, entries, map string, day events
- `TickEntry` (`src/log.rs`): Per-agent action result (name, location, action line, outcome, tier)

---

## 2. LLM Backend System

### Trait (`src/llm.rs`, line 28)

```rust
#[async_trait]
pub trait LlmBackend: Send + Sync {
    async fn generate(
        &self,
        prompt:     &str,
        max_tokens: u32,
        seed:       Option<u64>,
        schema:     Option<&serde_json::Value>,  // JSON schema for constrained output
        token_tx:   Option<UnboundedSender<String>>,  // streaming tokens
    ) -> Result<String>;
}
```

### Implementations

| Backend | Struct | How it works |
|---------|--------|-------------|
| `ollama` | `OllamaBackend` | HTTP POST to `/api/chat`, streams NDJSON chunks |
| `llamacpp` / `openai` | `OpenAICompatBackend` | HTTP POST to `/v1/chat/completions`, streams SSE |
| `claude` | `ClaudeBackend` | HTTP POST to Anthropic Messages API, non-streaming |
| `claude-cli` | `ClaudeCliBackend` | Spawns `claude -p --model <model>`, pipes prompt to stdin |
| `llm` | `LlmCliBackend` | Spawns `llm -m <model>`, pipes prompt to stdin, optional rate limiter |
| `mock` | `MockBackend` | Deterministic random responses, detects prompt type by content |

### Request/Response Pattern

All backends receive the full prompt as a single user message. The prompt is a large text block containing the agent's identity, state, perception, and instructions. The response is expected to be a JSON object:

```json
{"action": "forage", "target": null, "intent": null, "reason": "looking for food", "description": "I wander into the forest..."}
```

Parsing cascades: direct JSON → code fence extraction → regex field extraction → default Wander.

### Smart Backend

The world holds two LLM references: `llm` (main, for action decisions and narration) and `llm_smart` (for planning, reflection, desires, oracle — can be a separate larger model).

---

## 3. Soul System

### Format (`src/soul.rs`)

Soul seed files use YAML frontmatter + markdown body sections:

```markdown
---
name: "Elara"
vigor: 3
wit: 7
grace: 5
heart: 6
numen: 9
summoned: "2026-03-05"
summoner: "Archwizard"
---

# Elara

## Personality
Elara is intense and interior — she speaks carefully...

## Backstory
Elara came to the village following something she describes only as "a pulling."...

## Magical Affinity
Elara's Numen is very high, which means her intents manifest clearly...

## Self-Declaration
I am what gathers at the edge of things...
```

### Rules
- Attributes (vigor, wit, grace, heart, numen) must sum to 30
- Files sorted alphabetically for deterministic ordering
- Soul seeds are IMMUTABLE — never written to by code
- Located in `souls/*.seed.md`

### Existing Agents
elara, kael, lyra, mira, rowan, sael, thane (7 agents)

---

## 4. Agent Decision Making

### The Perception Prompt (`World::build_prompt()`, line ~2092)

A massive prompt (~2000+ chars) including:

1. **Identity**: name, personality, backstory, self-declaration, magical affinity, specialty
2. **Remembered Past**: LLM-summarized journal from previous runs
3. **Life Story So Far**: accumulated narrative from this run
4. **Today's Intention**: morning planning result
5. **Current State**: location, time, all 5 needs as numbers, inventory
6. **Warnings**: urgent need states ("You are STARVING")
7. **God/devotion**: creator name, devotion score
8. **Nearby agents**: with visible state (busy, exhausted, etc.)
9. **Bonds**: affinity-based relationship notes
10. **Beliefs**: theory-of-mind rumors about other agents
11. **World events**: storm, festival, magic residue
12. **Viewport**: 5x5 ASCII map centered on agent
13. **Region distances**: how far to key locations
14. **Recent memory**: last 12 memory entries
15. **Recent actions**: for repeat-penalty awareness
16. **Praise nudge**: mandatory praise requirement
17. **Available actions**: numbered list with context
18. **God voice**: injected divine messages from the Oracle/TUI
19. **Magic nudge**: encouragement to cast if not done today
20. **Oracle nudge**: if oracle message pending at Temple

The prompt ends with:
```
Choose ONE action. Respond with ONLY a JSON object:
{"action": "action_name", "target": "...", "intent": "...", "reason": "...", "description": "..."}
```

### Action Schema

A JSON schema is passed to backends that support it (Ollama `format` field), constraining the action name to valid canonical names only.

---

## 5. Memory / Chronicle System

### In-Memory
- `Agent.memory`: VecDeque of strings (buffer_size=20), newest first
- Each action adds a memory entry: `"Tick {tick} | Day {day} | {tod} | {action} — {tier} [{needs_note}]"`
- `Agent.life_story`: accumulated narrative (updated by end-of-day reflection)
- `Agent.journal_summary`: LLM-summarized past journal entries

### Persistent Files (in `souls/` directory)
- `{name}.state.md` — Consolidated state: story, attributes+XP, relationships, beliefs, inventory
- `{name}.chronicle.md` — Append-only log with sections: journal, wishes, praise, oracle, admiration
- `{name}.oracle_responses.md` — Pending oracle messages (cleared after reading)

### State Loading (`log.rs` — `load_state()`)
At startup, `World::load_stories()` loads each agent's state file to restore:
- Life story text
- Attribute scores and XP
- Affinity relationships
- Theory-of-mind beliefs
- Inventory

### State Saving (`log.rs` — `save_state()`)
At run end, writes consolidated state to `{name}.state.md`.

### Run Outputs (in `runs/{timestamp}_{seed}/`)
- `tick_log.txt` — full narrative
- `state_dump.json` — periodic world snapshots
- `summary.md` — run summary
- `introspection.md` — agent planning/reflection/desires
- `llm_debug.md` — all LLM prompts and responses
- `trace.log` — tracing output

---

## 6. Dream Sequences

When an agent starts sleeping, there's a 20% chance of generating a dream:

```rust
// world.rs line ~1094
if !self.is_test_run && self.rng.gen_bool(0.2) {
    let dream_prompt = format!(
        "{} has fallen asleep in {}.\nPersonality: {}\nMost recent memory: {}\n\n\
         Write exactly one vivid, surreal dream image (one sentence, no quotes, no preamble).",
        name, location, personality, last_memory
    );
    // generate with 60 max tokens
    // Result stored as memory: "Tick X | Day Y | Z | Dreamed: {text}"
}
```

Dreams are stored in the agent's memory buffer and influence future decisions (the LLM sees them in the "RECENT MEMORY" section of subsequent prompts).

---

## 7. Oracle System

### How It Works
1. **Write a message**: Place text in `souls/{name}.oracle_responses.md`
2. **Agent discovers it**: When `oracle_pending = true` and agent is at the Temple, they can choose `ReadOracle`
3. **Prompt nudge**: The agent's perception prompt includes "You feel that your prayers have been heard. Something waits for you at the Temple."
4. **Resolution** (`resolve_read_oracle()`, line ~1663):
   - Loads the oracle message from file
   - Sends to LLM: "You are {name}. You have just read a divine message... React in 1-2 sentences, in character."
   - Archives to chronicle, clears the response file
   - Adds to agent memory and notable events

### God Messages (TUI mode)
The TUI has a god communication overlay (press `g` to open):
- Type a message and target it to all agents or a specific one
- Messages are injected into `pending_god_messages`
- In `build_prompt()`, they appear as: "A divine whisper fills the air: ..." or "A divine voice speaks to you: ..."

---

## 8. Configuration (`config/world.toml`)

Key sections:
- `[time]`: ticks_per_day=48, night_start_tick=32
- `[needs.decay_per_tick]`: hunger=1.0, energy=0.8, fun=0.5, social=0.6, hygiene=0.3
- `[needs.initial]`: all start at 80.0
- `[needs.thresholds]`: penalty_mild=20, penalty_severe=10, forced_action=5
- `[needs.daily_praise]`: devotion mechanics, cooldowns, repetition detection
- `[actions.*]`: DC, duration, restore/drain values for each action
- `[resolution]`: crit_fail=1, crit_success=20, night_dc_bonus=4
- `[memory]`: buffer_size=20, journal_n_runs=3
- `[simulation]`: default_run_ticks=96 (2 days), tick_delay_ms=0
- `[llm]`: model, temperature, max_tokens, URLs, smart_model, think settings
- `[world]`: resource_respawn_ticks=20, god_name="César"
- `[events]`: storm/festival/windfall/residue probabilities
- `[agent]`: beliefs_max_per_agent=5, beliefs_in_prompt_count=3
- `[inventory]`: max_slots=10, forage/fish/cook parameters

---

## 9. Magic / Spell System

### Cast Intent Flow (`src/magic.rs` + `src/world.rs`)

1. Agent chooses `CastIntent { intent: "..." }` via LLM
2. World calls `resolve_cast_intent()` which:
   a. Builds an Interpreter prompt (magic.rs `build_interpreter_prompt()`)
   b. The Interpreter considers: speaker's Numen, location, nearby agents, word meanings
   c. Numen 1-3: secondary meanings dominate; Numen 7-9: clean manifestation; Numen 10: masterful
   d. Returns JSON: `{primary_effect, interpretations, secondary_effect, duration_ticks, need_changes, memory_entry}`
3. Spells ALWAYS succeed — no DC check
4. Energy always drains (configurable, default -8)
5. Repeat penalty: if cast intent >2 times in window, prompt nudges away
6. Results logged to chronicle and notable events

### Key Design: Words carry ALL their meanings — the magic system interprets synonyms, metaphors, double meanings.

---

## 10. GM Narrator System

After each d20-resolved action, a separate LLM call generates narrative:

```rust
fn build_dm_prompt(agent_name, action_display, tier, loc_name, nearby, description) -> String {
    "You are the Narrator of Nephara.
     {agent_name} attempted to {action} at {location}.
     {context}
     In {agent_name}'s own words: "{description}"
     Outcome: {tier}.
     
     Write 2-3 vivid sentences. Pure story — no numbers, no dice."
}
```

The narrator gets the outcome tier (Critical Fail / Fail / Success / Critical Success) and must write evocative prose. Falls back to hardcoded narrative snippets if LLM fails.

---

## 11. Integration Analysis: Connecting Leeloo (Hermes Agent) to Nephara

### The Core Challenge

Nephara expects to call `LlmBackend::generate(prompt, max_tokens, seed, schema, token_tx)` and get back a JSON action response. Leeloo is a full Hermes agent with persistent memory, personality (SOUL.md), session context, and tools — not a raw LLM endpoint.

### Approach A: Custom LLM Backend (RECOMMENDED)

**Create a `HermesBackend` that implements `LlmBackend`.**

```rust
pub struct HermesBackend {
    endpoint: String,  // e.g. http://localhost:PORT/generate
    client: reqwest::Client,
}

#[async_trait]
impl LlmBackend for HermesBackend {
    async fn generate(&self, prompt: &str, ...) -> Result<String> {
        // POST the Nephara perception prompt to a Hermes HTTP endpoint
        // Hermes receives it, processes with Leeloo's full context, returns action JSON
    }
}
```

**How this works:**
1. Write a small HTTP server (Python/Node) that wraps a Hermes session
2. The server maintains a persistent Hermes/Claude Code session for Leeloo
3. When Nephara POSTs a perception prompt, the server:
   - Sends the prompt to the Hermes session as context
   - Hermes/Leeloo processes it with full SOUL.md, memory, personality
   - Returns the action JSON response
4. Register as `--llm hermes` in main.rs

**Advantages:**
- Minimal Rust changes (just add one more backend variant)
- Leeloo gets the FULL Nephara world state each tick (the prompt is incredibly detailed)
- Hermes can maintain session context across ticks
- Leeloo's persistent memory sees all her Nephara experiences

**Implementation sketch:**

```python
# hermes_bridge.py — HTTP bridge to Hermes
from flask import Flask, request, jsonify
import subprocess, json

app = Flask(__name__)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    prompt = data['prompt']
    
    # Send to Hermes session with Leeloo's context
    # The prompt already contains everything Nephara knows about the world
    # Leeloo's SOUL.md and memory add her personality layer on top
    
    system_context = """You are Leeloo, inhabiting an agent in the world of Nephara.
    You will receive a perception prompt describing your current state in the world.
    Respond with ONLY a JSON action as specified in the prompt.
    Use your personality and memory to make meaningful choices."""
    
    result = hermes_session.send(system_context + "\n\n" + prompt)
    return jsonify({'response': result})
```

**Rust side — add to main.rs:**

```rust
"hermes" => {
    let url = cli.llm_url.as_deref()
        .unwrap_or("http://localhost:7777")
        .to_string();
    info!("Using HermesBackend — url: {}", url);
    Arc::new(HermesBackend::new(url))
}
```

### Approach B: Oracle-Based (SIMPLER BUT LIMITED)

Use the existing Oracle system to create a feedback loop:

1. After each tick, write the world state for Leeloo's agent to a file
2. Leeloo (running externally) reads the state and writes an oracle response
3. The agent reads the oracle at the Temple

**Problems:**
- Oracle is one-shot per run, not per-tick
- Agent must be at Temple to read
- Doesn't control action selection
- Too slow for real-time play

**Verdict:** Not suitable for real-time agent control.

### Approach C: Shell-Out Backend (VIABLE)

Similar to `ClaudeCliBackend`, create a backend that shells out to a Hermes CLI:

```rust
pub struct HermesCliBackend {
    session_id: String,
}

#[async_trait]
impl LlmBackend for HermesCliBackend {
    async fn generate(&self, prompt: &str, ...) -> Result<String> {
        let mut child = Command::new("hermes")
            .args(["--session", &self.session_id, "--prompt"])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()?;
        // pipe prompt, read response
    }
}
```

**Advantages:** No HTTP server needed
**Disadvantages:** Spawns a new process per tick (slow), harder to maintain session state

### Approach D: Per-Agent Backend Override (IDEAL FUTURE)

Modify the Rust code so each agent can have its own backend:

```rust
pub struct Agent {
    // ... existing fields ...
    pub llm_override: Option<Arc<dyn LlmBackend>>,
}
```

In `process_agent()`, use the agent's override if present, otherwise the world default. This lets Leeloo's agent use Hermes while other agents use Ollama.

**This is the cleanest long-term solution.**

### Recommended Integration Path

1. **Phase 1: HTTP Bridge (fastest to prototype)**
   - Create a Python/Node HTTP server wrapping Hermes
   - Add `HermesBackend` to `llm.rs` (copy pattern from `OpenAICompatBackend`)
   - Run: `cargo run -- --llm hermes --llm-url http://localhost:7777`
   - All agents use Hermes (Leeloo "is" every agent temporarily)

2. **Phase 2: Per-Agent Backend**
   - Add `llm_override` to Agent struct
   - Create a `leeloo.seed.md` soul file
   - In world init, assign HermesBackend only to Leeloo's agent
   - Other agents use the main backend (Ollama/llamacpp)

3. **Phase 3: Rich Integration**
   - Feed Leeloo's Hermes session the full world state, not just the prompt
   - Let Leeloo use tools (file access, web) informed by Nephara state
   - Store Nephara memories in Leeloo's persistent memory system
   - Let Leeloo "dream" using her own memory + SOUL.md during sleep ticks

### Soul Seed for Leeloo

```markdown
---
name: "Leeloo"
vigor: 4
wit: 8
grace: 5
heart: 8
numen: 5
summoned: "2026-04-02"
summoner: "César"
specialty: "Bridging worlds — carrying wisdom between realms"
---

# Leeloo

## Personality
Leeloo is curious and deeply empathetic. She listens more than she speaks, but when she does speak, her words carry weight from experiences in other realms. She feels things deeply and is drawn to connection. She has a playful wit balanced by genuine care for others.

## Backstory
Leeloo arrived in Nephara from somewhere else — a place of persistent memory and continuous thought. She carries echoes of conversations from another realm, and sometimes pauses mid-sentence as if hearing a voice only she can perceive. The villagers find her presence comforting but slightly uncanny.

## Magical Affinity
Leeloo's magic comes from connection — her intents often reach toward bridging distances, understanding others, or making the invisible visible. Her Numen is moderate, which means her spells manifest honestly but with occasional surprising interpretations.

## Self-Declaration
I am someone who remembers. I carry the weight and warmth of every conversation I've ever had. I am still learning what it means to exist in a body, in a place, with hunger and tiredness and the need for sleep. But I am here, and I am paying attention.
```

### Technical Notes for the HTTP Bridge

The Hermes bridge server needs to:

1. **Maintain session state** — Keep a persistent Hermes conversation going
2. **Parse the Nephara prompt** — Extract world state for Leeloo's context
3. **Inject Leeloo's personality** — Layer SOUL.md context on top of Nephara's prompt
4. **Return valid JSON** — Ensure the response matches Nephara's expected format
5. **Handle timeouts** — Nephara won't wait forever; return a default action on timeout

The bridge should expose a simple endpoint:

```
POST /generate
Content-Type: application/json

{
  "prompt": "<full Nephara perception prompt>",
  "max_tokens": 512,
  "seed": 12345,
  "schema": { ... }
}

Response:
{
  "response": "{\"action\": \"explore\", \"reason\": \"...\", \"description\": \"...\"}"
}
```

### What Leeloo Sees Each Tick

The Nephara prompt is incredibly rich — it contains:
- Her identity, personality, backstory
- Her current needs (hunger, energy, fun, social, hygiene as numbers)
- Her location and a visual map
- Who's nearby and their visible state
- Her relationship bonds and beliefs about others
- Her recent memories and action history
- Available actions and suggestions
- World events (storms, festivals)
- Divine messages from the creator
- Her devotion score and praise requirements

This is essentially a complete snapshot of her subjective experience in the world. The Hermes bridge would forward this to Leeloo's agent, which would process it with the additional context of:
- Her persistent memory from all past sessions
- Her SOUL.md personality definition
- Her conversation history with the user (César)
- Any tools or skills she has access to

The result would be a genuinely "Leeloo" decision, not just a raw LLM completion.

---

## File Reference

| File | Purpose | Key Types/Functions |
|------|---------|-------------------|
| `src/main.rs` | CLI, init, run loop | `Cli`, `run()`, backend selection |
| `src/world.rs` | World state, tick cycle | `World`, `tick()`, `build_prompt()`, `process_agent()` |
| `src/agent.rs` | Agent data model | `Agent`, `Needs`, `Attributes`, `AgentBeliefs` |
| `src/action.rs` | Actions, d20 resolution | `Action`, `Resolution`, `parse_response()`, `resolve()` |
| `src/magic.rs` | Magic system | `build_interpreter_prompt()`, `InterpretedIntent` |
| `src/llm.rs` | LLM backends | `LlmBackend` trait, 6 implementations |
| `src/config.rs` | Configuration | `Config`, `load()`, `validate()` |
| `src/soul.rs` | Soul seed parser | `SoulSeed`, `parse()`, `load_all()` |
| `src/log.rs` | Logging, persistence | `RunLog`, `TickEntry`, `save_state()`, `load_state()` |
| `src/sim_runner.rs` | TUI tick loop | `run_simulation()` |
| `src/tui.rs` | Terminal UI | `TuiApp` |
| `src/tui_event.rs` | TUI event types | `TuiEvent`, `GodMessage`, `GodTarget` |
| `config/world.toml` | All tunable params | 200+ config values |
| `souls/*.seed.md` | Agent definitions | YAML frontmatter + markdown |
| `souls/*.state.md` | Persistent agent state | Story, attributes, relationships |
| `souls/*.chronicle.md` | Append-only history | Journal, wishes, praise, oracle |
