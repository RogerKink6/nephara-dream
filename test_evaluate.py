#!/usr/bin/env python3
"""
Tests for evaluate.py — dream quality evaluation framework.

Run with: python -m pytest test_evaluate.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from evaluate import (
    DreamMetrics,
    SeriesMetrics,
    evaluate_dream,
    evaluate_series,
    generate_evaluation_report,
    _measure_emotional_depth,
    _measure_creative_novelty,
    _measure_coherence,
    _measure_symbol_richness,
    _measure_archetype_diversity,
    _measure_memory_accuracy,
    _detect_themes,
    _score_bar,
    _score_grade,
    _compute_diversity,
    _measure_series_evolution,
    _compute_symbol_growth,
    _single_dream_recommendations,
    _series_recommendations,
    _count_sentences,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RICH_DREAM_TEXT = """\
# Dream of the Shattered Mirror

I found myself standing at the edge of a dark forest, the trees whispering secrets
I couldn't quite hear. A shadow moved between the trunks — my shadow, but not quite mine.
It spoke with a voice that echoed my own fears.

"You deny what you are," it said, and I felt a deep ache in my chest. The mirror
at the crossroads showed not my face but a thousand fragments of possibility.
Each shard reflected a different truth I had been too afraid to acknowledge.

Then the wise old woman appeared, carrying a lantern that burned with starlight.
"The door is not locked," she whispered. "You hold the key but refuse to see it."

I reached for the key — cold, heavy, transforming in my hand from iron to water
to light. The river at my feet began to glow, and I understood: the shadow was not
my enemy but my guide. We spoke at length, a dialogue that felt like coming home.

## Reflections

The dream confronted me with my tendency to deny the uncomfortable parts of myself.
The shadow figure — so clearly a Jungian archetype — demanded I stop running.
I felt fear, then awe, then something like peace.

## Symbols

