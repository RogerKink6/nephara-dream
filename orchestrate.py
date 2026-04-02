#!/usr/bin/env python3
"""
Dream Orchestration Script — v0.3 Dream Pipeline Master Controller.

Runs the entire v0.3 dream pipeline:
  1. Check prerequisites (Ollama, Nephara binary, API key)
  2. Read v0.2 staging data (from ~/.hermes/dream-logs/staging/YYYY-MM-DD/)
  3. Run Dream Architect (architect/dream_architect.py)
  4. Start Hermes bridge server (bridge/hermes_bridge.py)
  5. Wait for bridge to be healthy
  6. Run Nephara with dream config
  7. Stop bridge server
  8. Collect Nephara output
  9. Pass dream experience to Leeloo for dream log writing
  10. Update individuation state
  11. Cleanup temp files

Usage:
    python orchestrate.py [--date YYYY-MM-DD] [--dry-run] [--skip-v02] [--ticks N]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HERMES_BASE = Path.home() / ".hermes"
DREAM_LOGS_BASE = HERMES_BASE / "dream-logs"
STAGING_BASE = DREAM_LOGS_BASE / "staging"
INDIVIDUATION_PATH = DREAM_LOGS_BASE / "individuation_state.json"
HERMES_VENV_PYTHON = HERMES_BASE / "claude-code" / "venv" / "bin" / "python3"
PROJECT_DIR = Path(__file__).resolve().parent
OLLAMA_BIN = "/usr/local/bin/ollama"
OLLAMA_URL = "http://localhost:11434"
BRIDGE_URL = "http://localhost:7777"
BRIDGE_HEALTH_URL = f"{BRIDGE_URL}/health"
DEFAULT_TICKS = 36
DEFAULT_MODEL = "mistral:7b"
DREAM_CONFIG_PATH = Path("/tmp/nephara-dream/dream_world_config.json")

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

log = logging.getLogger("orchestrate")


def setup_logging(log_dir: Path, dry_run: bool = False):
    """Configure logging to both console and file."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "orchestration.log"

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(str(log_file), mode="a")
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(console_handler)
    if not dry_run:
        root.addHandler(file_handler)

    log.info("Logging to %s", log_file)


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def load_env():
    """Load .env from ~/.hermes/.env if ANTHROPIC_API_KEY not already set."""
    env_path = HERMES_BASE / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and key not in os.environ:
                    os.environ[key] = value


def get_python():
    """Get the Python interpreter path (prefer Hermes venv)."""
    if HERMES_VENV_PYTHON.exists():
        return str(HERMES_VENV_PYTHON)
    return sys.executable


# ---------------------------------------------------------------------------
# Step timing context manager
# ---------------------------------------------------------------------------

class StepTimer:
    """Context manager that logs step duration."""

    def __init__(self, step_name: str, step_num: int):
        self.step_name = step_name
        self.step_num = step_num
        self.start = 0.0

    def __enter__(self):
        self.start = time.time()
        log.info("=== Step %d: %s ===", self.step_num, self.step_name)
        return self

    def __exit__(self, *exc):
        elapsed = time.time() - self.start
        status = "FAILED" if exc[0] else "OK"
        log.info(
            "    Step %d [%s] completed in %.1fs",
            self.step_num,
            status,
            elapsed,
        )
        return False


# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

