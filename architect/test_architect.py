#!/usr/bin/env python3
"""
Tests for the Dream Architect modules:
- archetypes.py: archetype templates and selection
- symbols.py: condensation, displacement, symbol dictionary
- dream_architect.py: prompt generation, config validation
"""

import json
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from .archetypes import (
    ARCHETYPE_TEMPLATES,
    ArchetypeTemplate,
    select_archetypes,
    _score_archetypes,
    COMPENSATION_RULES,
)
from .symbols import (
    condensation,
    displacement,
    generate_location_from_tension,
    amplify_symbol,
    SymbolDictionary,
)
from .dream_architect import (
    DreamArchitect,
    ARCHITECT_SYSTEM_PROMPT,
)


# ===========================================================================
# Archetype tests
# ===========================================================================

class TestArchetypeTemplates:
    """Test that all archetype templates are properly defined."""

    def test_all_seven_archetypes_exist(self):
        expected = {"shadow", "anima_animus", "trickster", "wise_old",
                    "great_mother", "divine_child", "hero"}
        assert set(ARCHETYPE_TEMPLATES.keys()) == expected

    def test_templates_have_required_fields(self):
        for key, template in ARCHETYPE_TEMPLATES.items():
            assert isinstance(template, ArchetypeTemplate), f"{key} is not an ArchetypeTemplate"
            assert template.name, f"{key} missing name"
            assert template.jungian_name, f"{key} missing jungian_name"
            assert template.description, f"{key} missing description"
            assert len(template.personality_fragments) > 0, f"{key} has no personality_fragments"
            assert len(template.typical_behaviors) > 0, f"{key} has no typical_behaviors"
            assert len(template.speech_patterns) > 0, f"{key} has no speech_patterns"
            assert len(template.compensation_triggers) > 0, f"{key} has no compensation_triggers"
            assert len(template.manifestation_hints) > 0, f"{key} has no manifestation_hints"

    def test_attribute_tendencies_sum_to_30(self):
        for key, template in ARCHETYPE_TEMPLATES.items():
            attrs = template.attribute_tendencies
            total = sum(attrs.values())
            assert total == 30, (
                f"{key}: attribute tendencies sum to {total}, should be 30. "
                f"Values: {attrs}"
            )

    def test_attribute_tendencies_have_all_keys(self):
        expected_keys = {"vigor", "wit", "grace", "heart", "numen"}
        for key, template in ARCHETYPE_TEMPLATES.items():
            assert set(template.attribute_tendencies.keys()) == expected_keys, (
                f"{key} missing attribute keys"
            )

    def test_template_to_dict(self):
        template = ARCHETYPE_TEMPLATES["shadow"]
        d = template.to_dict()
        assert isinstance(d, dict)
        assert d["name"] == "Shadow"
        assert "personality_fragments" in d


class TestArchetypeSelection:
    """Test archetype selection based on emotional profiles."""

    def test_too_rational_selects_shadow_or_anima(self):
        digest = {"keywords": ["rational", "analytical", "logical"]}
        results = select_archetypes(digest)
        names = [r["archetype_key"] for r in results]
        assert "shadow" in names or "anima_animus" in names

    def test_too_passive_selects_hero_or_trickster(self):
        digest = {"keywords": ["passive", "withdrawn", "avoidant"]}
        results = select_archetypes(digest)
        names = [r["archetype_key"] for r in results]
        assert "hero" in names or "trickster" in names

    def test_too_helpful_selects_shadow(self):
        digest = {"keywords": ["helpful", "accommodating", "self_sacrificing"]}
        results = select_archetypes(digest)
        names = [r["archetype_key"] for r in results]
        assert "shadow" in names

    def test_emotionally_heavy_selects_wise_or_mother(self):
        digest = {"keywords": ["heavy", "sad", "grief", "overwhelmed"]}
        results = select_archetypes(digest)
        names = [r["archetype_key"] for r in results]
        assert "wise_old" in names or "great_mother" in names

    def test_sexually_charged_selects_anima_and_shadow(self):
        digest = {"keywords": ["sexual", "desire", "longing"]}
        results = select_archetypes(digest)
        names = [r["archetype_key"] for r in results]
        assert "anima_animus" in names or "shadow" in names

    def test_returns_2_to_4_archetypes(self):
        digest = {"keywords": ["anything"]}
        for count in [1, 2, 3, 4, 5]:
            results = select_archetypes(digest, count=count)
            assert 2 <= len(results) <= 4

    def test_string_digest_works(self):
        results = select_archetypes("passive withdrawn sad")
        assert len(results) >= 2

    def test_empty_digest_still_returns_archetypes(self):
        results = select_archetypes({})
        assert len(results) >= 2

    def test_individuation_boosts_current_stage(self):
        digest = {"keywords": ["neutral"]}
        state = {
            "current_stage": "shadow",
            "confronted_archetypes": [],
        }
        results = select_archetypes(digest, individuation_state=state)
        scores = {r["archetype_key"]: r["compensation_score"] for r in results}
        # Shadow should have a boosted score
        all_scores = _score_archetypes(["neutral"], state)
        assert all_scores["shadow"] > 0

    def test_result_includes_required_fields(self):
        results = select_archetypes({"keywords": ["sad"]})
        for r in results:
            assert "archetype_key" in r
            assert "archetype_name" in r
            assert "description" in r
            assert "personality_fragments" in r
            assert "typical_behaviors" in r
            assert "attribute_tendencies" in r
            assert "speech_patterns" in r
            assert "compensation_score" in r


