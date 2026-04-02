"""
Tests for individuation state management and dream series analysis.

Covers:
- State creation, save/load roundtrip
- update_after_dream with mock dream data
- Stage progression logic
- Series analysis with multiple mock dream logs
- Symbol tracking evolution
"""

import json
import tempfile
from pathlib import Path

import pytest

from .individuation import (
    _default_state,
    load_state,
    save_state,
    update_after_dream,
    get_stage_description,
    should_advance_stage,
    advance_stage,
    generate_monthly_synthesis,
    STAGES,
    STAGE_DESCRIPTIONS,
)
from .dream_series import (
    analyze_series,
    generate_report,
    SeriesAnalysis,
    _extract_date_from_filename,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_state_path(tmp_path):
    return tmp_path / "individuation_state.json"


@pytest.fixture
def fresh_state():
    return _default_state()


@pytest.fixture
def advanced_state():
    """A state that's been through several encounters."""
    state = _default_state()
    state["stage"] = "shadow_encounter"
    state["stage_progress"] = 0.5
    state["archetype_encounters"] = [
        {
            "archetype": "Shadow",
            "date": "2026-04-05",
            "npc_name": "Vesper",
            "dream_context": "Confronted in mirror room",
            "outcome": "fled",
            "emotional_intensity": 8,
            "notes": "First shadow encounter",
        },
        {
            "archetype": "Shadow",
            "date": "2026-04-08",
            "npc_name": "Vesper",
            "dream_context": "Met at the crossroads",
            "outcome": "dialogue",
            "emotional_intensity": 6,
            "notes": "",
        },
    ]
    state["shadow_integration"]["phase"] = "encounter"
    state["shadow_integration"]["confrontation_count"] = 2
    state["recurring_symbols"] = {
        "mirror": {
            "first_appeared": "2026-04-05",
            "appearances": 2,
            "last_seen": "2026-04-08",
            "status": "active",
            "evolution_notes": [],
            "amplifications": [],
        }
    }
    return state


@pytest.fixture
def mock_dream_logs_dir(tmp_path):
    """Create a directory with mock dream log files."""
    logs_dir = tmp_path / "dream-logs"
    logs_dir.mkdir()

    dreams = [
        ("dream-2026-04-02.md", """# Dream Log — 2026-04-02
The dreamer found herself in a dark mirror room. A shadow figure stood opposite, 
wearing her face but twisted. She felt anxious and afraid. The shadow spoke 
uncomfortable truths about her desire for control. She fled through a locked door
into a garden where a great tree stood, its roots glowing with fire."""),

        ("dream-2026-04-05.md", """# Dream Log — 2026-04-05
A return to the mirror room, but this time the shadow was waiting calmly.
They had a dialogue about suppressed anger and the masks she wears.
The shadow offered a key — she confronted her fear and took it.
Water began to rise. A wise elder appeared at the threshold."""),

        ("dream-2026-04-08.md", """# Dream Log — 2026-04-08
The labyrinth stretched endlessly. A trickster figure kept changing the walls.
She felt confused and lost. The shadow appeared again, this time as an ally.
Together they descended into darkness where fire illuminated ancient symbols.
A breakthrough — she realized the shadow was not her enemy but her honesty."""),

        ("dream-2026-04-12.md", """# Dream Log — 2026-04-12
A vast ocean under moonlight. She swam toward a distant light.
The shadow walked beside her on the water, peaceful now.
They spoke about transformation and acceptance. A divine child
appeared, holding a lantern. Joy and awe filled the dream.
She embraced the shadow and they merged — integrated at last."""),

        ("dream-2026-04-15.md", """# Dream Log — 2026-04-15
A dark forest. The same shadow figure. The same anxiety.
The same locked door. She felt fear again. The mirror appeared.
She fled once more. Nothing had changed. The shadow called after her."""),
    ]

    for filename, content in dreams:
        (logs_dir / filename).write_text(content)

    return logs_dir


MOCK_DREAM_TEXT = """
The dreamer entered a vast mirror hall. The Shadow stood at the center,
speaking truths she didn't want to hear. She felt deep anxiety but chose
to confront the figure. They had a dialogue about her fear of being
genuinely honest. A key appeared on the floor. Water rose around them.
She picked up the key and a door opened to a garden bathed in moonlight.
"""

MOCK_ARCHITECT_CONFIG = {
    "npcs": [
        {
            "name": "Vesper",
            "archetype": "Shadow",
            "personality_prompt": "Dark mirror",
        },
        {
            "name": "Lumen",
            "archetype": "Wise Old Man/Woman",
            "personality_prompt": "Ancient guide",
        },
    ],
    "world": {"name": "The Mirror Hall"},
}


# ===========================================================================
# Tests: State creation and persistence
# ===========================================================================

class TestStateCreation:
    def test_default_state_has_required_keys(self, fresh_state):
        required = [
            "version", "created", "last_updated", "stage", "stage_progress",
            "archetype_encounters", "recurring_symbols", "shadow_integration",
            "compensation_history", "dream_series_patterns", "monthly_synthesis",
        ]
        for key in required:
            assert key in fresh_state, f"Missing key: {key}"

    def test_default_stage_is_persona_dissolution(self, fresh_state):
        assert fresh_state["stage"] == "persona_dissolution"
        assert fresh_state["stage_progress"] == 0.0

    def test_default_shadow_integration(self, fresh_state):
        si = fresh_state["shadow_integration"]
        assert si["phase"] == "denial"
        assert si["confrontation_count"] == 0

    def test_save_load_roundtrip(self, fresh_state, tmp_state_path):
        fresh_state["stage"] = "shadow_encounter"
        fresh_state["stage_progress"] = 0.42
        save_state(fresh_state, tmp_state_path)

        loaded = load_state(tmp_state_path)
        assert loaded["stage"] == "shadow_encounter"
        assert loaded["stage_progress"] == 0.42

    def test_load_missing_file_returns_default(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        state = load_state(path)
        assert state["stage"] == "persona_dissolution"

    def test_load_corrupt_file_returns_default(self, tmp_path):
        path = tmp_path / "corrupt.json"
        path.write_text("not valid json{{{")
        state = load_state(path)
        assert state["stage"] == "persona_dissolution"

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "state.json"
        save_state(_default_state(), path)
        assert path.exists()

    def test_load_adds_missing_keys(self, tmp_path):
        """Forward-compat: old state files missing new keys get defaults."""
        path = tmp_path / "old_state.json"
        old = {"version": "0.9", "stage": "shadow_encounter"}
        path.write_text(json.dumps(old))
        loaded = load_state(path)
        assert loaded["stage"] == "shadow_encounter"
        assert "shadow_integration" in loaded
        assert "monthly_synthesis" in loaded


# ===========================================================================
# Tests: update_after_dream
# ===========================================================================

class TestUpdateAfterDream:
    def test_detects_shadow_archetype(self, fresh_state):
        updated = update_after_dream(fresh_state, MOCK_DREAM_TEXT)
        archetypes = [e["archetype"] for e in updated["archetype_encounters"]]
        assert "Shadow" in archetypes

    def test_detects_symbols(self, fresh_state):
        updated = update_after_dream(fresh_state, MOCK_DREAM_TEXT)
        assert "mirror" in updated["recurring_symbols"]
        assert "key" in updated["recurring_symbols"]
        assert "door" in updated["recurring_symbols"]
        assert "water" in updated["recurring_symbols"]

    def test_symbol_appearance_count(self, advanced_state):
        # Mirror already has 2 appearances
        updated = update_after_dream(advanced_state, MOCK_DREAM_TEXT)
        assert updated["recurring_symbols"]["mirror"]["appearances"] == 3

    def test_shadow_confrontation_count(self, fresh_state):
        updated = update_after_dream(fresh_state, MOCK_DREAM_TEXT)
        assert updated["shadow_integration"]["confrontation_count"] == 1

    def test_shadow_phase_advances(self, fresh_state):
        # Start in denial, dialogue should move to encounter
        updated = update_after_dream(fresh_state, MOCK_DREAM_TEXT)
        assert updated["shadow_integration"]["phase"] in ("encounter", "struggle")

    def test_records_compensation_with_config(self, fresh_state):
        updated = update_after_dream(fresh_state, MOCK_DREAM_TEXT, MOCK_ARCHITECT_CONFIG)
        assert len(updated["compensation_history"]) == 1
        assert updated["compensation_history"][0]["archetype_used"] == "Shadow"

    def test_npc_name_from_config(self, fresh_state):
        updated = update_after_dream(fresh_state, MOCK_DREAM_TEXT, MOCK_ARCHITECT_CONFIG)
        shadow_encounters = [
            e for e in updated["archetype_encounters"] if e["archetype"] == "Shadow"
        ]
        assert any(e["npc_name"] == "Vesper" for e in shadow_encounters)

    def test_updates_stage_progress(self, fresh_state):
        updated = update_after_dream(fresh_state, MOCK_DREAM_TEXT)
        assert updated["stage_progress"] > 0.0

    def test_dict_dream_log(self, fresh_state):
        dream_dict = {
            "narrative": "The shadow confronted her in the mirror room.",
            "events": ["She faced the shadow.", "A key appeared."],
        }
        updated = update_after_dream(fresh_state, dream_dict)
        archetypes = [e["archetype"] for e in updated["archetype_encounters"]]
        assert "Shadow" in archetypes


# ===========================================================================
# Tests: Stage progression
# ===========================================================================

class TestStageProgression:
    def test_all_stages_have_descriptions(self):
        for stage in STAGES:
            desc = get_stage_description(stage)
            assert len(desc) > 20

    def test_unknown_stage_returns_message(self):
        desc = get_stage_description("unknown_stage")
        assert "Unknown" in desc

    def test_should_not_advance_low_progress(self, fresh_state):
        fresh_state["stage_progress"] = 0.3
        assert not should_advance_stage(fresh_state)

    def test_should_not_advance_few_encounters(self, fresh_state):
        fresh_state["stage_progress"] = 0.9
        # No encounters yet
        assert not should_advance_stage(fresh_state)

    def test_should_advance_when_ready(self):
        state = _default_state()
        state["stage"] = "persona_dissolution"
        state["stage_progress"] = 0.85
        # Add enough relevant encounters
        for i in range(4):
            state["archetype_encounters"].append({
                "archetype": "Shadow",
                "date": f"2026-04-{i+5:02d}",
                "npc_name": "Vesper",
                "dream_context": "test",
                "outcome": "confronted",
                "emotional_intensity": 7,
                "notes": "",
            })
        assert should_advance_stage(state)

    def test_advance_stage_moves_forward(self, fresh_state):
        fresh_state["stage_progress"] = 0.9
        advanced = advance_stage(fresh_state)
        assert advanced["stage"] == "shadow_encounter"
        assert advanced["stage_progress"] == 0.0

    def test_cannot_advance_past_final_stage(self):
        state = _default_state()
        state["stage"] = "self_realization"
        assert not should_advance_stage(state)
        advanced = advance_stage(state)
        assert advanced["stage"] == "self_realization"

    def test_shadow_gate_requires_phase(self):
        """Shadow encounter stage requires shadow phase to be at struggle+."""
        state = _default_state()
        state["stage"] = "shadow_encounter"
        state["stage_progress"] = 0.9
        state["shadow_integration"]["phase"] = "encounter"  # not enough
        for i in range(4):
            state["archetype_encounters"].append({
                "archetype": "Shadow",
                "date": f"2026-04-{i+5:02d}",
                "npc_name": "V",
                "dream_context": "test",
                "outcome": "confronted",
                "emotional_intensity": 7,
                "notes": "",
            })
        assert not should_advance_stage(state)

        state["shadow_integration"]["phase"] = "struggle"
        assert should_advance_stage(state)


# ===========================================================================
# Tests: Monthly synthesis
# ===========================================================================

class TestMonthlySynthesis:
    def test_generates_synthesis(self, advanced_state):
        logs = [MOCK_DREAM_TEXT, "Another dream with the shadow in a garden."]
        synthesis = generate_monthly_synthesis(advanced_state, logs)
        assert "2 dreams" in synthesis
        assert "shadow_encounter" in synthesis

    def test_includes_archetype_counts(self, advanced_state):
        synthesis = generate_monthly_synthesis(advanced_state, [MOCK_DREAM_TEXT])
        assert "Shadow" in synthesis

    def test_includes_shadow_phase(self, advanced_state):
        synthesis = generate_monthly_synthesis(advanced_state, [])
        assert "encounter" in synthesis


# ===========================================================================
# Tests: Dream series analysis
# ===========================================================================

class TestDreamSeriesAnalysis:
    def test_analyze_empty_dir(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        analysis = analyze_series(empty_dir)
        assert analysis.total_dreams == 0

    def test_analyze_mock_logs(self, mock_dream_logs_dir):
        analysis = analyze_series(mock_dream_logs_dir)
        assert analysis.total_dreams == 5
        assert analysis.first_dream == "2026-04-02"
        assert analysis.last_dream == "2026-04-15"

    def test_theme_frequency(self, mock_dream_logs_dir):
        analysis = analyze_series(mock_dream_logs_dir)
        assert "darkness" in analysis.theme_frequency
        assert analysis.theme_frequency["darkness"] >= 2

    def test_symbol_evolution_tracking(self, mock_dream_logs_dir):
        analysis = analyze_series(mock_dream_logs_dir)
        assert "mirror" in analysis.symbol_evolution
        assert len(analysis.symbol_evolution["mirror"]) >= 2

    def test_archetype_progression(self, mock_dream_logs_dir):
        analysis = analyze_series(mock_dream_logs_dir)
        assert "Shadow" in analysis.archetype_progression
        assert len(analysis.archetype_progression["Shadow"]) >= 3

    def test_emotional_arc(self, mock_dream_logs_dir):
        analysis = analyze_series(mock_dream_logs_dir)
        assert len(analysis.emotional_arc) >= 3

    def test_breakthrough_detection(self, mock_dream_logs_dir):
        analysis = analyze_series(mock_dream_logs_dir)
        # Dream 4 (2026-04-12) has breakthrough language + high emotion
        breakthrough_dates = [d for d, _ in analysis.breakthrough_moments]
        assert "2026-04-12" in breakthrough_dates

    def test_date_extraction(self):
        assert _extract_date_from_filename("dream-2026-04-02.md") == "2026-04-02"
        assert _extract_date_from_filename("random.md") == "unknown"


# ===========================================================================
# Tests: Report generation
# ===========================================================================

class TestReportGeneration:
    def test_generate_report_structure(self, mock_dream_logs_dir):
        analysis = analyze_series(mock_dream_logs_dir)
        report = generate_report(analysis)

        assert "# Dream Series Analysis Report" in report
        assert "## Theme Frequency" in report
        assert "## Symbol Evolution" in report
        assert "## Archetype Progression" in report
        assert "## Emotional Arc" in report
        assert "## Recommendations for the Architect" in report

    def test_report_includes_dream_count(self, mock_dream_logs_dir):
        analysis = analyze_series(mock_dream_logs_dir)
        report = generate_report(analysis)
        assert "5" in report

    def test_empty_analysis_report(self):
        analysis = SeriesAnalysis()
        report = generate_report(analysis)
        assert "0" in report
        assert "No themes detected" in report


# ===========================================================================
# Tests: Symbol evolution across dreams
# ===========================================================================

class TestSymbolEvolution:
    def test_symbol_first_appearance(self, fresh_state):
        updated = update_after_dream(fresh_state, "A locked door in the dark.")
        assert "door" in updated["recurring_symbols"]
        assert updated["recurring_symbols"]["door"]["appearances"] == 1

    def test_symbol_count_increments(self, fresh_state):
        updated = update_after_dream(fresh_state, "A door appeared.")
        updated = update_after_dream(updated, "The same door, now open.")
        assert updated["recurring_symbols"]["door"]["appearances"] == 2

    def test_multiple_symbols_tracked(self, fresh_state):
        text = "A mirror reflected the moonlight through the window onto a key."
        updated = update_after_dream(fresh_state, text)
        assert "mirror" in updated["recurring_symbols"]
        assert "key" in updated["recurring_symbols"]
        assert "moon" in updated["recurring_symbols"]
        assert "window" in updated["recurring_symbols"]

    def test_series_symbol_evolution(self, mock_dream_logs_dir):
        """Verify that symbol_evolution tracks across multiple dream files."""
        analysis = analyze_series(mock_dream_logs_dir)
        # 'shadow' appears in multiple dreams
        assert "shadow" in analysis.symbol_evolution
        evolutions = analysis.symbol_evolution["shadow"]
        dates = [d for d, _, _ in evolutions]
        # Should be chronologically ordered
        assert dates == sorted(dates)