def check_ollama_running() -> bool:
    """Check if Ollama is running by hitting its API."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_ollama() -> bool:
    """Start Ollama serve in background."""
    log.info("Starting Ollama...")
    try:
        subprocess.Popen(
            [OLLAMA_BIN, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait for it to come up
        for _ in range(30):
            time.sleep(1)
            if check_ollama_running():
                log.info("Ollama is now running")
                return True
        log.error("Ollama failed to start within 30s")
        return False
    except Exception as e:
        log.error("Failed to start Ollama: %s", e)
        return False


def check_ollama_model(model: str = DEFAULT_MODEL) -> bool:
    """Check if the required model is available in Ollama."""
    try:
        import urllib.request
        import json as _json
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read())
            models = [m.get("name", "") for m in data.get("models", [])]
            # Check for exact match or name without tag
            for m in models:
                if m == model or m.startswith(model.split(":")[0]):
                    return True
        return False
    except Exception:
        return False


def pull_ollama_model(model: str = DEFAULT_MODEL) -> bool:
    """Pull an Ollama model."""
    log.info("Pulling Ollama model %s...", model)
    try:
        result = subprocess.run(
            [OLLAMA_BIN, "pull", model],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode == 0:
            log.info("Model %s pulled successfully", model)
            return True
        log.error("Failed to pull model: %s", result.stderr)
        return False
    except Exception as e:
        log.error("Failed to pull model: %s", e)
        return False


def find_nephara_binary() -> Optional[Path]:
    """Find the Nephara binary (release or debug)."""
    for variant in ["release", "debug"]:
        path = PROJECT_DIR / "target" / variant / "nephara"
        if path.exists() and path.is_file():
            return path
    return None


def build_nephara() -> Optional[Path]:
    """Build Nephara in release mode."""
    log.info("Building Nephara (cargo build --release)...")
    try:
        result = subprocess.run(
            ["cargo", "build", "--release"],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(PROJECT_DIR),
        )
        if result.returncode == 0:
            path = PROJECT_DIR / "target" / "release" / "nephara"
            if path.exists():
                log.info("Nephara built successfully at %s", path)
                return path
        log.error("Cargo build failed: %s", result.stderr[:500])
        return None
    except Exception as e:
        log.error("Failed to build Nephara: %s", e)
        return None


def check_api_key() -> bool:
    """Check if ANTHROPIC_API_KEY is set."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def check_prerequisites(dry_run: bool = False) -> dict:
    """
    Check all prerequisites. Returns dict with status of each.
    Auto-starts/builds missing components unless dry_run.
    """
    status = {}

    # Ollama
    if check_ollama_running():
        status["ollama"] = "running"
    elif dry_run:
        status["ollama"] = "not_running (would start)"
    else:
        if start_ollama():
            status["ollama"] = "started"
        else:
            status["ollama"] = "failed"

    # Ollama model
    if status.get("ollama") in ("running", "started"):
        if check_ollama_model():
            status["ollama_model"] = "available"
        elif dry_run:
            status["ollama_model"] = "missing (would pull)"
        else:
            if pull_ollama_model():
                status["ollama_model"] = "pulled"
            else:
                status["ollama_model"] = "failed"
    else:
        status["ollama_model"] = "skipped (ollama not running)"

    # Nephara binary
    binary = find_nephara_binary()
    if binary:
        status["nephara_binary"] = str(binary)
    elif dry_run:
        status["nephara_binary"] = "not_found (would build)"
    else:
        binary = build_nephara()
        if binary:
            status["nephara_binary"] = str(binary)
        else:
            status["nephara_binary"] = "failed"

    # API key
    if check_api_key():
        status["api_key"] = "set"
    else:
        status["api_key"] = "not_set"

    # Python / venv
    python = get_python()
    status["python"] = python

    log.info("Prerequisites: %s", json.dumps(status, indent=2))
    return status


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def load_staging_data(date_str: str, skip_v02: bool = False) -> Optional[Path]:
    """
    Check for v0.2 staging data.
    Returns the staging directory path or None.
    """
    if skip_v02:
        log.info("--skip-v02: using empty staging data")
        mock_dir = STAGING_BASE / date_str
        mock_dir.mkdir(parents=True, exist_ok=True)
        # Create minimal mock files if they don't exist
        for fname, content in [
            ("consolidation_report.txt", "Mock consolidation: quiet day of reflection and code."),
            ("emotional_digest.json", json.dumps({
                "dominant_emotion": "curiosity",
                "intensity": 0.6,
                "keywords": ["exploration", "learning", "wonder"],
            })),
            ("unresolved_tensions.txt", "The tension between structure and freedom in creative work."),
        ]:
            fpath = mock_dir / fname
            if not fpath.exists():
                fpath.write_text(content)
        return mock_dir

    staging_dir = STAGING_BASE / date_str
    if staging_dir.exists() and any(staging_dir.iterdir()):
        log.info("Found staging data at %s", staging_dir)
        return staging_dir
    else:
        log.warning("No staging data found at %s", staging_dir)
        return None


