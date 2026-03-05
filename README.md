# Nephara

A text-based world simulation where AI agents (small local LLMs via Ollama) inhabit a shared village, perceive their surroundings, and take actions driven by needs, personality, and a Kabbalistic freeform magic system.

Three founding entities — Elara, Rowan, and Thane — live out their days in a tick-based loop. Each tick an agent perceives the world, decides on an action, and the world resolves it with d20 rolls and narrative. Spells always succeed, but words carry all their meanings.

## Requirements

- [Nix](https://nixos.org/) with flakes enabled
- For live runs: [Ollama](https://ollama.com/) (included in the dev shell)

## Quick Start

Enter the dev shell:

```sh
nix develop
```

### Mock run (no LLM required)

Fully deterministic, no Ollama needed:

```sh
cargo run -- --llm mock
```

With a fixed seed for reproducible output:

```sh
cargo run -- --llm mock --seed 42
```

Short test run:

```sh
cargo run -- --llm mock --ticks 48 --seed 42
```

### Live run (Ollama + local LLM)

In a separate terminal, start Ollama and pull the model:

```sh
ollama serve
ollama pull gemma3:4b
```

Then run:

```sh
cargo run
```

Override the model or Ollama URL:

```sh
cargo run -- --model gemma3:12b
cargo run -- --llm-url http://other-host:11434
```

## CLI Reference

```
nephara [OPTIONS]

Options:
  --ticks <N>       Ticks to simulate (default: 144, i.e. 3 in-game days)
  --llm <BACKEND>   LLM backend: ollama (default) or mock
  --llm-url <URL>   Override Ollama URL (default: http://localhost:11434)
  --model <MODEL>   Override model name (default: gemma3:4b)
  --config <PATH>   Config file (default: config/world.toml)
  --souls <DIR>     Soul seeds directory (default: souls/)
  --seed <N>        Deterministic seed (random if omitted, logged at startup)
  --verbose         Enable debug logging
```

## Output

Each run creates a directory under `runs/` containing:

- `tick_log.txt` — the full scrolling narrative (same as stdout)
- `state_dump_tick_NNNN.json` — world snapshots every N ticks (configurable)

Agent journals are appended to `souls/*.journal.md` after each run.

## Configuration

All tunable parameters live in `config/world.toml` — need decay rates, action DCs, restoration amounts, tick counts, LLM settings. No recompilation needed to tweak values.

## Development Commands

```sh
# Build
cargo build

# Run tests
cargo test

# Check for warnings/errors without producing a binary
cargo check

# Format code
cargo fmt

# Lint
cargo clippy

# Verbose logging (debug level)
cargo run -- --llm mock --verbose
```

### Log Categories

`RUST_LOG` filters against named targets. The following categories are available:

| Target | What it covers |
|--------|----------------|
| `llm` | Ollama health check, every request (model, tokens, prompt chars), every raw response |
| `action` | Raw LLM response per agent, parsed action, d20 roll details, outcome tier |
| `magic` | Interpreter prompt built, raw Interpreter response, parsed InterpretedIntent |
| `narrate` | GM Narrator prompt sent, raw narrative response |

Examples:

```sh
# General info + all LLM traffic
RUST_LOG=info,llm=debug cargo run -- --llm mock --ticks 6 --seed 42

# Only d20 rolls and action parsing
RUST_LOG=off,action=debug cargo run -- --llm mock --ticks 6 --seed 42

# Full firehose
RUST_LOG=debug cargo run -- --llm mock --ticks 6 --seed 42

# Live run: confirm Ollama is ready, then watch LLM round-trips
RUST_LOG=info,llm=debug cargo run -- --ticks 6
```

## Project Structure

```
src/
  main.rs     CLI, initialization, run loop
  world.rs    World struct, locations, tick cycle, GM Narrator
  agent.rs    Agent struct, needs, attributes, memory buffer
  action.rs   Action enum, d20 resolution, outcome tiers
  magic.rs    Cast Intent flow, Interpreter prompt, response parsing
  llm.rs      LlmBackend trait, OllamaBackend, MockBackend
  config.rs   TOML deserialization into typed config struct
  soul.rs     Soul seed parser (YAML frontmatter + markdown body)
  log.rs      Tick log formatting, journal writing, state dumps

souls/        Entity definitions (*.seed.md) and chronicles (*.journal.md)
config/       world.toml — all tunable world parameters
spec/         Full design specification
rituals/      The summoning prompt used to create the founding entities
runs/         Simulation output (gitignored)
```

## Determinism

Given the same `--seed`, `--ticks`, and `--llm mock`, the output is byte-for-byte identical. Useful for regression testing:

```sh
cargo run -- --llm mock --ticks 144 --seed 42 > out1.txt
cargo run -- --llm mock --ticks 144 --seed 42 > out2.txt
diff out1.txt out2.txt   # empty — identical
```

Live Ollama runs are deterministic on the same model version and hardware (seed is passed to Ollama's generate options with `temperature: 0`).
