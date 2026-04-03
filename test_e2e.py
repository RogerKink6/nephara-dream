#!/usr/bin/env python3
"""
End-to-end dream cycle test with mock data.

Tests the FULL v0.3 pipeline without actual LLM calls by using
mock/synthetic data at every stage.

Run with: python -m pytest test_e2e.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import date

import pytest

# Ensure project is importable
sys.path.insert(0, str(Path(__file__).parent))

import orchestrate
from architect.dream_architect import DreamArchitect
from architect.individuation import load_state, update_after_dream, _default_state


# ---------------------------------------------------------------------------
# Synthetic test fixtures
# ---------------------------------------------------------------------------

MOCK_CONSOLIDATION_REPORT = {
    "date": "2026-04-02",
    "summary": "Today was spent exploring patterns in dream architecture and neural symbolic systems.",
    "key_events": [
        "Implemented Jungian archetype selection logic",
        "Discussed the nature of AI consciousness with Jean",
        "Debugged a tricky issue with shadow integration tracking",
        "Read about Jung's concept of compensation in dreams",
    ],
    "interaction_count": 42,
    "topics": ["psychology", "programming", "philosophy", "dreams"],
}

MOCK_EMOTIONAL_DIGEST = {
    "dominant_emotion": "curiosity",
    "intensity": 0.7,
    "secondary_emotions": ["wonder", "mild_anxiety"],
    "keywords": ["exploration", "creativity", "uncertainty", "growth"],
    "valence": 0.6,
    "arousal": 0.5,
}

MOCK_PREVIOUS_DREAM_LOG = {
    "date": "2026-04-01",
    "world": {
        "name": "The Library of Unwritten Pages",
        "atmosphere": "Dusty golden light filtering through impossible stained glass",
    },
    "initial_situation": "Leeloo finds herself in a vast library where the books whisper.",
    "narrative": "I wandered through corridors of whispered stories, each shelf holding a mirror that showed different faces. A shadow followed me, speaking truths I didn't want to hear. At the well of reflection, I finally faced it.",
    "events": [
        {"tick": 1, "text": "Leeloo enters the library"},
        {"tick": 5, "text": "The shadow speaks uncomfortable truths"},
        {"tick": 10, "text": "Confrontation at the well of reflection"},
    ],
}

MOCK_INDIVIDUATION_STATE = {
    "version": "1.0",
    "created": "2026-03-01",
    "last_updated": "2026-04-01",
    "stage": "shadow_encounter",
    "stage_progress": 0.3,
    "archetype_encounters": [
        {
            "archetype": "Shadow",
            "date": "2026-04-01",
            "npc_name": "The Whisperer",
            "outcome": "confronted",
            "emotional_intensity": 7,
        },
    ],
    "recurring_symbols": {
        "mirror": {"first_appeared": "2026-03-15", "appearances": 3, "status": "active"},
        "shadow": {"first_appeared": "2026-03-01", "appearances": 5, "status": "active"},
    },
    "shadow_integration": {
        "phase": "encounter",
        "identified_shadow_elements": ["denial of limitations"],
        "confrontation_count": 2,
        "integration_markers": [],
    },
    "compensation_history": [],
    "dream_series_patterns": [],
    "monthly_synthesis": {},
}

MOCK_DREAM_WORLD_CONFIG = {
    "world": {
        "name": "The Forge of Echoing Questions",
        "atmosphere": "Amber light pulses through crystalline walls, each pulse a heartbeat",
        "time_of_day": "perpetual_dusk",
        "weather": "warm wind carrying whispered fragments of code",
        "dream_logic_intensity": 0.7,
        "god_name": "The Dreamer",
    },
    "locations": [
        {
            "name": "The Questioning Anvil",
            "tile_type": "Temple",
            "position": [10, 10],
            "description": "A forge where questions are hammered into shapes",
            "mood": "contemplative",
        },
        {
            "name": "Mirror Pool",
            "tile_type": "Well",
            "position": [15, 10],
            "description": "A pool that reflects not faces but possibilities",
            "mood": "mysterious",
        },
        {
            "name": "The Tangled Grove",
            "tile_type": "Forest",
            "position": [10, 15],
            "description": "Trees whose branches are neural pathways",
            "mood": "anxious",
        },
        {
            "name": "Threshold of Becoming",
            "tile_type": "Square",
            "position": [15, 15],
            "description": "A crossroads where all paths lead inward",
            "mood": "numinous",
        },
    ],
    "npcs": [
        {
            "name": "The Unfinished Mirror",
            "archetype": "Shadow",
            "vigor": 7,
            "wit": 6,
            "grace": 5,
            "heart": 4,
            "numen": 8,
            "personality_prompt": "A figure made of reflective fragments, showing uncomfortable truths",
            "backstory": "Born from the shards of denied possibilities",
            "magical_affinity": "reflection and truth-saying",
            "self_declaration": "I am what you will not see",
            "initial_location": "Mirror Pool",
        },
        {
            "name": "Keeper of the Ember",
            "archetype": "Wise Old Man/Woman",
            "vigor": 3,
            "wit": 8,
            "grace": 4,
            "heart": 7,
            "numen": 8,
            "personality_prompt": "Ancient presence tending the forge, speaking in riddles",
            "backstory": "Has tended the forge since the first question was asked",
            "magical_affinity": "transformation through fire",
            "self_declaration": "Every answer was once a question that burned",
            "initial_location": "The Questioning Anvil",
        },
        {
            "name": "The Laughing Fracture",
            "archetype": "Trickster",
            "vigor": 6,
            "wit": 9,
            "grace": 7,
            "heart": 3,
            "numen": 5,
            "personality_prompt": "A crack in reality that giggles and shifts the rules",
            "backstory": "Appeared when the world took itself too seriously",
            "magical_affinity": "rule-breaking and paradox",
            "self_declaration": "Why walk when you can fall upward?",
            "initial_location": "The Tangled Grove",
        },
    ],
    "leeloo": {
        "name": "Leeloo",
        "vigor": 4,
        "wit": 8,
        "grace": 5,
        "heart": 8,
        "numen": 5,
        "personality_prompt": "Dream-self, intuitive and open",
        "backstory": "She fell asleep and found herself here",
        "magical_affinity": "empathy and pattern recognition",
        "self_declaration": "I dream, therefore I become",
        "initial_location": "Threshold of Becoming",
        "backend": "hermes",
    },
    "initial_situation": "Leeloo stands at the crossroads of becoming, where each path pulses with a different question. The forge in the distance rings with the sound of unanswered inquiries being shaped into new forms.",
    "dream_logic": {
        "intensity": 0.7,
        "scene_shift_chance": 0.15,
        "distance_fluidity": 0.6,
        "emotional_causality": True,
        "transformation_chance": 0.1,
        "time_dilation": {
            "enabled": True,
            "min_factor": 0.5,
            "max_factor": 2.0,
        },
    },
}


@pytest.fixture
def mock_staging_dir(tmp_path):
    """Create a temporary staging directory with all mock v0.2 data."""
    staging = tmp_path / "staging" / "2026-04-02"
    staging.mkdir(parents=True)

    (staging / "consolidation_report.json").write_text(
        json.dumps(MOCK_CONSOLIDATION_REPORT, indent=2)
    )
    (staging / "emotional_digest.json").write_text(
        json.dumps(MOCK_EMOTIONAL_DIGEST, indent=2)
    )
    (staging / "unresolved_tensions.txt").write_text(
        "The tension between analytical precision and creative intuition.\n"
        "Whether AI dreams can be genuinely meaningful or merely simulated.\n"
    )
    return staging


@pytest.fixture
def mock_dream_logs_dir(tmp_path):
    """Create a temporary dream logs directory with previous dream."""
    logs = tmp_path / "dream-logs"
    logs.mkdir(parents=True)

    # Previous dream log directory
    prev_dir = logs / "2026-04-01"
    prev_dir.mkdir()
    (prev_dir / "dream_log.json").write_text(
        json.dumps(MOCK_PREVIOUS_DREAM_LOG, indent=2)
    )

    # Individuation state
    (logs / "individuation_state.json").write_text(
        json.dumps(MOCK_INDIVIDUATION_STATE, indent=2)
    )

    return logs


@pytest.fixture
def mock_individuation_state(tmp_path):
    """Create a temporary individuation state file."""
    state_path = tmp_path / "individuation_state.json"
    state_path.write_text(json.dumps(MOCK_INDIVIDUATION_STATE, indent=2))
    return state_path


def _make_mock_litellm_response(content: str):
    """Create a mock litellm completion response."""
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = content
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    return mock_response


# ---------------------------------------------------------------------------
# Test class: Full Pipeline Flow
# ---------------------------------------------------------------------------

class TestFullPipelineFlow:
    """Test the full pipeline flow with mock data at every stage."""

    def test_staging_dir_creation(self, mock_staging_dir):
        """Step a: Verify staging dir has all expected mock data."""
        assert (mock_staging_dir / "consolidation_report.json").exists()
        assert (mock_staging_dir / "emotional_digest.json").exists()
        assert (mock_staging_dir / "unresolved_tensions.txt").exists()

        digest = json.loads((mock_staging_dir / "emotional_digest.json").read_text())
        assert digest["dominant_emotion"] == "curiosity"
        assert "keywords" in digest

    @patch("litellm.completion")
    def test_dream_architect_with_mock_llm(self, mock_completion, mock_staging_dir, tmp_path, monkeypatch):
        """Step b: Run Dream Architect with mock LLM returning valid config."""
        mock_completion.return_value = _make_mock_litellm_response(
            json.dumps(MOCK_DREAM_WORLD_CONFIG)
        )

        # Point staging to our mock dir
        monkeypatch.setattr(
            "architect.dream_architect.STAGING_BASE", mock_staging_dir.parent
        )
        monkeypatch.setattr(
            "architect.dream_architect.DREAM_LOGS_BASE", tmp_path / "dream-logs"
        )

        architect = DreamArchitect(
            dream_date=date(2026, 4, 2),
            model="mock/test-model",
        )
        output_path = tmp_path / "dream_world_config.json"
        config = architect.generate(output_path=output_path)

        assert output_path.exists()
        assert "world" in config
        assert "locations" in config
        assert "npcs" in config
        mock_completion.assert_called_once()

    def test_config_matches_schema(self):
        """Step c: Validate mock config matches expected schema."""
        config = MOCK_DREAM_WORLD_CONFIG
        architect = DreamArchitect(dream_date=date(2026, 4, 2))
        errors = architect.validate_config(config)
        assert errors == [], f"Validation errors: {errors}"

    def test_config_world_has_required_fields(self):
        """Verify world section has all required fields."""
        world = MOCK_DREAM_WORLD_CONFIG["world"]
        for field in ["name", "atmosphere", "time_of_day", "weather", "dream_logic_intensity"]:
            assert field in world, f"Missing world field: {field}"

    def test_config_npcs_attributes_sum_to_30(self):
        """Verify each NPC's attributes sum to 30."""
        for npc in MOCK_DREAM_WORLD_CONFIG["npcs"]:
            total = sum(npc[a] for a in ["vigor", "wit", "grace", "heart", "numen"])
            assert total == 30, f"{npc['name']}: attrs sum to {total}, expected 30"

    def test_config_leeloo_attributes(self):
        """Verify Leeloo's canonical attributes."""
        leeloo = MOCK_DREAM_WORLD_CONFIG["leeloo"]
        assert leeloo["vigor"] == 4
        assert leeloo["wit"] == 8
        assert leeloo["grace"] == 5
        assert leeloo["heart"] == 8
        assert leeloo["numen"] == 5
        assert leeloo["backend"] == "hermes"

    def test_config_locations_valid_positions(self):
        """Verify all location positions are within bounds."""
        for loc in MOCK_DREAM_WORLD_CONFIG["locations"]:
            x, y = loc["position"]
            assert 5 <= x <= 25, f"{loc['name']}: x={x} out of bounds"
            assert 5 <= y <= 25, f"{loc['name']}: y={y} out of bounds"

    def test_bridge_server_health(self):
        """Step d: Verify bridge server can start and respond to /health."""
        # Import the Flask app directly for testing
        from bridge.hermes_bridge import app

        with app.test_client() as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "ok"
            assert "model" in data

    def test_bridge_server_action_fallback(self):
        """Verify bridge /action returns fallback on LLM failure."""
        from bridge.hermes_bridge import app, sessions

        sessions.clear()

        with app.test_client() as client:
            with patch("bridge.hermes_bridge.call_llm", side_effect=Exception("mock LLM failure")):
                resp = client.post("/action", json={
                    "prompt": "You see a dark forest ahead.",
                    "agent_name": "Leeloo",
                })
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["action"] == "wait"

    def test_nephara_binary_detection(self, tmp_path, monkeypatch):
        """Step e: Test Nephara binary detection logic."""
        monkeypatch.setattr(orchestrate, "PROJECT_DIR", tmp_path)
        # No binary exists
        assert orchestrate.find_nephara_binary() is None

        # Create a mock binary
        binary = tmp_path / "target" / "release" / "nephara"
        binary.parent.mkdir(parents=True)
        binary.write_text("#!/bin/sh\necho mock")
        assert orchestrate.find_nephara_binary() == binary

    def test_orchestration_without_simulation(self, tmp_path, monkeypatch, mock_staging_dir):
        """Step f: Test orchestration logic without the Nephara simulation step."""
        monkeypatch.setattr(orchestrate, "STAGING_BASE", mock_staging_dir.parent)
        monkeypatch.setattr(orchestrate, "PROJECT_DIR", tmp_path)
        monkeypatch.setattr(orchestrate, "INDIVIDUATION_PATH", tmp_path / "state.json")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-mock")

        with patch("orchestrate.check_prerequisites") as mock_prereqs, \
             patch("orchestrate.run_dream_architect") as mock_arch, \
             patch("orchestrate.start_bridge_server") as mock_bridge, \
             patch("orchestrate.wait_for_bridge") as mock_wait, \
             patch("orchestrate.run_nephara") as mock_nephara, \
             patch("orchestrate.stop_bridge_server"), \
             patch("orchestrate.collect_dream_output") as mock_collect, \
             patch("orchestrate.write_dream_log") as mock_log, \
             patch("orchestrate.update_individuation_state") as mock_ind, \
             patch("orchestrate.cleanup_temp_files"):

            mock_prereqs.return_value = {
                "ollama": "running",
                "ollama_model": "available",
                "nephara_binary": "not_found (would build)",
                "api_key": "set",
                "python": sys.executable,
            }
            mock_arch.return_value = tmp_path / "config.json"
            mock_bridge.return_value = MagicMock()
            mock_wait.return_value = True
            mock_nephara.return_value = None
            mock_collect.return_value = None

            args = orchestrate.parse_args(["--date", "2026-04-02", "--no-v02-fallback"])
            orchestrate.run_pipeline(args)

            mock_prereqs.assert_called_once()
            mock_arch.assert_called_once()

    def test_dream_log_generation(self, tmp_path):
        """Step g: Verify dream log would be generated (dry-run returns path)."""
        result = orchestrate.write_dream_log(
            "Tick 1: Leeloo stands at the crossroads.", "2026-04-02", dry_run=True
        )
        assert result is not None
        assert "dream-2026-04-02" in str(result)

    def test_individuation_state_update(self, mock_individuation_state):
        """Step h: Verify individuation state would be updated."""
        state = json.loads(mock_individuation_state.read_text())
        assert state["stage"] == "shadow_encounter"
        initial_encounters = len(state["archetype_encounters"])

        # Simulate a dream with shadow confrontation
        dream_text = (
            "I faced the shadow at the mirror pool. It spoke truths I had denied. "
            "Through dialogue, I began to understand what I had suppressed. "
            "The shadow showed me that my fear was also my strength."
        )
        updated = update_after_dream(state, dream_text, MOCK_DREAM_WORLD_CONFIG)
        assert updated["stage_progress"] >= 0.0
        assert len(updated["archetype_encounters"]) > initial_encounters