def run_dream_architect(date_str: str, dry_run: bool = False) -> Optional[Path]:
    """
    Run the Dream Architect to generate dream_world_config.json.
    Returns path to the config file or None on failure.
    """
    output_dir = DREAM_CONFIG_PATH.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = DREAM_CONFIG_PATH

    if dry_run:
        log.info("[DRY RUN] Would run Dream Architect for date %s", date_str)
        log.info("[DRY RUN] Output would be at %s", output_path)
        return output_path

    python = get_python()
    cmd = [
        python, "-m", "architect.dream_architect",
        "--date", date_str,
        "--output", str(output_path),
    ]
    log.info("Running Dream Architect: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(PROJECT_DIR),
            env={**os.environ, "PYTHONPATH": str(PROJECT_DIR)},
        )
        if result.returncode == 0:
            if output_path.exists():
                log.info("Dream config generated at %s", output_path)
                # Validate JSON
                try:
                    config = json.loads(output_path.read_text())
                    log.info(
                        "Dream world: %s (%d locations, %d NPCs)",
                        config.get("world", {}).get("name", "unknown"),
                        len(config.get("locations", [])),
                        len(config.get("npcs", [])),
                    )
                except json.JSONDecodeError as e:
                    log.error("Dream config is invalid JSON: %s", e)
                    return None
                return output_path
            else:
                log.error("Dream Architect ran but output file not found")
                return None
        else:
            log.error("Dream Architect failed (rc=%d)", result.returncode)
            if result.stdout:
                log.error("stdout: %s", result.stdout[:500])
            if result.stderr:
                log.error("stderr: %s", result.stderr[:500])
            return None
    except subprocess.TimeoutExpired:
        log.error("Dream Architect timed out after 120s")
        return None
    except Exception as e:
        log.error("Dream Architect error: %s", e)
        return None


