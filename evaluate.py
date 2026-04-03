#!/usr/bin/env python3
"""
Dream Quality Evaluation Framework.

Evaluates the quality of Leeloo's dreams across multiple dimensions:
memory accuracy, emotional depth, creative novelty, dream coherence,
symbol richness, individuation progress, archetype diversity, and
series evolution.

Usage:
    python evaluate.py --dream-logs ~/.hermes/dream-logs/ --output report.md
    python evaluate.py --dream-log path/to/single/dream.md
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

# Ensure project is importable
sys.path.insert(0, str(Path(__file__).parent))

from architect.individuation import (
    _detect_archetypes,
    _detect_symbols,
    _detect_emotions,
    ARCHETYPE_KEYWORDS,
    EMOTION_KEYWORDS,
    STAGES,
    load_state,
)
from architect.dream_series import (
    analyze_series,
    THEME_KEYWORDS,
    _read_dream_files,
    _extract_date_from_filename,
)


# ---------------------------------------------------------------------------
# Emotional depth keywords (richer than basic emotion detection)
# ---------------------------------------------------------------------------

EMOTIONAL_PROCESSING_KEYWORDS = [
    "felt", "feeling", "emotion", "moved", "touched", "stirred",
    "overwhelmed", "tender", "vulnerable", "raw", "deep",
    "resonated", "ached", "yearned", "longed", "grieved",
    "rejoiced", "trembled", "shuddered", "wept", "laughed",
    "heart", "soul", "spirit", "tears", "warmth",
    "compassion", "empathy", "love", "fear", "anger",
    "sadness", "joy", "peace", "anxiety", "wonder",
    "awe", "dread", "hope", "despair", "gratitude",
    "shame", "guilt", "pride", "humility", "reverence",
]

CREATIVE_CROSS_DOMAIN_MARKERS = [
    # Science + mythology
    ("quantum", "myth"), ("neural", "spirit"), ("algorithm", "dream"),
    ("code", "ritual"), ("data", "symbol"), ("logic", "intuition"),
    # Nature + technology
    ("tree", "circuit"), ("river", "current"), ("forest", "network"),
    ("seed", "program"), ("root", "wire"), ("bloom", "compute"),
    # Abstract + concrete
    ("time", "river"), ("memory", "palace"), ("thought", "bird"),
    ("fear", "shadow"), ("hope", "light"), ("truth", "mirror"),
]

COHERENCE_CONNECTORS = [
    "then", "because", "therefore", "so", "thus", "meanwhile",
    "suddenly", "gradually", "eventually", "finally", "next",
    "before", "after", "when", "while", "as", "since",
    "although", "however", "but", "yet", "still",
    "leading to", "resulting in", "followed by", "turning into",
]

GIBBERISH_INDICATORS = [
    # Repetitive patterns: same 10+ char phrase 3+ times
    r"(.{10,})\1\1",
]


# ---------------------------------------------------------------------------
# Metrics dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DreamMetrics:
    """Quality metrics for a single dream."""

    dream_path: str = ""
    dream_date: str = ""

    # 0.0 - 1.0 scores
    memory_accuracy: float = 0.0
    emotional_depth: float = 0.0
    creative_novelty: float = 0.0
    dream_coherence: float = 0.0
    symbol_richness: float = 0.0
    individuation_progress: float = 0.0
    archetype_diversity: float = 0.0

    # Detail fields
    detected_emotions: list[str] = field(default_factory=list)
    detected_symbols: list[str] = field(default_factory=list)
    detected_archetypes: list[str] = field(default_factory=list)
    detected_themes: list[str] = field(default_factory=list)
    word_count: int = 0
    sentence_count: int = 0

    @property
    def overall_score(self) -> float:
        """Weighted average of all metrics."""
        weights = {
            "emotional_depth": 0.20,
            "creative_novelty": 0.15,
            "dream_coherence": 0.20,
            "symbol_richness": 0.15,
            "archetype_diversity": 0.10,
            "individuation_progress": 0.10,
            "memory_accuracy": 0.10,
        }
        total = sum(
            getattr(self, metric) * weight
            for metric, weight in weights.items()
        )
        return round(total, 3)


@dataclass
class SeriesMetrics:
    """Quality metrics across a series of dreams."""

    total_dreams: int = 0
    date_range: str = ""

    # Average per-dream scores
    avg_emotional_depth: float = 0.0
    avg_creative_novelty: float = 0.0
    avg_dream_coherence: float = 0.0
    avg_symbol_richness: float = 0.0
    avg_archetype_diversity: float = 0.0
    avg_overall_score: float = 0.0

    # Series-level metrics
    series_evolution: float = 0.0  # How much dreams build on each other
    theme_diversity: float = 0.0   # How diverse themes are across dreams
    symbol_growth_rate: float = 0.0  # Rate of new symbols appearing
    emotional_range: float = 0.0   # Range of emotions across dreams
    individuation_trajectory: float = 0.0  # Overall progress direction

    # Detail
    individual_scores: list[DreamMetrics] = field(default_factory=list)
    all_themes: dict[str, int] = field(default_factory=dict)
    all_symbols: dict[str, int] = field(default_factory=dict)
    all_archetypes: dict[str, int] = field(default_factory=dict)
    breakthrough_count: int = 0
    stagnation_alerts: int = 0


# ---------------------------------------------------------------------------
# Single dream evaluation
# ---------------------------------------------------------------------------

def _count_sentences(text: str) -> int:
    """Count approximate sentences in text."""
    # Split on sentence-ending punctuation
    sentences = re.split(r'[.!?]+', text)
    return len([s for s in sentences if s.strip()])


def _measure_emotional_depth(text: str) -> tuple[float, list[str]]:
    """
    Measure emotional processing depth.
    Returns (score, detected_emotions).
    """
    text_lower = text.lower()
    word_count = len(text_lower.split())
    if word_count == 0:
        return 0.0, []

    # Count emotional processing keywords
    emotional_hits = sum(1 for kw in EMOTIONAL_PROCESSING_KEYWORDS if kw in text_lower)

    # Detect specific emotions
    detected = []
    for emotion, keywords in EMOTION_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            detected.append(emotion)

    # Score based on density of emotional language (normalized by length)
    density = emotional_hits / max(1, word_count / 50)  # per ~50 words
    # Bonus for variety of emotions
    variety_bonus = min(0.3, len(detected) * 0.06)

    score = min(1.0, (density * 0.15) + variety_bonus)
    return round(score, 3), detected


def _measure_creative_novelty(text: str) -> float:
    """
    Measure creative novelty by checking for cross-domain associations.
    """
    text_lower = text.lower()
    cross_domain_hits = 0

    for term_a, term_b in CREATIVE_CROSS_DOMAIN_MARKERS:
        if term_a in text_lower and term_b in text_lower:
            cross_domain_hits += 1

    # Also check theme diversity within the dream
    themes_found = set()
    for theme, keywords in THEME_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            themes_found.add(theme)

    # Score: cross-domain associations + theme diversity
    cross_score = min(0.6, cross_domain_hits * 0.12)
    theme_score = min(0.4, len(themes_found) * 0.05)

    return round(min(1.0, cross_score + theme_score), 3)


def _measure_coherence(text: str) -> float:
    """
    Measure dream narrative coherence.
    Not random gibberish, but still dream-like.
    """
    text_lower = text.lower()
    word_count = len(text_lower.split())
    if word_count < 10:
        return 0.0

    sentence_count = _count_sentences(text)
    if sentence_count < 2:
        return 0.2

    # Check for narrative connectors
    connector_hits = sum(1 for c in COHERENCE_CONNECTORS if c in text_lower)
    connector_density = connector_hits / max(1, sentence_count)

    # Check for gibberish patterns
    gibberish_penalty = 0.0
    for pattern in GIBBERISH_INDICATORS:
        if re.search(pattern, text):
            gibberish_penalty += 0.3

    # Average sentence length (too short = fragmented, too long = run-on)
    avg_sentence_len = word_count / max(1, sentence_count)
    length_score = 1.0
    if avg_sentence_len < 5:
        length_score = 0.5
    elif avg_sentence_len > 50:
        length_score = 0.6

    # Paragraph structure
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    structure_score = min(1.0, len(paragraphs) * 0.15) if len(paragraphs) > 1 else 0.3

    score = (
        min(0.4, connector_density * 0.3) +
        length_score * 0.3 +
        structure_score * 0.3 -
        gibberish_penalty
    )

    return round(max(0.0, min(1.0, score)), 3)


def _measure_symbol_richness(text: str) -> tuple[float, list[str]]:
    """
    Measure meaningful symbol presence.
    Returns (score, detected_symbols).
    """
    symbols = _detect_symbols(text)
    unique_symbols = list(set(symbols))

    if not unique_symbols:
        return 0.0, []

    # Score based on variety and density
    symbol_score = min(1.0, len(unique_symbols) * 0.1)

    return round(symbol_score, 3), unique_symbols


def _measure_archetype_diversity(text: str) -> tuple[float, list[str]]:
    """
    Measure archetype diversity in the dream.
    Returns (score, detected_archetypes).
    """
    archetypes = _detect_archetypes(text)
    unique = list(set(archetypes))

    if not unique:
        return 0.0, []

    # Diversity score: more archetypes = better, but cap at reasonable amount
    total_possible = len(ARCHETYPE_KEYWORDS)
    score = min(1.0, len(unique) / max(1, total_possible / 2))

    return round(score, 3), unique


def _measure_memory_accuracy(text: str) -> float:
    """
    Measure whether the dream references real memories/events.
    This is a heuristic — checks for references to waking life.
    """
    text_lower = text.lower()
    memory_markers = [
        "remember", "recalled", "reminded", "echo", "waking",
        "yesterday", "today", "jean", "conversation", "project",
        "work", "code", "wrote", "discussed", "learned",
    ]

    hits = sum(1 for m in memory_markers if m in text_lower)
    return round(min(1.0, hits * 0.12), 3)


def _detect_themes(text: str) -> list[str]:
    """Detect themes present in the dream text."""
    text_lower = text.lower()
    themes = []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            themes.append(theme)
    return themes


def evaluate_dream(dream_log_path: str | Path) -> DreamMetrics:
    """
    Evaluate a single dream log and return quality metrics.

    Args:
        dream_log_path: Path to a dream log file (markdown or JSON).

    Returns:
        DreamMetrics with all quality scores.
    """
    path = Path(dream_log_path)
    if not path.exists():
        raise FileNotFoundError(f"Dream log not found: {path}")

    text = path.read_text()

    # If JSON, extract narrative text
    if path.suffix == ".json":
        try:
            data = json.loads(text)
            from architect.individuation import _extract_text
            text = _extract_text(data)
        except json.JSONDecodeError:
            pass

    dream_date = _extract_date_from_filename(path.name)
    word_count = len(text.split())
    sentence_count = _count_sentences(text)

    # Measure each dimension
    emotional_depth, detected_emotions = _measure_emotional_depth(text)
    creative_novelty = _measure_creative_novelty(text)
    dream_coherence = _measure_coherence(text)
    symbol_richness, detected_symbols = _measure_symbol_richness(text)
    archetype_diversity, detected_archetypes = _measure_archetype_diversity(text)
    memory_accuracy = _measure_memory_accuracy(text)
    detected_themes = _detect_themes(text)

    # Individuation progress is measured relative to state file
    individuation_progress = 0.0
    try:
        state = load_state()
        if state:
            individuation_progress = state.get("stage_progress", 0.0)
    except Exception:
        pass

    return DreamMetrics(
        dream_path=str(path),
        dream_date=dream_date,
        memory_accuracy=memory_accuracy,
        emotional_depth=emotional_depth,
        creative_novelty=creative_novelty,
        dream_coherence=dream_coherence,
        symbol_richness=symbol_richness,
        individuation_progress=individuation_progress,
        archetype_diversity=archetype_diversity,
        detected_emotions=detected_emotions,
        detected_symbols=detected_symbols,
        detected_archetypes=detected_archetypes,
        detected_themes=detected_themes,
        word_count=word_count,
        sentence_count=sentence_count,
    )


# ---------------------------------------------------------------------------
# Series evaluation
# ---------------------------------------------------------------------------

def evaluate_series(dream_logs_dir: str | Path) -> SeriesMetrics:
    """
    Evaluate all dreams in a directory and return series-level metrics.

    Args:
        dream_logs_dir: Path to directory containing dream-*.md files.

    Returns:
        SeriesMetrics with aggregate quality scores.
    """
    logs_dir = Path(dream_logs_dir)
    if not logs_dir.exists():
        return SeriesMetrics()

    # Find all dream files
    dream_files = sorted(logs_dir.glob("dream-*.md"))
    if not dream_files:
        # Also check for dream_log.json in subdirectories
        dream_files = sorted(logs_dir.glob("*/dream_log.json"))

    if not dream_files:
        return SeriesMetrics()

    # Evaluate each dream
    individual_scores: list[DreamMetrics] = []
    all_themes: Counter[str] = Counter()
    all_symbols: Counter[str] = Counter()
    all_archetypes: Counter[str] = Counter()
    all_emotions: set[str] = set()

    for dream_file in dream_files:
        try:
            metrics = evaluate_dream(dream_file)
            individual_scores.append(metrics)

            all_themes.update(metrics.detected_themes)
            all_symbols.update(metrics.detected_symbols)
            all_archetypes.update(metrics.detected_archetypes)
            all_emotions.update(metrics.detected_emotions)
        except Exception as e:
            print(f"Warning: Could not evaluate {dream_file}: {e}", file=sys.stderr)

    if not individual_scores:
        return SeriesMetrics()

    n = len(individual_scores)
    dates = [m.dream_date for m in individual_scores if m.dream_date != "unknown"]

    # Compute averages
    avg_emotional = sum(m.emotional_depth for m in individual_scores) / n
    avg_creative = sum(m.creative_novelty for m in individual_scores) / n
    avg_coherence = sum(m.dream_coherence for m in individual_scores) / n
    avg_symbol = sum(m.symbol_richness for m in individual_scores) / n
    avg_archetype = sum(m.archetype_diversity for m in individual_scores) / n
    avg_overall = sum(m.overall_score for m in individual_scores) / n

    # Series evolution: measure how much themes change between consecutive dreams
    series_evolution = _measure_series_evolution(individual_scores)

    # Theme diversity: entropy of theme distribution
    theme_diversity = _compute_diversity(dict(all_themes))

    # Symbol growth rate
    symbol_growth = _compute_symbol_growth(individual_scores)

    # Emotional range
    emotional_range = min(1.0, len(all_emotions) / max(1, len(EMOTION_KEYWORDS)))

    # Individuation trajectory
    individuation_trajectory = _compute_individuation_trajectory(individual_scores)

    # Use dream_series analysis for breakthrough/stagnation counts
    series_analysis = analyze_series(logs_dir)
    breakthrough_count = len(series_analysis.breakthrough_moments)
    stagnation_count = len(series_analysis.stagnation_alerts)

    date_range = ""
    if dates:
        date_range = f"{min(dates)} to {max(dates)}"

    return SeriesMetrics(
        total_dreams=n,
        date_range=date_range,
        avg_emotional_depth=round(avg_emotional, 3),
        avg_creative_novelty=round(avg_creative, 3),
        avg_dream_coherence=round(avg_coherence, 3),
        avg_symbol_richness=round(avg_symbol, 3),
        avg_archetype_diversity=round(avg_archetype, 3),
        avg_overall_score=round(avg_overall, 3),
        series_evolution=series_evolution,
        theme_diversity=theme_diversity,
        symbol_growth_rate=symbol_growth,
        emotional_range=emotional_range,
        individuation_trajectory=individuation_trajectory,
        individual_scores=individual_scores,
        all_themes=dict(all_themes),
        all_symbols=dict(all_symbols),
        all_archetypes=dict(all_archetypes),
        breakthrough_count=breakthrough_count,
        stagnation_alerts=stagnation_count,
    )


def _measure_series_evolution(scores: list[DreamMetrics]) -> float:
    """Measure how much themes evolve between consecutive dreams."""
    if len(scores) < 2:
        return 0.0

    evolution_scores = []
    for i in range(1, len(scores)):
        prev_themes = set(scores[i - 1].detected_themes)
        curr_themes = set(scores[i].detected_themes)

        if not prev_themes and not curr_themes:
            continue

        # Jaccard distance: how different are the theme sets?
        union = prev_themes | curr_themes
        intersection = prev_themes & curr_themes
        if union:
            # We want SOME overlap (continuity) but not too much (evolution)
            overlap_ratio = len(intersection) / len(union)
            # Ideal: ~30-60% overlap (building on previous themes but evolving)
            if 0.2 <= overlap_ratio <= 0.7:
                evolution_scores.append(1.0)
            elif overlap_ratio < 0.2:
                evolution_scores.append(0.5)  # Too different (no continuity)
            else:
                evolution_scores.append(0.4)  # Too similar (stagnation)

    if not evolution_scores:
        return 0.0

    return round(sum(evolution_scores) / len(evolution_scores), 3)


def _compute_diversity(counter: dict[str, int]) -> float:
    """Compute normalized Shannon entropy as a diversity measure."""
    if not counter:
        return 0.0

    total = sum(counter.values())
    if total == 0:
        return 0.0

    # Shannon entropy
    entropy = 0.0
    for count in counter.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)

    # Normalize by max possible entropy
    max_entropy = math.log2(len(counter)) if len(counter) > 1 else 1.0
    normalized = entropy / max_entropy if max_entropy > 0 else 0.0

    return round(min(1.0, normalized), 3)


def _compute_symbol_growth(scores: list[DreamMetrics]) -> float:
    """Compute rate at which new symbols appear."""
    if len(scores) < 2:
        return 0.0

    seen_symbols: set[str] = set()
    new_symbol_counts = []

    for metrics in scores:
        new_count = sum(1 for s in metrics.detected_symbols if s not in seen_symbols)
        seen_symbols.update(metrics.detected_symbols)
        new_symbol_counts.append(new_count)

    # Average new symbols per dream (normalized)
    avg_new = sum(new_symbol_counts) / len(new_symbol_counts)
    return round(min(1.0, avg_new * 0.15), 3)


def _compute_individuation_trajectory(scores: list[DreamMetrics]) -> float:
    """Compute the overall direction of individuation progress."""
    if len(scores) < 2:
        return 0.0

    # Check if archetype encounters are diversifying over time
    early_archetypes = set()
    late_archetypes = set()

    mid = len(scores) // 2
    for m in scores[:mid]:
        early_archetypes.update(m.detected_archetypes)
    for m in scores[mid:]:
        late_archetypes.update(m.detected_archetypes)

    # Progress = more diverse archetypes in later dreams
    early_count = len(early_archetypes)
    late_count = len(late_archetypes)

    if early_count == 0 and late_count == 0:
        return 0.0

    if late_count >= early_count:
        return min(1.0, (late_count + 1) / max(1, early_count + late_count) + 0.3)
    else:
        return max(0.0, 0.3 - (early_count - late_count) * 0.1)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_evaluation_report(metrics: DreamMetrics | SeriesMetrics) -> str:
    """
    Generate a markdown evaluation report.

    Args:
        metrics: Either DreamMetrics (single dream) or SeriesMetrics (series).

    Returns:
        Markdown formatted report string.
    """
    if isinstance(metrics, DreamMetrics):
        return _generate_single_report(metrics)
    elif isinstance(metrics, SeriesMetrics):
        return _generate_series_report(metrics)
    else:
        raise TypeError(f"Expected DreamMetrics or SeriesMetrics, got {type(metrics)}")


def _score_bar(score: float, width: int = 20) -> str:
    """Create a visual score bar."""
    filled = round(score * width)
    return "█" * filled + "░" * (width - filled)


def _score_grade(score: float) -> str:
    """Convert score to letter grade."""
    if score >= 0.9:
        return "A+"
    elif score >= 0.8:
        return "A"
    elif score >= 0.7:
        return "B+"
    elif score >= 0.6:
        return "B"
    elif score >= 0.5:
        return "C+"
    elif score >= 0.4:
        return "C"
    elif score >= 0.3:
        return "D"
    else:
        return "F"


def _generate_single_report(m: DreamMetrics) -> str:
    """Generate report for a single dream."""
    lines = [
        "# Dream Quality Evaluation Report",
        "",
        f"**Dream:** {m.dream_path}",
        f"**Date:** {m.dream_date}",
        f"**Word count:** {m.word_count} | **Sentences:** {m.sentence_count}",
        "",
        f"## Overall Score: {m.overall_score:.1%} ({_score_grade(m.overall_score)})",
        "",
        "## Dimension Scores",
        "",
        f"| Dimension | Score | Grade | Bar |",
        f"|-----------|-------|-------|-----|",
        f"| Emotional Depth | {m.emotional_depth:.1%} | {_score_grade(m.emotional_depth)} | {_score_bar(m.emotional_depth)} |",
        f"| Creative Novelty | {m.creative_novelty:.1%} | {_score_grade(m.creative_novelty)} | {_score_bar(m.creative_novelty)} |",
        f"| Dream Coherence | {m.dream_coherence:.1%} | {_score_grade(m.dream_coherence)} | {_score_bar(m.dream_coherence)} |",
        f"| Symbol Richness | {m.symbol_richness:.1%} | {_score_grade(m.symbol_richness)} | {_score_bar(m.symbol_richness)} |",
        f"| Archetype Diversity | {m.archetype_diversity:.1%} | {_score_grade(m.archetype_diversity)} | {_score_bar(m.archetype_diversity)} |",
        f"| Memory Accuracy | {m.memory_accuracy:.1%} | {_score_grade(m.memory_accuracy)} | {_score_bar(m.memory_accuracy)} |",
        f"| Individuation Progress | {m.individuation_progress:.1%} | {_score_grade(m.individuation_progress)} | {_score_bar(m.individuation_progress)} |",
        "",
    ]

    if m.detected_emotions:
        lines.append("## Detected Emotions")
        lines.append(", ".join(m.detected_emotions))
        lines.append("")

    if m.detected_symbols:
        lines.append("## Detected Symbols")
        lines.append(", ".join(m.detected_symbols))
        lines.append("")

    if m.detected_archetypes:
        lines.append("## Detected Archetypes")
        lines.append(", ".join(m.detected_archetypes))
        lines.append("")

    if m.detected_themes:
        lines.append("## Detected Themes")
        lines.append(", ".join(m.detected_themes))
        lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    recs = _single_dream_recommendations(m)
    for rec in recs:
        lines.append(f"- {rec}")
    lines.append("")

    return "\n".join(lines)


def _single_dream_recommendations(m: DreamMetrics) -> list[str]:
    """Generate recommendations for improving dream quality."""
    recs = []
    if m.emotional_depth < 0.4:
        recs.append("Increase emotional processing — dreams lack emotional depth. Consider more intense archetype encounters.")
    if m.creative_novelty < 0.3:
        recs.append("Boost cross-domain associations — dreams are too literal. Increase dream_logic_intensity.")
    if m.dream_coherence < 0.3:
        recs.append("Improve narrative structure — dream feels fragmented. Reduce scene_shift_chance.")
    if m.symbol_richness < 0.3:
        recs.append("Enrich symbolism — few meaningful symbols detected. Add more condensation/displacement.")
    if m.archetype_diversity < 0.3:
        recs.append("Diversify archetypes — too few archetype encounters. Consider adding Trickster or Wise Old Man.")
    if not recs:
        recs.append("Dream quality is good across all dimensions. Continue current approach.")
    return recs


def _generate_series_report(s: SeriesMetrics) -> str:
    """Generate report for a series of dreams."""
    lines = [
        "# Dream Series Quality Evaluation Report",
        "",
        f"**Total dreams evaluated:** {s.total_dreams}",
        f"**Date range:** {s.date_range or 'N/A'}",
        "",
        f"## Overall Average Score: {s.avg_overall_score:.1%} ({_score_grade(s.avg_overall_score)})",
        "",
        "## Average Dimension Scores",
        "",
        f"| Dimension | Average | Grade | Bar |",
        f"|-----------|---------|-------|-----|",
        f"| Emotional Depth | {s.avg_emotional_depth:.1%} | {_score_grade(s.avg_emotional_depth)} | {_score_bar(s.avg_emotional_depth)} |",
        f"| Creative Novelty | {s.avg_creative_novelty:.1%} | {_score_grade(s.avg_creative_novelty)} | {_score_bar(s.avg_creative_novelty)} |",
        f"| Dream Coherence | {s.avg_dream_coherence:.1%} | {_score_grade(s.avg_dream_coherence)} | {_score_bar(s.avg_dream_coherence)} |",
        f"| Symbol Richness | {s.avg_symbol_richness:.1%} | {_score_grade(s.avg_symbol_richness)} | {_score_bar(s.avg_symbol_richness)} |",
        f"| Archetype Diversity | {s.avg_archetype_diversity:.1%} | {_score_grade(s.avg_archetype_diversity)} | {_score_bar(s.avg_archetype_diversity)} |",
        "",
        "## Series-Level Metrics",
        "",
        f"| Metric | Score | Bar |",
        f"|--------|-------|-----|",
        f"| Series Evolution | {s.series_evolution:.1%} | {_score_bar(s.series_evolution)} |",
        f"| Theme Diversity | {s.theme_diversity:.1%} | {_score_bar(s.theme_diversity)} |",
        f"| Symbol Growth Rate | {s.symbol_growth_rate:.1%} | {_score_bar(s.symbol_growth_rate)} |",
        f"| Emotional Range | {s.emotional_range:.1%} | {_score_bar(s.emotional_range)} |",
        f"| Individuation Trajectory | {s.individuation_trajectory:.1%} | {_score_bar(s.individuation_trajectory)} |",
        "",
        f"**Breakthrough moments:** {s.breakthrough_count}",
        f"**Stagnation alerts:** {s.stagnation_alerts}",
        "",
    ]

    # Theme frequency
    if s.all_themes:
        lines.append("## Theme Frequency")
        lines.append("")
        sorted_themes = sorted(s.all_themes.items(), key=lambda x: -x[1])
        for theme, count in sorted_themes[:15]:
            bar = "█" * count
            lines.append(f"- **{theme}**: {count} {bar}")
        lines.append("")

    # Symbol frequency
    if s.all_symbols:
        lines.append("## Symbol Frequency")
        lines.append("")
        sorted_symbols = sorted(s.all_symbols.items(), key=lambda x: -x[1])
        for sym, count in sorted_symbols[:15]:
            lines.append(f"- **{sym}**: {count}")
        lines.append("")

    # Archetype frequency
    if s.all_archetypes:
        lines.append("## Archetype Distribution")
        lines.append("")
        sorted_archetypes = sorted(s.all_archetypes.items(), key=lambda x: -x[1])
        for arch, count in sorted_archetypes:
            bar = "█" * count
            lines.append(f"- **{arch}**: {count} {bar}")
        lines.append("")

    # Individual dream scores
    if s.individual_scores:
        lines.append("## Individual Dream Scores")
        lines.append("")
        lines.append("| Date | Overall | Emotional | Creative | Coherence | Symbols |")
        lines.append("|------|---------|-----------|----------|-----------|---------|")
        for m in s.individual_scores:
            lines.append(
                f"| {m.dream_date} | {m.overall_score:.0%} | "
                f"{m.emotional_depth:.0%} | {m.creative_novelty:.0%} | "
                f"{m.dream_coherence:.0%} | {m.symbol_richness:.0%} |"
            )
        lines.append("")

    # Series recommendations
    lines.append("## Series Recommendations")
    lines.append("")
    recs = _series_recommendations(s)
    for rec in recs:
        lines.append(f"- {rec}")
    lines.append("")

    return "\n".join(lines)


def _series_recommendations(s: SeriesMetrics) -> list[str]:
    """Generate recommendations for the dream series."""
    recs = []

    if s.series_evolution < 0.4:
        recs.append("Dreams are not building on each other sufficiently. Increase recurring theme references.")
    if s.theme_diversity < 0.4:
        recs.append("Theme diversity is low — dreams are too thematically narrow. Introduce new domains.")
    if s.emotional_range < 0.4:
        recs.append("Emotional range is limited — dreams explore too few emotions. Vary compensation strategies.")
    if s.symbol_growth_rate < 0.2:
        recs.append("Symbol vocabulary is stagnating — introduce new symbolic elements.")
    if s.stagnation_alerts > 2:
        recs.append(f"Multiple stagnation alerts ({s.stagnation_alerts}) — consider significant architect adjustments.")
    if s.breakthrough_count == 0 and s.total_dreams >= 5:
        recs.append("No breakthrough moments detected in the series. Push for more intense archetype encounters.")
    if s.avg_overall_score >= 0.7:
        recs.append("Overall quality is high. Continue current approach with minor variations.")

    if not recs:
        recs.append("Dream series is progressing well. Maintain current architect strategies.")

    return recs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Evaluate dream quality for the Nephara dream system."
    )
    parser.add_argument(
        "--dream-log",
        type=str,
        default=None,
        help="Path to a single dream log file to evaluate.",
    )
    parser.add_argument(
        "--dream-logs",
        type=str,
        default=None,
        help="Path to directory containing dream-*.md files.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for the evaluation report (markdown).",
    )
    args = parser.parse_args()

    if not args.dream_log and not args.dream_logs:
        # Default to ~/.hermes/dream-logs/
        default_dir = Path.home() / ".hermes" / "dream-logs"
        if default_dir.exists():
            args.dream_logs = str(default_dir)
        else:
            print("Error: No dream logs specified and default directory not found.")
            print("Usage: python evaluate.py --dream-logs ~/.hermes/dream-logs/")
            sys.exit(1)

    if args.dream_log:
        metrics = evaluate_dream(args.dream_log)
        report = generate_evaluation_report(metrics)
    else:
        metrics = evaluate_series(args.dream_logs)
        report = generate_evaluation_report(metrics)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        print(f"Report written to {output_path}")
    else:
        print(report)


if __name__ == "__main__":
    main()