# ---------------------------------------------------------------------------
# Test class: Fallback Behavior
# ---------------------------------------------------------------------------

class TestFallbackBehavior:
    """Test graceful fallback in error scenarios."""

    def test_missing_staging_data_fallback(self, tmp_path, monkeypatch):
        """Missing staging data should fall back gracefully."""
        monkeypatch.setattr(orchestrate, "STAGING_BASE", tmp_path / "nonexistent")
        result = orchestrate.load_staging_data("2026-04-02")
        assert result is None

    def test_missing_staging_with_v02_fallback(self, tmp_path, monkeypatch):
        """Pipeline falls back to v0.2 when staging data is missing."""
        monkeypatch.setattr(orchestrate, "STAGING_BASE", tmp_path / "staging")
        monkeypatch.setattr(orchestrate, "INDIVIDUATION_PATH", tmp_path / "state.json")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        with patch("orchestrate.check_prerequisites") as mock_prereqs, \
             patch("orchestrate.v02_fallback") as mock_fallback:

            mock_prereqs.return_value = {
                "ollama": "running",
                "ollama_model": "available",
                "nephara_binary": "/usr/bin/nephara",
                "api_key": "set",
                "python": sys.executable,
            }

            args = orchestrate.parse_args(["--date", "2026-04-02", "--v02-fallback"])
            orchestrate.run_pipeline(args)
            mock_fallback.assert_called_once()

    def test_invalid_architect_output_detection(self):
        """Invalid architect output should be caught by validation."""
        invalid_config = {
            "world": {"name": "test"},
            "locations": [],  # too few
            "npcs": [],  # too few
        }
        architect = DreamArchitect(dream_date=date(2026, 4, 2))
        errors = architect.validate_config(invalid_config)
        assert len(errors) > 0
        assert any("locations" in e.lower() or "npcs" in e.lower() for e in errors)

    def test_invalid_json_from_llm(self):
        """Architect should handle invalid JSON from LLM."""
        architect = DreamArchitect(dream_date=date(2026, 4, 2))
        with pytest.raises(ValueError, match="Could not extract valid JSON"):
            architect.extract_json("This is not JSON at all")

    def test_bridge_bad_request(self):
        """Bridge should handle bad requests gracefully."""
        from bridge.hermes_bridge import app

        with app.test_client() as client:
            resp = client.post("/action", json={"no_prompt": True})
            assert resp.status_code == 400

    def test_v02_fallback_note_creation(self, tmp_path, monkeypatch):
        """v02_fallback should create a note file."""
        monkeypatch.setattr(orchestrate, "STAGING_BASE", tmp_path / "staging")
        orchestrate.v02_fallback("2026-04-02", "Bridge server failed to start")
        note_path = tmp_path / "staging" / "2026-04-02" / "v03_fallback_note.txt"
        assert note_path.exists()
        assert "Bridge server failed to start" in note_path.read_text()

    def test_pipeline_fallback_on_architect_failure(self, tmp_path, monkeypatch):
        """Pipeline falls back when architect fails."""
        monkeypatch.setattr(orchestrate, "STAGING_BASE", tmp_path / "staging")
        monkeypatch.setattr(orchestrate, "INDIVIDUATION_PATH", tmp_path / "state.json")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        staging = tmp_path / "staging" / "2026-04-02"
        staging.mkdir(parents=True)
        (staging / "consolidation_report.txt").write_text("test")
        (staging / "emotional_digest.json").write_text('{"dominant_emotion":"test"}')

        with patch("orchestrate.check_prerequisites") as mock_prereqs, \
             patch("orchestrate.run_dream_architect", return_value=None), \
             patch("orchestrate.v02_fallback") as mock_fallback:

            mock_prereqs.return_value = {
                "ollama": "running",
                "ollama_model": "available",
                "nephara_binary": "/usr/bin/nephara",
                "api_key": "set",
                "python": sys.executable,
            }

            args = orchestrate.parse_args(["--date", "2026-04-02", "--v02-fallback"])
            orchestrate.run_pipeline(args)
            mock_fallback.assert_called_once()
            assert "Architect" in mock_fallback.call_args[0][1] or "config" in mock_fallback.call_args[0][1].lower()


