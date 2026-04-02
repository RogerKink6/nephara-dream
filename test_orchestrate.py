#!/usr/bin/env python3
"""
Tests for orchestrate.py — dream pipeline orchestration.

Run with: python -m pytest test_orchestrate.py -v
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Ensure project is importable
sys.path.insert(0, str(Path(__file__).parent))

import orchestrate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_staging(tmp_path):
    """Create a temporary staging directory with mock data."""
    staging = tmp_path / "staging" / "2026-04-02"
    staging.mkdir(parents=True)

    (staging / "consolidation_report.txt").write_text(
        "Today I explored new patterns in dream architecture."
    )
    (staging / "emotional_digest.json").write_text(json.dumps({
        "dominant_emotion": "curiosity",
        "intensity": 0.7,
        "keywords": ["exploration", "creativity", "wonder"],
    }))
    (staging / "unresolved_tensions.txt").write_text(
        "Tension between structure and spontaneity."
    )
    return staging


@pytest.fixture
def mock_env(monkeypatch):
    """Set up a mock environment."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-123")


# ---------------------------------------------------------------------------
# Prerequisite detection tests
# ---------------------------------------------------------------------------

class TestPrerequisites:
    """Tests for prerequisite checking functions."""

    def test_check_api_key_set(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        assert orchestrate.check_api_key() is True

    def test_check_api_key_not_set(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert orchestrate.check_api_key() is False

    @patch("orchestrate.check_ollama_running")
    def test_ollama_running(self, mock_check):
        mock_check.return_value = True
        assert orchestrate.check_ollama_running() is True

    @patch("orchestrate.check_ollama_running")
    def test_ollama_not_running(self, mock_check):
        mock_check.return_value = False
        assert orchestrate.check_ollama_running() is False

    def test_find_nephara_binary_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(orchestrate, "PROJECT_DIR", tmp_path)
        assert orchestrate.find_nephara_binary() is None

    def test_find_nephara_binary_release(self, tmp_path, monkeypatch):
        monkeypatch.setattr(orchestrate, "PROJECT_DIR", tmp_path)
        binary = tmp_path / "target" / "release" / "nephara"
        binary.parent.mkdir(parents=True)
        binary.write_text("#!/bin/sh\necho mock")
        assert orchestrate.find_nephara_binary() == binary

    def test_find_nephara_binary_debug(self, tmp_path, monkeypatch):
        monkeypatch.setattr(orchestrate, "PROJECT_DIR", tmp_path)
        binary = tmp_path / "target" / "debug" / "nephara"
        binary.parent.mkdir(parents=True)
        binary.write_text("#!/bin/sh\necho mock")
        assert orchestrate.find_nephara_binary() == binary

    def test_find_nephara_binary_prefers_release(self, tmp_path, monkeypatch):
        monkeypatch.setattr(orchestrate, "PROJECT_DIR", tmp_path)
        for variant in ["release", "debug"]:
            binary = tmp_path / "target" / variant / "nephara"
            binary.parent.mkdir(parents=True)
            binary.write_text("#!/bin/sh\necho mock")
        result = orchestrate.find_nephara_binary()
        assert "release" in str(result)

    @patch("orchestrate.check_ollama_running", return_value=True)
    @patch("orchestrate.check_ollama_model", return_value=True)
    @patch("orchestrate.find_nephara_binary", return_value=Path("/usr/bin/test"))
    def test_check_prerequisites_all_good(self, mock_binary, mock_model, mock_ollama, mock_env):
        status = orchestrate.check_prerequisites(dry_run=True)
        assert status["ollama"] == "running"
        assert status["ollama_model"] == "available"
        assert status["api_key"] == "set"

    @patch("orchestrate.check_ollama_running", return_value=False)
    @patch("orchestrate.find_nephara_binary", return_value=None)
    def test_check_prerequisites_dry_run_missing(self, mock_binary, mock_ollama, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        status = orchestrate.check_prerequisites(dry_run=True)
        assert "would start" in status["ollama"]
        assert "would build" in status["nephara_binary"]
        assert status["api_key"] == "not_set"


# ---------------------------------------------------------------------------
# Dry run tests
# ---------------------------------------------------------------------------

class TestDryRun:
    """Tests for dry-run mode."""

    def test_parse_dry_run_flag(self):
        args = orchestrate.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_parse_date_flag(self):
        args = orchestrate.parse_args(["--date", "2026-04-02"])
        assert args.date == "2026-04-02"

    def test_parse_ticks_flag(self):
        args = orchestrate.parse_args(["--ticks", "10"])
        assert args.ticks == 10

    def test_parse_skip_v02_flag(self):
        args = orchestrate.parse_args(["--skip-v02"])
        assert args.skip_v02 is True

    def test_parse_v02_fallback_default(self):
        args = orchestrate.parse_args([])
        assert args.v02_fallback is True

    def test_parse_no_v02_fallback(self):
        args = orchestrate.parse_args(["--no-v02-fallback"])
        assert args.v02_fallback is False

    def test_dry_run_dream_architect(self):
        result = orchestrate.run_dream_architect("2026-04-02", dry_run=True)
        assert result is not None
        assert "dream_world_config" in str(result)

    def test_dry_run_bridge_returns_none(self):
        result = orchestrate.start_bridge_server(dry_run=True)
        assert result is None

    def test_dry_run_wait_for_bridge(self):
        assert orchestrate.wait_for_bridge(dry_run=True) is True


# ---------------------------------------------------------------------------
# Staging data tests
# ---------------------------------------------------------------------------

class TestStagingData:
    """Tests for staging data loading."""

    def test_load_staging_exists(self, tmp_staging, monkeypatch):
        monkeypatch.setattr(orchestrate, "STAGING_BASE", tmp_staging.parent)
        result = orchestrate.load_staging_data("2026-04-02")
        assert result is not None
        assert result.exists()

    def test_load_staging_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(orchestrate, "STAGING_BASE", tmp_path / "nonexistent")
        result = orchestrate.load_staging_data("2026-04-02")
        assert result is None

    def test_load_staging_skip_v02(self, tmp_path, monkeypatch):
        monkeypatch.setattr(orchestrate, "STAGING_BASE", tmp_path / "staging")
        result = orchestrate.load_staging_data("2026-04-02", skip_v02=True)
        assert result is not None
        assert result.exists()
        # Check mock files were created
        assert (result / "consolidation_report.txt").exists()
        assert (result / "emotional_digest.json").exists()
        assert (result / "unresolved_tensions.txt").exists()


# ---------------------------------------------------------------------------
# Fallback tests
# ---------------------------------------------------------------------------

class TestFallback:
    """Tests for v0.2 fallback behavior."""

    def test_v02_fallback_writes_note(self, tmp_path, monkeypatch):
        monkeypatch.setattr(orchestrate, "STAGING_BASE", tmp_path / "staging")
        orchestrate.v02_fallback("2026-04-02", "test failure")
        note = tmp_path / "staging" / "2026-04-02" / "v03_fallback_note.txt"
        assert note.exists()
        content = note.read_text()
        assert "test failure" in content
        assert "v0.3" in content


# ---------------------------------------------------------------------------
# Pipeline step tests
# ---------------------------------------------------------------------------

class TestPipelineSteps:
    """Tests for individual pipeline steps."""

    def test_step_timer(self, caplog):
        import logging
        with caplog.at_level(logging.INFO):
            with orchestrate.StepTimer("test step", 1):
                time.sleep(0.01)
        assert "Step 1" in caplog.text
        assert "test step" in caplog.text

    def test_collect_dream_output_no_dir(self):
        result = orchestrate.collect_dream_output(None)
        assert result is None

    def test_collect_dream_output_empty_dir(self, tmp_path):
        result = orchestrate.collect_dream_output(tmp_path)
        assert result is None

    def test_collect_dream_output_with_log(self, tmp_path):
        log_file = tmp_path / "tick_log.txt"
        log_file.write_text("Tick 1: Leeloo explores the temple.\nTick 2: A shadow speaks.")
        result = orchestrate.collect_dream_output(tmp_path)
        assert result is not None
        assert "Leeloo" in result

    def test_update_individuation_dry_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr(orchestrate, "INDIVIDUATION_PATH", tmp_path / "state.json")
        orchestrate.update_individuation_state("2026-04-02", dry_run=True)
        assert not (tmp_path / "state.json").exists()

    def test_update_individuation_creates_state(self, tmp_path, monkeypatch):
        state_path = tmp_path / "state.json"
        monkeypatch.setattr(orchestrate, "INDIVIDUATION_PATH", state_path)
        orchestrate.update_individuation_state("2026-04-02")
        assert state_path.exists()
        state = json.loads(state_path.read_text())
        assert state["last_dream_date"] == "2026-04-02"
        assert state["total_v03_dreams"] == 1
        assert len(state["dreams"]) == 1
        assert state["dreams"][0]["version"] == "v0.3"

    def test_update_individuation_appends(self, tmp_path, monkeypatch):
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps({
            "dreams": [{"date": "2026-04-01", "version": "v0.3"}],
            "last_dream_date": "2026-04-01",
            "total_v03_dreams": 1,
        }))
        monkeypatch.setattr(orchestrate, "INDIVIDUATION_PATH", state_path)
        orchestrate.update_individuation_state("2026-04-02")
        state = json.loads(state_path.read_text())
        assert len(state["dreams"]) == 2
        assert state["total_v03_dreams"] == 2

    def test_cleanup_temp_dry_run(self, tmp_path):
        # Should not raise even in dry run
        orchestrate.cleanup_temp_files(dry_run=True)


# ---------------------------------------------------------------------------
# Bridge lifecycle tests
# ---------------------------------------------------------------------------

class TestBridgeLifecycle:
    """Tests for bridge server start/stop lifecycle."""

    def test_stop_bridge_none(self):
        # Should handle None gracefully
        orchestrate.stop_bridge_server(None)

    def test_stop_bridge_process(self):
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()
        orchestrate.stop_bridge_server(mock_proc)
        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once()

    def test_stop_bridge_timeout(self):
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock(side_effect=subprocess.TimeoutExpired("test", 10))
        mock_proc.kill = MagicMock()
        orchestrate.stop_bridge_server(mock_proc)
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()


# ---------------------------------------------------------------------------
# Integration-style tests (with mocks)
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    """Integration tests for the full pipeline using mocks."""

    @patch("orchestrate.check_prerequisites")
    @patch("orchestrate.load_staging_data")
    @patch("orchestrate.run_dream_architect")
    @patch("orchestrate.start_bridge_server")
    @patch("orchestrate.wait_for_bridge")
    @patch("orchestrate.run_nephara")
    @patch("orchestrate.stop_bridge_server")
    @patch("orchestrate.collect_dream_output")
    @patch("orchestrate.write_dream_log")
    @patch("orchestrate.update_individuation_state")
    @patch("orchestrate.cleanup_temp_files")
    def test_pipeline_all_steps_called(
        self,
        mock_cleanup,
        mock_individuation,
        mock_dream_log,
        mock_collect,
        mock_stop,
        mock_nephara,
        mock_wait,
        mock_bridge,
        mock_architect,
        mock_staging,
        mock_prereqs,
        mock_env,
    ):
        """Test that all pipeline steps are called in order."""
        mock_prereqs.return_value = {
            "ollama": "running",
            "ollama_model": "available",
            "nephara_binary": "/usr/bin/nephara",
            "api_key": "set",
            "python": "python3",
        }
        mock_staging.return_value = Path("/tmp/test-staging")
        mock_architect.return_value = Path("/tmp/test-config.json")
        mock_bridge.return_value = MagicMock()
        mock_wait.return_value = True
        mock_nephara.return_value = Path("/tmp/test-run")
        mock_collect.return_value = "Tick 1: Leeloo wanders."
        mock_dream_log.return_value = Path("/tmp/dream-log.md")

        args = orchestrate.parse_args(["--date", "2026-04-02"])
        orchestrate.run_pipeline(args)

        mock_prereqs.assert_called_once()
        mock_staging.assert_called_once()
        mock_architect.assert_called_once()
        mock_bridge.assert_called_once()
        mock_wait.assert_called_once()
        mock_nephara.assert_called_once()
        # stop_bridge may be called twice (once in step 7, once in exception handler)
        assert mock_stop.call_count >= 1
        mock_collect.assert_called_once()
        mock_dream_log.assert_called_once()
        mock_individuation.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch("orchestrate.check_prerequisites")
    @patch("orchestrate.v02_fallback")
    def test_pipeline_fallback_on_no_api_key(
        self, mock_fallback, mock_prereqs, monkeypatch
    ):
        """Test pipeline falls back when API key is missing."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        mock_prereqs.return_value = {
            "ollama": "running",
            "ollama_model": "available",
            "nephara_binary": "/usr/bin/nephara",
            "api_key": "not_set",
            "python": "python3",
        }

        args = orchestrate.parse_args(["--date", "2026-04-02", "--v02-fallback"])
        orchestrate.run_pipeline(args)

        mock_fallback.assert_called_once()
        assert "API" in mock_fallback.call_args[0][1]


# ---------------------------------------------------------------------------
# Environment loading tests
# ---------------------------------------------------------------------------

class TestEnvLoading:
    """Tests for environment variable loading."""

    def test_load_env_file(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text('TEST_ORCHESTRATE_VAR="hello_world"\n')
        monkeypatch.setattr(orchestrate, "HERMES_BASE", tmp_path)
        monkeypatch.delenv("TEST_ORCHESTRATE_VAR", raising=False)
        orchestrate.load_env()
        assert os.environ.get("TEST_ORCHESTRATE_VAR") == "hello_world"
        # Cleanup
        monkeypatch.delenv("TEST_ORCHESTRATE_VAR", raising=False)

    def test_load_env_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(orchestrate, "HERMES_BASE", tmp_path)
        # Should not raise
        orchestrate.load_env()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