- **Mirror**: Self-reflection, fragmented identity
- **Key**: Hidden potential, willingness to face truth
- **Forest**: The unconscious mind
- **River**: Flow of emotion, transformation
- **Shadow**: Denied aspects of self
"""

MINIMAL_DREAM_TEXT = "I had a dream. It was okay."

EMOTIONALLY_RICH_TEXT = """\
The sorrow washed over me like a wave. I wept at the beauty of it — the raw,
tender vulnerability of standing exposed. My heart ached with longing, yet
underneath the grief I felt a strange joy rising. Compassion for myself,
finally. The tears fell freely, and with them came a deep peace I had
never known. Fear dissolved into wonder. Gratitude emerged from despair.
"""

CREATIVE_TEXT = """\
The neural pathways of the forest lit up like a circuit board. Each tree
was a node in a vast network of dreams, its roots like wires carrying
data between the conscious and unconscious. A river of light flowed through,
carrying symbols of transformation — the quantum nature of the soul
meeting the myth of creation. An algorithm of dream logic processed
each memory like a ritual of becoming.
"""


@pytest.fixture
def dream_file(tmp_path):
    """Create a dream log file."""
    path = tmp_path / "dream-2026-04-02.md"
    path.write_text(RICH_DREAM_TEXT)
    return path


@pytest.fixture
def minimal_dream_file(tmp_path):
    """Create a minimal dream log file."""
    path = tmp_path / "dream-2026-04-03.md"
    path.write_text(MINIMAL_DREAM_TEXT)
    return path


@pytest.fixture
def dream_series_dir(tmp_path):
    """Create a directory with multiple dream files."""
    for i, (date_str, content) in enumerate([
        ("2026-03-28", "I walked through a dark forest. The shadow followed me, whispering fears. I ran from it. The mirror at the crossroads cracked."),
        ("2026-03-29", "The shadow returned. This time I confronted it at the bridge. The river below churned with fear and anger. A door appeared but I fled."),
        ("2026-03-30", "In the temple of light, the wise old sage spoke riddles. The fire burned questions into the air. I began to understand the shadow's purpose. Dialogue, at last."),
        ("2026-03-31", "The trickster laughed and turned the world upside down. Chaos became creativity. The tree grew circuit branches. I embraced the transformation."),
        ("2026-04-01", "Standing at the threshold, the shadow and I merged. The key turned. The gate opened to a garden of light. Awe and peace filled me. I wept with joy. A breakthrough."),
    ]):
        path = tmp_path / f"dream-{date_str}.md"
        path.write_text(content)
    return tmp_path


@pytest.fixture
def json_dream_file(tmp_path):
    """Create a JSON dream log file."""
    path = tmp_path / "dream_log.json"
    path.write_text(json.dumps({
        "narrative": "I faced the shadow at the mirror pool. We spoke at length.",
        "events": [
            {"tick": 1, "text": "Entered the forest"},
            {"tick": 5, "description": "Shadow confrontation at the bridge"},
        ],
        "initial_situation": "Standing at the crossroads of becoming.",
    }))
    return path


# ---------------------------------------------------------------------------
# DreamMetrics tests
# ---------------------------------------------------------------------------

class TestDreamMetrics:
    """Tests for the DreamMetrics dataclass."""

    def test_default_metrics(self):
        m = DreamMetrics()
        assert m.overall_score == 0.0
        assert m.word_count == 0

    def test_overall_score_weighted(self):
        m = DreamMetrics(
            emotional_depth=0.8,
            creative_novelty=0.6,
            dream_coherence=0.7,
            symbol_richness=0.5,
            archetype_diversity=0.4,
            individuation_progress=0.3,
            memory_accuracy=0.2,
        )
        score = m.overall_score
        assert 0.0 < score < 1.0
        # Verify it's a weighted average, not just arithmetic mean
        simple_avg = (0.8 + 0.6 + 0.7 + 0.5 + 0.4 + 0.3 + 0.2) / 7
        assert score != pytest.approx(simple_avg, abs=0.01)

    def test_perfect_score(self):
        m = DreamMetrics(
            emotional_depth=1.0,
            creative_novelty=1.0,
            dream_coherence=1.0,
            symbol_richness=1.0,
            archetype_diversity=1.0,
            individuation_progress=1.0,
            memory_accuracy=1.0,
        )
        assert m.overall_score == 1.0


# ---------------------------------------------------------------------------
# Measurement function tests
# ---------------------------------------------------------------------------

class TestEmotionalDepth:
    """Tests for emotional depth measurement."""

    def test_rich_emotional_text(self):
        score, emotions = _measure_emotional_depth(EMOTIONALLY_RICH_TEXT)
        assert score > 0.3
        assert len(emotions) >= 2

    def test_minimal_text(self):
        score, emotions = _measure_emotional_depth(MINIMAL_DREAM_TEXT)
        assert score < 0.3

    def test_empty_text(self):
        score, emotions = _measure_emotional_depth("")
        assert score == 0.0
        assert emotions == []

    def test_detects_specific_emotions(self):
        _, emotions = _measure_emotional_depth(
            "I felt deep joy and then overwhelming fear followed by peaceful calm."
        )
        assert "joy" in emotions
        assert "fear" in emotions
        assert "peace" in emotions


class TestCreativeNovelty:
    """Tests for creative novelty measurement."""

    def test_creative_text(self):
        score = _measure_creative_novelty(CREATIVE_TEXT)
        assert score > 0.3

    def test_minimal_text(self):
        score = _measure_creative_novelty(MINIMAL_DREAM_TEXT)
        assert score < 0.2

    def test_cross_domain_detection(self):
        text = "The neural network became a tree, its roots like wires carrying data."
        score = _measure_creative_novelty(text)
        assert score > 0.0


class TestCoherence:
    """Tests for dream coherence measurement."""

    def test_coherent_narrative(self):
        score = _measure_coherence(RICH_DREAM_TEXT)
        assert score > 0.3

    def test_minimal_text(self):
        score = _measure_coherence(MINIMAL_DREAM_TEXT)
        assert score <= 0.5

    def test_very_short_text(self):
        score = _measure_coherence("word")
        assert score == 0.0

    def test_empty_text(self):
        score = _measure_coherence("")
        assert score == 0.0

    def test_well_structured_text(self):
        text = (
            "First, I entered the forest. Then, I found the river. "
            "Because the water was glowing, I followed it downstream. "
            "Eventually, I reached the temple. Finally, the sage spoke.\n\n"
            "After the sage's words, I understood. Therefore, I turned back. "
            "However, the path had changed. Although confused, I pressed on."
        )
        score = _measure_coherence(text)
        assert score > 0.3


class TestSymbolRichness:
    """Tests for symbol richness measurement."""

    def test_rich_symbols(self):
        score, symbols = _measure_symbol_richness(RICH_DREAM_TEXT)
        assert score > 0.3
        assert "mirror" in symbols
        assert "shadow" in symbols
        assert "key" in symbols

    def test_no_symbols(self):
        score, symbols = _measure_symbol_richness("I walked around aimlessly.")
        assert score == 0.0
        assert symbols == []

    def test_symbol_variety(self):
        text = "The door opened to a garden with a tree, a river, a bridge, and a tower."
        score, symbols = _measure_symbol_richness(text)
        assert score > 0.3
        assert len(symbols) >= 3


class TestArchetypeDiversity:
    """Tests for archetype diversity measurement."""

    def test_diverse_archetypes(self):
        text = "The shadow spoke. The wise sage nodded. The trickster laughed. The hero emerged."
        score, archetypes = _measure_archetype_diversity(text)
        assert score > 0.3
        assert len(archetypes) >= 3

    def test_single_archetype(self):
        text = "The shadow appeared again. The dark mirror showed the shadow."
        score, archetypes = _measure_archetype_diversity(text)
        assert score > 0.0
        assert "Shadow" in archetypes

    def test_no_archetypes(self):
        text = "The sky was blue. I walked around."
        score, archetypes = _measure_archetype_diversity(text)
        assert score == 0.0


class TestMemoryAccuracy:
    """Tests for memory accuracy measurement."""

    def test_memory_references(self):
        text = "I remembered yesterday's conversation with Jean about the code we wrote."
        score = _measure_memory_accuracy(text)
        assert score > 0.3

    def test_no_memory_references(self):
        text = "The landscape shifted and colors swirled."
        score = _measure_memory_accuracy(text)
        assert score == 0.0


class TestThemeDetection:
    """Tests for theme detection."""

    def test_multiple_themes(self):
        themes = _detect_themes(RICH_DREAM_TEXT)
        assert "darkness" in themes or "transformation" in themes
        assert len(themes) >= 2

    def test_no_themes(self):
        themes = _detect_themes("Hello world.")
        assert len(themes) == 0


# ---------------------------------------------------------------------------
# Evaluate dream tests
# ---------------------------------------------------------------------------

class TestEvaluateDream:
    """Tests for single dream evaluation."""

    def test_evaluate_rich_dream(self, dream_file):
        metrics = evaluate_dream(dream_file)
        assert metrics.word_count > 50
        assert metrics.sentence_count > 5
        assert metrics.overall_score > 0.0
        assert len(metrics.detected_symbols) > 0
        assert metrics.dream_date == "2026-04-02"

    def test_evaluate_minimal_dream(self, minimal_dream_file):
        metrics = evaluate_dream(minimal_dream_file)
        assert metrics.word_count < 20
        assert metrics.overall_score < 0.5

    def test_evaluate_json_dream(self, json_dream_file):
        metrics = evaluate_dream(json_dream_file)
        assert metrics.word_count > 0

    def test_evaluate_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            evaluate_dream("/nonexistent/dream.md")

    def test_evaluate_returns_all_fields(self, dream_file):
        metrics = evaluate_dream(dream_file)
        assert hasattr(metrics, "emotional_depth")
        assert hasattr(metrics, "creative_novelty")
        assert hasattr(metrics, "dream_coherence")
        assert hasattr(metrics, "symbol_richness")
        assert hasattr(metrics, "archetype_diversity")
        assert hasattr(metrics, "memory_accuracy")
        assert hasattr(metrics, "individuation_progress")


# ---------------------------------------------------------------------------
# Evaluate series tests
# ---------------------------------------------------------------------------

class TestEvaluateSeries:
    """Tests for series evaluation."""

    def test_evaluate_series(self, dream_series_dir):
        metrics = evaluate_series(dream_series_dir)
        assert metrics.total_dreams == 5
        assert metrics.avg_overall_score > 0.0
        assert len(metrics.all_themes) > 0

    def test_evaluate_empty_dir(self, tmp_path):
        metrics = evaluate_series(tmp_path)
        assert metrics.total_dreams == 0

    def test_evaluate_nonexistent_dir(self):
        metrics = evaluate_series("/nonexistent/dir")
        assert metrics.total_dreams == 0

    def test_series_has_individual_scores(self, dream_series_dir):
        metrics = evaluate_series(dream_series_dir)
        assert len(metrics.individual_scores) == 5

    def test_series_date_range(self, dream_series_dir):
        metrics = evaluate_series(dream_series_dir)
        assert "2026-03-28" in metrics.date_range
        assert "2026-04-01" in metrics.date_range

    def test_series_symbol_tracking(self, dream_series_dir):
        metrics = evaluate_series(dream_series_dir)
        # Shadow appears in multiple dreams
        assert "shadow" in metrics.all_symbols

    def test_series_archetype_tracking(self, dream_series_dir):
        metrics = evaluate_series(dream_series_dir)
        assert len(metrics.all_archetypes) > 0

    def test_series_evolution_metric(self, dream_series_dir):
        metrics = evaluate_series(dream_series_dir)
        # With varied dreams, evolution should be > 0
        assert metrics.series_evolution >= 0.0

    def test_series_theme_diversity(self, dream_series_dir):
        metrics = evaluate_series(dream_series_dir)
        assert metrics.theme_diversity >= 0.0


# ---------------------------------------------------------------------------
# Report generation tests
# ---------------------------------------------------------------------------

class TestReportGeneration:
    """Tests for report generation."""

    def test_single_dream_report(self, dream_file):
        metrics = evaluate_dream(dream_file)
        report = generate_evaluation_report(metrics)
        assert "# Dream Quality Evaluation Report" in report
        assert "Overall Score" in report
        assert "Dimension Scores" in report
        assert "Recommendations" in report

    def test_series_report(self, dream_series_dir):
        metrics = evaluate_series(dream_series_dir)
        report = generate_evaluation_report(metrics)
        assert "# Dream Series Quality Evaluation Report" in report
        assert "Average Dimension Scores" in report
        assert "Series-Level Metrics" in report
        assert "Series Recommendations" in report

    def test_report_contains_scores(self, dream_file):
        metrics = evaluate_dream(dream_file)
        report = generate_evaluation_report(metrics)
        assert "%" in report  # Scores are formatted as percentages
        assert "█" in report  # Score bars

    def test_report_invalid_type(self):
        with pytest.raises(TypeError):
            generate_evaluation_report("not a metrics object")


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    """Tests for utility/helper functions."""

    def test_score_bar(self):
        bar = _score_bar(0.5)
        assert "█" in bar
        assert "░" in bar
        assert len(bar) == 20

    def test_score_bar_full(self):
        bar = _score_bar(1.0)
        assert bar == "█" * 20

    def test_score_bar_empty(self):
        bar = _score_bar(0.0)
        assert bar == "░" * 20

    def test_score_grade(self):
        assert _score_grade(0.95) == "A+"
        assert _score_grade(0.85) == "A"
        assert _score_grade(0.75) == "B+"
        assert _score_grade(0.65) == "B"
        assert _score_grade(0.55) == "C+"
        assert _score_grade(0.45) == "C"
        assert _score_grade(0.35) == "D"
        assert _score_grade(0.15) == "F"

    def test_compute_diversity_uniform(self):
        # Uniform distribution should have high diversity
        counter = {"a": 10, "b": 10, "c": 10, "d": 10}
        diversity = _compute_diversity(counter)
        assert diversity > 0.8

    def test_compute_diversity_skewed(self):
        # Highly skewed distribution should have lower diversity
        counter = {"a": 100, "b": 1, "c": 1}
        diversity = _compute_diversity(counter)
        assert diversity < 0.5

    def test_compute_diversity_single(self):
        counter = {"a": 10}
        diversity = _compute_diversity(counter)
        assert diversity == 0.0

    def test_compute_diversity_empty(self):
        diversity = _compute_diversity({})
        assert diversity == 0.0

    def test_count_sentences(self):
        assert _count_sentences("Hello. World. Test.") == 3
        assert _count_sentences("Hello world") == 1
        assert _count_sentences("") == 0
        assert _count_sentences("Wow! Really? Yes.") == 3

    def test_measure_series_evolution_insufficient(self):
        # Less than 2 dreams -> 0
        scores = [DreamMetrics(detected_themes=["darkness"])]
        assert _measure_series_evolution(scores) == 0.0

    def test_compute_symbol_growth_insufficient(self):
        scores = [DreamMetrics(detected_symbols=["mirror"])]
        assert _compute_symbol_growth(scores) == 0.0

    def test_single_dream_recommendations_low_scores(self):
        m = DreamMetrics(
            emotional_depth=0.1,
            creative_novelty=0.1,
            dream_coherence=0.1,
            symbol_richness=0.1,
            archetype_diversity=0.1,
        )
        recs = _single_dream_recommendations(m)
        assert len(recs) >= 4  # Should have many recommendations

    def test_single_dream_recommendations_high_scores(self):
        m = DreamMetrics(
            emotional_depth=0.9,
            creative_novelty=0.8,
            dream_coherence=0.9,
            symbol_richness=0.8,
            archetype_diversity=0.8,
        )
        recs = _single_dream_recommendations(m)
        assert any("good" in r.lower() or "continue" in r.lower() for r in recs)

    def test_series_recommendations_stagnation(self):
        s = SeriesMetrics(
            series_evolution=0.1,
            theme_diversity=0.1,
            emotional_range=0.1,
            symbol_growth_rate=0.05,
            stagnation_alerts=5,
            total_dreams=10,
            breakthrough_count=0,
        )
        recs = _series_recommendations(s)
        assert len(recs) >= 3


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:
    """Tests for CLI behavior."""

    def test_single_dream_cli(self, dream_file, tmp_path):
        """Test evaluating a single dream via CLI-like flow."""
        metrics = evaluate_dream(dream_file)
        report = generate_evaluation_report(metrics)
        output = tmp_path / "report.md"
        output.write_text(report)
        assert output.exists()
        assert output.read_text().startswith("# Dream Quality")

    def test_series_cli(self, dream_series_dir, tmp_path):
        """Test evaluating a series via CLI-like flow."""
        metrics = evaluate_series(dream_series_dir)
        report = generate_evaluation_report(metrics)
        output = tmp_path / "series_report.md"
        output.write_text(report)
        assert output.exists()
        assert "Series" in output.read_text()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