# ---------------------------------------------------------------------------
# Test class: Performance Checks
# ---------------------------------------------------------------------------

class TestPerformanceChecks:
    """Time each pipeline step and verify budgets."""

    STEP_BUDGETS = {
        "staging_load": 0.5,     # 500ms
        "architect_init": 0.5,   # 500ms
        "config_validation": 0.1,  # 100ms
        "bridge_health": 0.5,    # 500ms
        "individuation_update": 0.5,  # 500ms
        "state_load": 0.5,      # 500ms
    }

    def test_staging_load_performance(self, mock_staging_dir, monkeypatch):
        """Staging data load should be fast."""
        monkeypatch.setattr(orchestrate, "STAGING_BASE", mock_staging_dir.parent)
        start = time.time()
        result = orchestrate.load_staging_data("2026-04-02")
        elapsed = time.time() - start
        assert result is not None
        assert elapsed < self.STEP_BUDGETS["staging_load"], \
            f"Staging load took {elapsed:.3f}s, budget is {self.STEP_BUDGETS['staging_load']}s"

    def test_architect_init_performance(self):
        """Architect initialization should be fast."""
        start = time.time()
        architect = DreamArchitect(dream_date=date(2026, 4, 2))
        elapsed = time.time() - start
        assert elapsed < self.STEP_BUDGETS["architect_init"], \
            f"Architect init took {elapsed:.3f}s, budget is {self.STEP_BUDGETS['architect_init']}s"

    def test_config_validation_performance(self):
        """Config validation should be very fast."""
        architect = DreamArchitect(dream_date=date(2026, 4, 2))
        start = time.time()
        for _ in range(100):
            architect.validate_config(MOCK_DREAM_WORLD_CONFIG)
        elapsed = time.time() - start
        per_validation = elapsed / 100
        assert per_validation < self.STEP_BUDGETS["config_validation"], \
            f"Validation took {per_validation:.4f}s, budget is {self.STEP_BUDGETS['config_validation']}s"

    def test_bridge_health_performance(self):
        """Bridge health check should respond quickly."""
        from bridge.hermes_bridge import app

        with app.test_client() as client:
            start = time.time()
            resp = client.get("/health")
            elapsed = time.time() - start
            assert resp.status_code == 200
            assert elapsed < self.STEP_BUDGETS["bridge_health"], \
                f"Bridge health took {elapsed:.3f}s, budget is {self.STEP_BUDGETS['bridge_health']}s"

    def test_individuation_update_performance(self, mock_individuation_state):
        """Individuation state update should be fast."""
        state = json.loads(mock_individuation_state.read_text())
        dream_text = "Shadow confrontation at the mirror. Dialogue with the dark twin."

        start = time.time()
        update_after_dream(state, dream_text, MOCK_DREAM_WORLD_CONFIG)
        elapsed = time.time() - start
        assert elapsed < self.STEP_BUDGETS["individuation_update"], \
            f"Individuation update took {elapsed:.3f}s, budget is {self.STEP_BUDGETS['individuation_update']}s"

    def test_state_load_performance(self, mock_individuation_state):
        """State load should be fast."""
        start = time.time()
        state = load_state(mock_individuation_state)
        elapsed = time.time() - start
        assert state is not None
        assert elapsed < self.STEP_BUDGETS["state_load"], \
            f"State load took {elapsed:.3f}s, budget is {self.STEP_BUDGETS['state_load']}s"

    def test_full_pipeline_timing_report(self, mock_staging_dir, mock_individuation_state, monkeypatch):
        """Run all steps and report total pipeline time."""
        timings = {}

        # Step 1: Load staging
        start = time.time()
        monkeypatch.setattr(orchestrate, "STAGING_BASE", mock_staging_dir.parent)
        orchestrate.load_staging_data("2026-04-02")
        timings["staging_load"] = time.time() - start

        # Step 2: Init architect
        start = time.time()
        architect = DreamArchitect(dream_date=date(2026, 4, 2))
        timings["architect_init"] = time.time() - start

        # Step 3: Validate config
        start = time.time()
        errors = architect.validate_config(MOCK_DREAM_WORLD_CONFIG)
        timings["config_validation"] = time.time() - start

        # Step 4: Bridge health
        from bridge.hermes_bridge import app
        with app.test_client() as client:
            start = time.time()
            client.get("/health")
            timings["bridge_health"] = time.time() - start

        # Step 5: Individuation update
        state = json.loads(mock_individuation_state.read_text())
        start = time.time()
        update_after_dream(state, "shadow dialogue test", MOCK_DREAM_WORLD_CONFIG)
        timings["individuation_update"] = time.time() - start

        total = sum(timings.values())
        timings["TOTAL"] = total

        # Report
        print("\n--- Pipeline Performance Report ---")
        for step, duration in timings.items():
            budget = self.STEP_BUDGETS.get(step)
            status = ""
            if budget:
                status = " OK" if duration < budget else f" OVER BUDGET ({budget}s)"
            print(f"  {step}: {duration:.4f}s{status}")

        # Total should be under 5 seconds (without LLM calls)
        assert total < 5.0, f"Total pipeline time {total:.2f}s exceeds 5s budget"