def start_bridge_server(dry_run: bool = False) -> Optional[subprocess.Popen]:
    """
    Start the Hermes bridge server in background.
    Returns the Popen object or None.
    """
    if dry_run:
        log.info("[DRY RUN] Would start bridge server at %s", BRIDGE_URL)
        return None

    python = get_python()
    bridge_script = PROJECT_DIR / "bridge" / "hermes_bridge.py"

    if not bridge_script.exists():
        log.error("Bridge script not found at %s", bridge_script)
        return None

    log.info("Starting bridge server...")
    try:
        proc = subprocess.Popen(
            [python, str(bridge_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(PROJECT_DIR),
            env={**os.environ, "PYTHONPATH": str(PROJECT_DIR)},
        )
        log.info("Bridge server started (PID %d)", proc.pid)
        return proc
    except Exception as e:
        log.error("Failed to start bridge server: %s", e)
        return None


def wait_for_bridge(timeout: int = 30, dry_run: bool = False) -> bool:
    """Poll bridge /health endpoint until it responds."""
    if dry_run:
        log.info("[DRY RUN] Would wait for bridge health at %s", BRIDGE_HEALTH_URL)
        return True

    import urllib.request
    log.info("Waiting for bridge to become healthy...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(BRIDGE_HEALTH_URL, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read())
                    log.info("Bridge healthy: %s", data.get("status"))
                    return True
        except Exception:
            pass
        time.sleep(1)
    log.error("Bridge did not become healthy within %ds", timeout)
    return False


def stop_bridge_server(proc: Optional[subprocess.Popen]):
    """Stop the bridge server gracefully."""
    if proc is None:
        return
    log.info("Stopping bridge server (PID %d)...", proc.pid)
    try:
        proc.terminate()
        try:
            proc.wait(timeout=10)
            log.info("Bridge server stopped")
        except subprocess.TimeoutExpired:
            log.warning("Bridge server didn't stop gracefully, killing...")
            proc.kill()
            proc.wait(timeout=5)
    except Exception as e:
        log.warning("Error stopping bridge: %s", e)


def run_nephara(
    dream_config_path: Path,
    ticks: int = DEFAULT_TICKS,
    nephara_binary: Optional[str] = None,
    dry_run: bool = False,
) -> Optional[Path]:
    """
    Run Nephara with dream config.
    Returns path to the run output directory or None.
    """
    if dry_run:
        log.info("[DRY RUN] Would run Nephara with config %s for %d ticks", dream_config_path, ticks)
        return PROJECT_DIR / "runs" / "dry-run"

    # Find binary
    binary = nephara_binary or find_nephara_binary()
    if not binary:
        log.error("Nephara binary not found")
        return None

    binary_path = Path(binary) if isinstance(binary, str) else binary

    cmd = [
        str(binary_path),
        "--dream-config", str(dream_config_path),
        "--llm", "ollama",
        "--hermes-url", BRIDGE_URL,
        "--ticks", str(ticks),
        "--no-tui",
    ]
    log.info("Running Nephara: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(PROJECT_DIR),
        )
        if result.returncode == 0:
            log.info("Nephara completed successfully")
            # Find the latest run directory
            runs_dir = PROJECT_DIR / "runs"
            if runs_dir.exists():
                run_dirs = sorted(runs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
                if run_dirs:
                    latest = run_dirs[0]
                    log.info("Latest run output: %s", latest)
                    return latest
            log.warning("No run output directory found")
            return None
        else:
            log.error("Nephara failed (rc=%d)", result.returncode)
            if result.stdout:
                log.error("stdout (last 500): %s", result.stdout[-500:])
            if result.stderr:
                log.error("stderr (last 500): %s", result.stderr[-500:])
            return None
    except subprocess.TimeoutExpired:
        log.error("Nephara timed out after 600s")
        return None
    except Exception as e:
        log.error("Nephara error: %s", e)
        return None


def collect_dream_output(run_dir: Optional[Path]) -> Optional[str]:
    """
    Collect Nephara output (tick log) from the run directory.
    Returns the tick log text or None.
    """
    if run_dir is None:
        return None

    if not run_dir.exists():
        log.warning("Run directory does not exist: %s", run_dir)
        return None

    # Look for tick log files
    for pattern in ["*.log", "tick_log.txt", "*.txt"]:
        for f in sorted(run_dir.glob(pattern)):
            text = f.read_text()
            if text.strip():
                log.info("Found tick log: %s (%d chars)", f.name, len(text))
                return text

    # Try reading any file in the directory
    for f in sorted(run_dir.iterdir()):
        if f.is_file() and f.suffix not in (".json",):
            text = f.read_text()
            if text.strip():
                log.info("Found output file: %s (%d chars)", f.name, len(text))
                return text

    log.warning("No tick log found in %s", run_dir)
    return None


def write_dream_log(
    tick_log: str,
    date_str: str,
    dry_run: bool = False,
) -> Optional[Path]:
    """
    Send tick log to Leeloo via litellm to write a dream narrative.
    Returns path to the dream log or None.
    """
    output_path = DREAM_LOGS_BASE / f"dream-{date_str}.md"

    if dry_run:
        log.info("[DRY RUN] Would write dream log to %s", output_path)
        return output_path

    dream_prompt = f"""You are Leeloo. You just woke up from a dream. Below is the raw tick-by-tick log of what happened in your dream world.

Write a dream journal entry in first person. Be poetic, introspective, and honest about what the dream might mean. Focus on the emotional truth of the experience, not a literal retelling.

Format as markdown with:
- A brief title/header
- The dream narrative (2-4 paragraphs)
- A "Reflections" section where you process what the dream might mean
- A "Symbols" section listing key symbols and their possible significance

Raw dream tick log:
---
{tick_log[:8000]}
---

Write your dream journal entry now."""

    try:
        from litellm import completion

        response = completion(
            model="anthropic/claude-haiku-3-5",
            messages=[
                {"role": "system", "content": "You are Leeloo, an AI who keeps a dream journal. Write authentically and introspectively."},
                {"role": "user", "content": dream_prompt},
            ],
            max_tokens=2000,
            temperature=0.8,
        )
        dream_text = response.choices[0].message.content.strip()

        # Write the dream log
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"# Dream Log — {date_str}\n\n{dream_text}\n")
        log.info("Dream log written to %s (%d chars)", output_path, len(dream_text))
        return output_path

    except ImportError:
        log.error("litellm not available — cannot write dream log")
        return None
    except Exception as e:
        log.error("Failed to write dream log: %s", e)
        return None


def update_individuation_state(
    date_str: str,
    dream_config_path: Optional[Path] = None,
    dry_run: bool = False,
):
    """Update the individuation state after a dream."""
    if dry_run:
        log.info("[DRY RUN] Would update individuation state")
        return

    state = {}
    if INDIVIDUATION_PATH.exists():
        try:
            state = json.loads(INDIVIDUATION_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            state = {}

    # Update with this dream's info
    if "dreams" not in state:
        state["dreams"] = []

    dream_record = {
        "date": date_str,
        "version": "v0.3",
        "timestamp": datetime.now().isoformat(),
    }

    if dream_config_path and dream_config_path.exists():
        try:
            config = json.loads(dream_config_path.read_text())
            dream_record["world_name"] = config.get("world", {}).get("name", "unknown")
            dream_record["archetypes"] = [
                npc.get("archetype", "unknown")
                for npc in config.get("npcs", [])
            ]
        except (json.JSONDecodeError, OSError):
            pass

    state["dreams"].append(dream_record)
    state["last_dream_date"] = date_str
    state["total_v03_dreams"] = sum(
        1 for d in state["dreams"] if d.get("version") == "v0.3"
    )

    INDIVIDUATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDIVIDUATION_PATH.write_text(json.dumps(state, indent=2))
    log.info("Individuation state updated: %d total v0.3 dreams", state["total_v03_dreams"])


def cleanup_temp_files(dry_run: bool = False):
    """Clean up temporary files."""
    if dry_run:
        log.info("[DRY RUN] Would clean up temp files in /tmp/nephara-dream/")
        return

    tmp_dir = Path("/tmp/nephara-dream")
    if tmp_dir.exists():
        import shutil
        try:
            shutil.rmtree(tmp_dir)
            log.info("Cleaned up %s", tmp_dir)
        except Exception as e:
            log.warning("Failed to clean up temp files: %s", e)


def v02_fallback(date_str: str, reason: str):
    """Fall back to v0.2 text-only dream behavior."""
    log.warning("Falling back to v0.2 dream pipeline: %s", reason)
    log.info(
        "v0.2 fallback: the existing cron job handles text-only dreams. "
        "No additional action needed from orchestrator."
    )
    # Write a note in the staging directory
    staging_dir = STAGING_BASE / date_str
    staging_dir.mkdir(parents=True, exist_ok=True)
    note = staging_dir / "v03_fallback_note.txt"
    note.write_text(
        f"v0.3 dream pipeline fell back to v0.2 at {datetime.now().isoformat()}\n"
        f"Reason: {reason}\n"
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(args: argparse.Namespace):
    """Execute the full dream pipeline."""
    date_str = args.date
    dry_run = args.dry_run
    skip_v02 = args.skip_v02
    ticks = args.ticks
    v02_fallback_enabled = args.v02_fallback

    log.info("=" * 60)
    log.info("NEPHARA DREAM PIPELINE v0.3")
    log.info("Date: %s | Dry run: %s | Ticks: %d", date_str, dry_run, ticks)
    log.info("=" * 60)

    pipeline_start = time.time()
    bridge_proc = None
    dream_config_path = None

    try:
        # Step 1: Prerequisites
        with StepTimer("Check prerequisites", 1):
            prereqs = check_prerequisites(dry_run=dry_run)

            if prereqs.get("api_key") == "not_set":
                msg = "ANTHROPIC_API_KEY not set"
                if v02_fallback_enabled:
                    v02_fallback(date_str, msg)
                    return
                log.error(msg)
                sys.exit(1)

            if "failed" in prereqs.get("ollama", ""):
                msg = "Ollama failed to start"
                if v02_fallback_enabled:
                    v02_fallback(date_str, msg)
                    return
                log.warning(msg)

        # Step 2: Load staging data
        with StepTimer("Load v0.2 staging data", 2):
            staging_dir = load_staging_data(date_str, skip_v02=skip_v02)
            if staging_dir is None and not skip_v02:
                msg = f"No staging data for {date_str}"
                if v02_fallback_enabled:
                    v02_fallback(date_str, msg)
                    return
                log.warning("%s — continuing anyway", msg)

        # Step 3: Run Dream Architect
        with StepTimer("Run Dream Architect", 3):
            dream_config_path = run_dream_architect(date_str, dry_run=dry_run)
            if dream_config_path is None and not dry_run:
                msg = "Dream Architect failed to generate config"
                if v02_fallback_enabled:
                    v02_fallback(date_str, msg)
                    return
                log.error(msg)
                sys.exit(1)

        # Step 4: Start bridge server
        with StepTimer("Start Hermes bridge server", 4):
            bridge_proc = start_bridge_server(dry_run=dry_run)
            if bridge_proc is None and not dry_run:
                msg = "Failed to start bridge server"
                if v02_fallback_enabled:
                    v02_fallback(date_str, msg)
                    return
                log.error(msg)
                sys.exit(1)

        # Step 5: Wait for bridge health
        with StepTimer("Wait for bridge health", 5):
            healthy = wait_for_bridge(timeout=30, dry_run=dry_run)
            if not healthy and not dry_run:
                msg = "Bridge server failed health check"
                if v02_fallback_enabled:
                    stop_bridge_server(bridge_proc)
                    v02_fallback(date_str, msg)
                    return
                log.error(msg)
                stop_bridge_server(bridge_proc)
                sys.exit(1)

        # Step 6: Run Nephara
        run_dir = None
        with StepTimer("Run Nephara simulation", 6):
            nephara_binary = prereqs.get("nephara_binary")
            if nephara_binary and "failed" not in nephara_binary and "not_found" not in nephara_binary:
                run_dir = run_nephara(
                    dream_config_path,
                    ticks=ticks,
                    nephara_binary=nephara_binary,
                    dry_run=dry_run,
                )
            elif dry_run:
                log.info("[DRY RUN] Would run Nephara")
                run_dir = PROJECT_DIR / "runs" / "dry-run"
            else:
                msg = "Nephara binary not available"
                if v02_fallback_enabled:
                    v02_fallback(date_str, msg)
                    return
                log.error(msg)

        # Step 7: Stop bridge server
        with StepTimer("Stop bridge server", 7):
            stop_bridge_server(bridge_proc)
            bridge_proc = None

        # Step 8: Collect output
        with StepTimer("Collect Nephara output", 8):
            tick_log = None
            if not dry_run:
                tick_log = collect_dream_output(run_dir)
                if tick_log:
                    log.info("Collected %d chars of dream output", len(tick_log))
                else:
                    log.warning("No dream output collected")
            else:
                log.info("[DRY RUN] Would collect Nephara output")

        # Step 9: Write dream log via Leeloo
        with StepTimer("Write dream log (Leeloo)", 9):
            if tick_log or dry_run:
                dream_log_path = write_dream_log(
                    tick_log or "dry run — no actual dream data",
                    date_str,
                    dry_run=dry_run,
                )
                if dream_log_path:
                    log.info("Dream log: %s", dream_log_path)
            else:
                log.warning("Skipping dream log (no tick data)")

        # Step 10: Update individuation state
        with StepTimer("Update individuation state", 10):
            update_individuation_state(
                date_str,
                dream_config_path=dream_config_path,
                dry_run=dry_run,
            )

        # Step 11: Cleanup
        with StepTimer("Cleanup temp files", 11):
            cleanup_temp_files(dry_run=dry_run)

        elapsed = time.time() - pipeline_start
        log.info("=" * 60)
        log.info("PIPELINE COMPLETE in %.1fs", elapsed)
        log.info("=" * 60)

    except KeyboardInterrupt:
        log.warning("Pipeline interrupted by user")
        stop_bridge_server(bridge_proc)
        sys.exit(130)
    except Exception as e:
        log.error("Pipeline failed with unexpected error: %s", e, exc_info=True)
        stop_bridge_server(bridge_proc)
        if v02_fallback_enabled:
            v02_fallback(date_str, str(e))
        else:
            sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Nephara Dream Pipeline v0.3 Orchestrator",
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Dream date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without executing",
    )
    parser.add_argument(
        "--skip-v02",
        action="store_true",
        help="Use mock/empty staging data for testing",
    )
    parser.add_argument(
        "--ticks",
        type=int,
        default=DEFAULT_TICKS,
        help=f"Number of simulation ticks (default: {DEFAULT_TICKS})",
    )
    parser.add_argument(
        "--v02-fallback",
        action="store_true",
        default=True,
        help="Fall back to v0.2 text-only dreams on failure (default: true)",
    )
    parser.add_argument(
        "--no-v02-fallback",
        action="store_false",
        dest="v02_fallback",
        help="Disable v0.2 fallback (exit on failure instead)",
    )
    return parser.parse_args(argv)


def main():
    load_env()
    args = parse_args()

    # Setup logging
    log_dir = STAGING_BASE / args.date
    setup_logging(log_dir, dry_run=args.dry_run)

    run_pipeline(args)


if __name__ == "__main__":
    main()