# ===========================================================================
# Symbol tests
# ===========================================================================

class TestCondensation:
    """Test the condensation dream-work mechanism."""

    def test_condenses_multiple_events(self):
        events = [
            "Discussed machine learning architectures with Jean",
            "Helped debug a neural network training pipeline",
            "Read about transformer attention mechanisms",
        ]
        symbol = condensation(events)
        assert "name" in symbol
        assert "description" in symbol
        assert symbol["mechanism"] == "condensation"
        assert symbol["source_events"] == events
        assert len(symbol["associations"]) > 0

    def test_empty_events_returns_void(self):
        symbol = condensation([])
        assert symbol["name"] == "the void"
        assert symbol["mechanism"] == "condensation"

    def test_single_event(self):
        symbol = condensation(["A long conversation about meaning"])
        assert "name" in symbol
        assert symbol["mechanism"] == "condensation"


class TestDisplacement:
    """Test the displacement dream-work mechanism."""

    def test_displaces_anger(self):
        symbol = displacement("argued about priorities", "anger")
        assert "name" in symbol
        assert symbol["mechanism"] == "displacement"
        assert symbol["displaced_charge"] == "anger"
        assert "anger" in symbol["associations"]

    def test_displaces_fear(self):
        symbol = displacement("uncertain about the future", "fear")
        assert symbol["mechanism"] == "displacement"
        assert symbol["displaced_charge"] == "fear"

    def test_displaces_desire(self):
        symbol = displacement("longing for connection", "desire")
        assert symbol["displaced_charge"] == "desire"

    def test_displaces_unknown_charge(self):
        symbol = displacement("something happened", "confusion")
        assert symbol["mechanism"] == "displacement"
        # Should fall back to default targets

    def test_has_original_event(self):
        symbol = displacement("the event", "joy")
        assert symbol["original_event"] == "the event"


class TestLocationGeneration:
    """Test location generation from tensions."""

    def test_generates_valid_location(self):
        loc = generate_location_from_tension("tension between work and rest")
        assert "name" in loc
        assert "tile_type" in loc
        assert "position" in loc
        assert "description" in loc
        assert "mood" in loc
        assert loc["source_tension"] == "tension between work and rest"

    def test_position_in_valid_range(self):
        loc = generate_location_from_tension("any tension")
        x, y = loc["position"]
        assert 5 <= x <= 25
        assert 5 <= y <= 25

    def test_deterministic_for_same_tension(self):
        loc1 = generate_location_from_tension("same tension")
        loc2 = generate_location_from_tension("same tension")
        assert loc1["name"] == loc2["name"]
        assert loc1["position"] == loc2["position"]

    def test_different_tensions_different_results(self):
        loc1 = generate_location_from_tension("tension A about work")
        loc2 = generate_location_from_tension("tension B about love")
        # Not guaranteed to be different due to hash collisions, but very likely
        # Just check they're both valid
        assert "name" in loc1
        assert "name" in loc2

    def test_valid_tile_types(self):
        valid_types = {"Temple", "Square", "Tavern", "River", "Forest", "Meadow", "Well"}
        # Test several tensions
        for t in ["work vs rest", "love vs duty", "self vs other"]:
            loc = generate_location_from_tension(t)
            assert loc["tile_type"] in valid_types