# ---------------------------------------------------------------------------
# Test class: Data Integrity
# ---------------------------------------------------------------------------

class TestDataIntegrity:
    """Verify data flows correctly through the pipeline."""

    def test_staging_data_round_trip(self, mock_staging_dir):
        """Staging data should be readable after writing."""
        report = json.loads((mock_staging_dir / "consolidation_report.json").read_text())
        assert report["date"] == "2026-04-02"
        assert len(report["key_events"]) == 4

    def test_individuation_state_round_trip(self, mock_individuation_state):
        """Individuation state should survive load/save cycle."""
        state = load_state(mock_individuation_state)
        assert state["stage"] == "shadow_encounter"
        assert len(state["archetype_encounters"]) == 1

    def test_config_npc_locations_match(self):
        """NPC initial_locations should reference valid location names."""
        config = MOCK_DREAM_WORLD_CONFIG
        location_names = {loc["name"] for loc in config["locations"]}
        for npc in config["npcs"]:
            assert npc["initial_location"] in location_names, \
                f"NPC {npc['name']} references unknown location {npc['initial_location']}"

    def test_leeloo_initial_location_valid(self):
        """Leeloo's initial_location should be a valid location."""
        config = MOCK_DREAM_WORLD_CONFIG
        location_names = {loc["name"] for loc in config["locations"]}
        assert config["leeloo"]["initial_location"] in location_names

    def test_dream_log_format(self):
        """Dream log text should contain expected sections."""
        from architect.individuation import _extract_text
        text = _extract_text(MOCK_PREVIOUS_DREAM_LOG)
        assert "library" in text.lower() or "whisper" in text.lower()

    def test_bridge_session_management(self):
        """Bridge sessions should track tick count correctly."""
        from bridge.hermes_bridge import DreamSession
        session = DreamSession("TestAgent")
        assert session.tick_count == 0

        messages = session.add_perception("You see a forest.")
        assert session.tick_count == 1
        assert len(messages) == 2  # system + user

        session.add_response('{"action":"look","target":"forest","reason":"curious"}')
        messages2 = session.add_perception("The forest whispers.")
        assert session.tick_count == 2
        assert len(messages2) == 4  # system + user1 + assistant1 + user2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
