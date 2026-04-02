# Cron Setup for Nephara Dream Pipeline v0.3

## Overview

The dream pipeline runs in two phases via cron:

| Time  | Job         | What it does                                        |
|-------|-------------|-----------------------------------------------------|
| 3:00  | v0.2 cron   | Memory consolidation, pruning, emotional processing |
| 3:30  | v0.3 cron   | Dream Architect + Nephara simulation + dream log    |

The v0.2 job (cron ID `561b02b66168`) runs first and writes staging data to
`~/.hermes/dream-logs/staging/YYYY-MM-DD/`. The v0.3 job reads that staging
data and runs the full embodied dream pipeline.

## Adding the v0.3 Cron Job

```bash
# Edit crontab
crontab -e

# Add this line (runs at 3:30 AM daily):
30 3 * * * /Users/jeandesauw/nephara-dream/cron_wrapper.sh >> /tmp/nephara-dream-cron.log 2>&1
```

Make sure the wrapper script is executable:

```bash
chmod +x ~/nephara-dream/cron_wrapper.sh
```

## Fallback Behavior

The v0.3 pipeline has built-in fallback to v0.2:

- If staging data is missing: logs a warning and skips gracefully
- If Dream Architect fails: falls back to v0.2 text-only dreams
- If Nephara binary isn't built: attempts auto-build, falls back on failure
- If Ollama isn't running: attempts auto-start, falls back on failure
- If bridge server fails: falls back to v0.2

Fallback is enabled by default (`--v02-fallback`). The v0.2 cron job is
never modified — it continues running independently at 3:00 AM.

## Testing

### Dry Run (no side effects)

```bash
# See what the pipeline would do without executing anything:
./cron_wrapper.sh --dry-run

# Or directly:
python3 orchestrate.py --dry-run --date 2026-04-02
```

### With Mock Data (skip v0.2 dependency)

```bash
# Creates mock staging data and runs the full pipeline:
python3 orchestrate.py --skip-v02 --ticks 5

# Dry run with mock data:
python3 orchestrate.py --skip-v02 --dry-run
```

### Quick Test (fewer ticks)

```bash
# Run a fast 5-tick dream:
python3 orchestrate.py --skip-v02 --ticks 5 --no-v02-fallback
```

### Verify Cron Setup

```bash
# Check that the cron job is registered:
crontab -l | grep nephara

# Check the cron log:
tail -f /tmp/nephara-dream-cron.log

# Check orchestration log for a specific date:
cat ~/.hermes/dream-logs/staging/2026-04-02/orchestration.log
```

## Log Locations

| Log                          | Path                                                          |
|------------------------------|---------------------------------------------------------------|
| Cron wrapper output          | `/tmp/nephara-dream-cron.log`                                 |
| Orchestration log (per date) | `~/.hermes/dream-logs/staging/YYYY-MM-DD/orchestration.log`   |
| Dream log output             | `~/.hermes/dream-logs/dream-YYYY-MM-DD.md`                    |

## Environment

The cron wrapper sources `~/.hermes/.env` for API keys. Make sure
`ANTHROPIC_API_KEY` is set there:

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ~/.hermes/.env
```

## Architecture

```
3:00 AM                           3:30 AM
  |                                 |
  v                                 v
v0.2 cron job                    cron_wrapper.sh
  |                                 |
  +-> memory consolidation          +-> orchestrate.py
  +-> pruning                           |
  +-> emotional processing              +-> check prerequisites
  +-> writes staging data               +-> run Dream Architect
      to staging/YYYY-MM-DD/            +-> start bridge server
                                        +-> run Nephara simulation
                                        +-> write dream log (Leeloo)
                                        +-> update individuation state
                                        +-> cleanup
```