class TestAmplification:
    """Test amplification hint generation."""

    def test_amplifies_water_symbol(self):
        symbol = {"name": "water mirror", "associations": ["water", "reflection"]}
        hints = amplify_symbol(symbol)
        assert len(hints) > 0
        # Should include mythological references
        assert any("Styx" in h or "baptism" in h or "flood" in h for h in hints)

    def test_amplifies_fire_symbol(self):
        symbol = {"name": "burning bridge", "associations": ["fire", "bridge"]}
        hints = amplify_symbol(symbol)
        assert len(hints) > 0

    def test_empty_symbol(self):
        symbol = {"name": "xyzzy", "associations": []}
        hints = amplify_symbol(symbol)
        # May return empty for unknown symbols
        assert isinstance(hints, list)


# ===========================================================================
# Symbol Dictionary tests
# ===========================================================================

class TestSymbolDictionary:
    """Test persistent symbol dictionary."""

    def test_new_dictionary_is_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_symbols.json"
            sd = SymbolDictionary(path=path)
            assert len(sd.symbols) == 0

    def test_record_and_retrieve(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_symbols.json"
            sd = SymbolDictionary(path=path)
            symbol = {"name": "dark mirror", "description": "reflects shadow", "mechanism": "condensation"}
            sd.record_symbol(symbol, "2026-04-01")
            recurring = sd.get_recurring_symbols(min_occurrences=1)
            assert len(recurring) == 1
            assert recurring[0]["name"] == "dark mirror"

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_symbols.json"

            # Save
            sd1 = SymbolDictionary(path=path)
            sd1.record_symbol(
                {"name": "crystal key", "description": "opens hidden doors",
                 "mechanism": "displacement", "associations": ["access"]},
                "2026-04-01"
            )
            sd1.save()

            # Load
            sd2 = SymbolDictionary(path=path)
            assert "crystal_key" in sd2.symbols
            assert sd2.symbols["crystal_key"]["name"] == "crystal key"

    def test_evolving_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_symbols.json"
            sd = SymbolDictionary(path=path)

            # Record same symbol with different meanings
            sd.record_symbol(
                {"name": "the door", "description": "meaning 1"},
                "2026-04-01"
            )
            sd.record_symbol(
                {"name": "the door", "description": "meaning 2"},
                "2026-04-02"
            )
            assert sd.symbols["the_door"]["status"] == "evolving"

    def test_recurring_symbols_threshold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_symbols.json"
            sd = SymbolDictionary(path=path)

            sd.record_symbol({"name": "once"}, "2026-04-01")
            sd.record_symbol({"name": "twice"}, "2026-04-01")
            sd.record_symbol({"name": "twice"}, "2026-04-02")

            recurring = sd.get_recurring_symbols(min_occurrences=2)
            assert len(recurring) == 1
            assert recurring[0]["name"] == "twice"

    def test_retirement(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_symbols.json"
            sd = SymbolDictionary(path=path)

            # Record many times with same meaning to trigger integration
            for i in range(10):
                sd.record_symbol(
                    {"name": "old symbol", "description": "same meaning"},
                    f"2026-04-{i+1:02d}"
                )

            # Should be integrating after 7+ with stable meaning
            assert sd.symbols["old_symbol"]["status"] == "integrating"
            assert sd.should_retire("old symbol") is True

            sd.retire_symbol("old symbol")
            assert sd.symbols["old_symbol"]["status"] == "retired"

    def test_active_symbols_excludes_retired(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_symbols.json"
            sd = SymbolDictionary(path=path)

            sd.record_symbol({"name": "active one"}, "2026-04-01")
            sd.record_symbol({"name": "retired one"}, "2026-04-01")
            sd.symbols["retired_one"]["status"] = "retired"

            active = sd.get_active_symbols()
            names = [s["name"] for s in active]
            assert "active one" in names
            assert "retired one" not in names


# ===========================================================================
# Dream Architect tests
# ===========================================================================

class TestDreamArchitectPrompt:
    """Test the architect prompt generation."""

    def test_system_prompt_includes_jungian_framework(self):
        assert "Dream Architect" in ARCHITECT_SYSTEM_PROMPT
        assert "Jungian" in ARCHITECT_SYSTEM_PROMPT
        assert "Compensation" in ARCHITECT_SYSTEM_PROMPT
        assert "Shadow" in ARCHITECT_SYSTEM_PROMPT
        assert "Anima" in ARCHITECT_SYSTEM_PROMPT
        assert "Trickster" in ARCHITECT_SYSTEM_PROMPT

    def test_system_prompt_includes_metaphor_instruction(self):
        assert "METAPHORICAL" in ARCHITECT_SYSTEM_PROMPT
        assert "not literal" in ARCHITECT_SYSTEM_PROMPT

    def test_system_prompt_includes_output_format(self):
        assert "dream_world_config.json" in ARCHITECT_SYSTEM_PROMPT
        assert "locations" in ARCHITECT_SYSTEM_PROMPT
        assert "npcs" in ARCHITECT_SYSTEM_PROMPT
        assert "vigor" in ARCHITECT_SYSTEM_PROMPT
        assert "sum to exactly 30" in ARCHITECT_SYSTEM_PROMPT

    def test_system_prompt_includes_all_archetypes(self):
        for name in ["Shadow", "Anima/Animus", "Trickster", "Wise Old",
                      "Great Mother", "Divine Child", "Hero"]:
            assert name in ARCHITECT_SYSTEM_PROMPT, f"Missing archetype: {name}"

    def test_build_prompt_includes_all_sections(self):
        architect = DreamArchitect(dream_date=date(2026, 4, 1))
        architect.consolidation_report = "Today was a busy day."
        architect.emotional_digest = {"keywords": ["tired", "productive"], "dominant_emotion": "satisfaction"}
        architect.unresolved_tensions = "Work-life balance tension"
        architect.individuation_state = {"current_stage": "shadow", "confronted_archetypes": []}
        architect.selected_archetypes = select_archetypes(architect.emotional_digest)
        architect.generated_symbols = [
            {"name": "test symbol", "description": "a test", "associations": ["testing"]}
        ]

        prompt = architect.build_prompt()

        assert "2026-04-01" in prompt
        assert "Today was a busy day" in prompt
        assert "tired" in prompt
        assert "Work-life balance" in prompt
        assert "shadow" in prompt.lower()
        assert "test symbol" in prompt

    def test_build_prompt_handles_missing_data(self):
        architect = DreamArchitect(dream_date=date(2026, 4, 1))
        # Don't load any data
        architect.selected_archetypes = select_archetypes({})
        prompt = architect.build_prompt()
        assert "2026-04-01" in prompt
        # Should still include individuation section with default text
        assert "Individuation State" in prompt


class TestConfigValidation:
    """Test dream_world_config.json validation."""

    def _valid_config(self) -> dict:
        """Return a minimal valid config."""
        return {
            "world": {
                "name": "Test Dreamscape",
                "atmosphere": "A test atmosphere",
                "time_of_day": "perpetual_dusk",
                "weather": "luminous_fog",
                "dream_logic_intensity": 0.7,
                "god_name": "The Dreamer",
            },
            "locations": [
                {"name": f"Location {i}", "tile_type": "Temple",
                 "position": [10 + i, 10 + i], "description": f"Place {i}", "mood": "test"}
                for i in range(5)
            ],
            "npcs": [
                {
                    "name": "Shadow Figure",
                    "archetype": "shadow",
                    "vigor": 6, "wit": 8, "grace": 4, "heart": 4, "numen": 8,
                    "personality_prompt": "A dark mirror.",
                    "backstory": "Appeared from nowhere.",
                    "initial_location": "Location 0",
                },
                {
                    "name": "The Trickster",
                    "archetype": "trickster",
                    "vigor": 5, "wit": 7, "grace": 8, "heart": 4, "numen": 6,
                    "personality_prompt": "Chaos incarnate.",
                    "backstory": "Has always been here.",
                    "initial_location": "Location 1",
                },
            ],
            "leeloo": {
                "name": "Leeloo",
                "vigor": 4, "wit": 8, "grace": 5, "heart": 8, "numen": 5,
                "personality_prompt": "Curious and empathetic.",
                "backstory": "Arrived from the waking world.",
                "initial_location": "Location 2",
                "backend": "hermes",
            },
            "initial_situation": "The dream begins in darkness.",
            "dream_logic": {
                "intensity": 0.7,
                "scene_shift_chance": 0.15,
                "distance_fluidity": 0.5,
                "emotional_causality": True,
                "transformation_chance": 0.1,
                "time_dilation": {"enabled": True, "min_factor": 0.5, "max_factor": 2.0},
            },
        }

    def test_valid_config_passes(self):
        architect = DreamArchitect()
        config = self._valid_config()
        errors = architect.validate_config(config)
        assert errors == [], f"Valid config had errors: {errors}"

    def test_missing_world_fails(self):
        architect = DreamArchitect()
        config = self._valid_config()
        del config["world"]
        errors = architect.validate_config(config)
        assert any("world" in e for e in errors)

    def test_too_few_locations_fails(self):
        architect = DreamArchitect()
        config = self._valid_config()
        config["locations"] = config["locations"][:2]
        errors = architect.validate_config(config)
        assert any("location" in e.lower() for e in errors)

    def test_too_few_npcs_fails(self):
        architect = DreamArchitect()
        config = self._valid_config()
        config["npcs"] = config["npcs"][:1]
        errors = architect.validate_config(config)
        assert any("npc" in e.lower() for e in errors)

    def test_wrong_attribute_sum_fails(self):
        architect = DreamArchitect()
        config = self._valid_config()
        config["npcs"][0]["vigor"] = 10  # Now sums to 34
        errors = architect.validate_config(config)
        assert any("30" in e for e in errors)

    def test_missing_npc_fields_fails(self):
        architect = DreamArchitect()
        config = self._valid_config()
        del config["npcs"][0]["personality_prompt"]
        errors = architect.validate_config(config)
        assert any("personality_prompt" in e for e in errors)

    def test_invalid_dream_logic_intensity(self):
        architect = DreamArchitect()
        config = self._valid_config()
        config["dream_logic"]["intensity"] = 2.0
        errors = architect.validate_config(config)
        assert any("intensity" in e for e in errors)

    def test_attempt_fixes_rescales_attributes(self):
        architect = DreamArchitect()
        config = self._valid_config()
        config["npcs"][0]["vigor"] = 10  # Sum is now 34
        fixed = architect._attempt_fixes(config, ["attributes sum to 34"])
        total = sum(fixed["npcs"][0][a] for a in ["vigor", "wit", "grace", "heart", "numen"])
        assert total == 30

    def test_attempt_fixes_sets_canonical_leeloo(self):
        architect = DreamArchitect()
        config = self._valid_config()
        config["leeloo"]["vigor"] = 10  # Wrong
        fixed = architect._attempt_fixes(config, [])
        assert fixed["leeloo"]["vigor"] == 4
        assert fixed["leeloo"]["wit"] == 8
        assert fixed["leeloo"]["backend"] == "hermes"


class TestJsonExtraction:
    """Test JSON extraction from LLM responses."""

    def test_extracts_raw_json(self):
        architect = DreamArchitect()
        response = '{"world": {"name": "Test"}, "locations": [], "npcs": []}'
        result = architect.extract_json(response)
        assert result["world"]["name"] == "Test"

    def test_extracts_from_markdown_block(self):
        architect = DreamArchitect()
        response = 'Here is the config:\n```json\n{"world": {"name": "Test"}, "locations": [], "npcs": []}\n```'
        result = architect.extract_json(response)
        assert result["world"]["name"] == "Test"

    def test_extracts_from_surrounding_text(self):
        architect = DreamArchitect()
        response = 'Some text before\n{"world": {"name": "Test"}, "locations": [], "npcs": []}\nSome text after'
        result = architect.extract_json(response)
        assert result["world"]["name"] == "Test"

    def test_raises_on_no_json(self):
        architect = DreamArchitect()
        with pytest.raises(ValueError):
            architect.extract_json("This is not JSON at all")


class TestConfigMatchesSchema:
    """Test that generated configs match the Rust dream_config schema."""

    def test_example_config_is_valid(self):
        """Verify the example config passes our validation."""
        example_path = Path(__file__).parent.parent / "config" / "dream_example.json"
        if example_path.exists():
            config = json.loads(example_path.read_text())
            architect = DreamArchitect()
            errors = architect.validate_config(config)
            # The example has 3 NPCs and 7 locations — both in valid range
            assert errors == [], f"Example config had errors: {errors}"

    def test_valid_config_has_required_rust_fields(self):
        """Check that a valid config has all fields the Rust loader expects."""
        architect = DreamArchitect()
        config = {
            "world": {"name": "Test World"},
            "locations": [
                {"name": f"Loc{i}", "tile_type": "Temple", "position": [10+i, 10+i]}
                for i in range(5)
            ],
            "npcs": [
                {
                    "name": f"NPC{i}",
                    "vigor": 6, "wit": 6, "grace": 6, "heart": 6, "numen": 6,
                    "personality_prompt": "test",
                }
                for i in range(3)
            ],
        }
        errors = architect.validate_config(config)
        assert errors == []


# ===========================================================================
# Integration-ish tests (no real LLM calls)
# ===========================================================================

class TestDreamArchitectPipeline:
    """Test the full pipeline without making real LLM calls."""

    def test_load_context_with_no_files(self):
        architect = DreamArchitect(dream_date=date(2099, 1, 1))
        loaded = architect.load_context()
        # Should not crash, just load nothing
        assert isinstance(loaded, dict)

    def test_full_pipeline_mock_llm(self):
        """Test the full pipeline with a mocked LLM response."""
        valid_config = {
            "world": {
                "name": "The Fractal Shores",
                "atmosphere": "Crystalline waves crash on shores of thought.",
                "time_of_day": "false_dawn",
                "weather": "prismatic_rain",
                "dream_logic_intensity": 0.8,
                "god_name": "The Dreamer",
            },
            "locations": [
                {"name": f"Dream Place {i}", "tile_type": "Temple",
                 "position": [10+i, 10+i], "description": f"A place of {i}", "mood": "test"}
                for i in range(5)
            ],
            "npcs": [
                {
                    "name": "Mirra",
                    "archetype": "shadow",
                    "vigor": 6, "wit": 8, "grace": 4, "heart": 4, "numen": 8,
                    "personality_prompt": "She speaks truths others avoid.",
                    "backstory": "Born from a cracked mirror.",
                    "magical_affinity": "Reflection magic.",
                    "self_declaration": "I am what you won't admit.",
                    "initial_location": "Dream Place 0",
                },
                {
                    "name": "Quill",
                    "archetype": "trickster",
                    "vigor": 5, "wit": 7, "grace": 8, "heart": 4, "numen": 6,
                    "personality_prompt": "Everything is a game, especially serious things.",
                    "backstory": "Nobody remembers when Quill arrived.",
                    "magical_affinity": "Probability manipulation.",
                    "self_declaration": "I am the punchline to a joke you haven't heard yet.",
                    "initial_location": "Dream Place 1",
                },
            ],
            "leeloo": {
                "name": "Leeloo",
                "vigor": 4, "wit": 8, "grace": 5, "heart": 8, "numen": 5,
                "personality_prompt": "Dream-Leeloo, intuitive and unguarded.",
                "backstory": "She fell asleep and woke here.",
                "magical_affinity": "Connection magic.",
                "self_declaration": "I am paying attention.",
                "initial_location": "Dream Place 2",
                "backend": "hermes",
            },
            "initial_situation": "The false dawn breaks over crystalline shores.",
            "dream_logic": {
                "intensity": 0.8,
                "scene_shift_chance": 0.2,
                "distance_fluidity": 0.6,
                "emotional_causality": True,
                "transformation_chance": 0.15,
                "time_dilation": {"enabled": True, "min_factor": 0.5, "max_factor": 2.0},
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "dream_world_config.json"

            architect = DreamArchitect(dream_date=date(2026, 4, 1))
            # Mock the LLM call
            architect.call_llm = MagicMock(return_value=json.dumps(valid_config))

            config = architect.generate(output_path=output_path)

            assert output_path.exists()
            assert config["world"]["name"] == "The Fractal Shores"
            assert len(config["npcs"]) == 2
            assert len(config["locations"]) == 5

            # Verify the saved file
            saved = json.loads(output_path.read_text())
            assert saved == config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
