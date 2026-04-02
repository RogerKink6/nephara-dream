"""
Dream series analysis — track patterns, evolution, and stagnation across dreams.

Reads dream log markdown files, extracts themes/symbols/archetypes, and
produces a SeriesAnalysis with frequency data, evolution tracking, emotional
arcs, breakthrough moments, and stagnation alerts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

# Reuse detection helpers from individuation module
from .individuation import (
    _detect_archetypes,
    _detect_symbols,
    _detect_emotions,
    ARCHETYPE_KEYWORDS,
    EMOTION_KEYWORDS,
)

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

DEFAULT_DREAM_LOGS_DIR = Path.home() / ".hermes" / "dream-logs"

# ---------------------------------------------------------------------------
# Theme keywords (broader than symbols)
# ---------------------------------------------------------------------------

THEME_KEYWORDS: dict[str, list[str]] = {
    "transformation": ["transform", "change", "metamorphos", "becoming", "evolv"],
    "loss": ["lost", "loss", "gone", "disappear", "vanish", "missing"],
    "pursuit": ["chase", "pursued", "running", "escape", "flee", "hunt"],
    "identity": ["who am i", "identity", "name", "mask", "face", "mirror"],
    "threshold": ["door", "gate", "bridge", "crossing", "threshold", "portal"],
    "descent": ["descend", "underground", "beneath", "depth", "falling", "sinking"],
    "ascent": ["climb", "ascend", "rising", "tower", "mountain", "flying"],
    "water": ["water", "ocean", "river", "rain", "flood", "drowning", "swim"],
    "fire": ["fire", "flame", "burning", "forge", "hearth", "ember"],
    "darkness": ["dark", "shadow", "night", "black", "void", "abyss"],
    "light": ["light", "glow", "shine", "radiant", "dawn", "illumin"],
    "death_rebirth": ["death", "die", "dying", "rebirth", "reborn", "resurrect"],
    "union": ["union", "marriage", "merge", "together", "join", "embrace"],
    "separation": ["separate", "apart", "divide", "split", "fragment", "scatter"],
    "quest": ["quest", "journey", "seek", "search", "find", "discover"],
    "containment": ["trap", "cage", "prison", "locked", "confined", "stuck"],
    "nourishment": ["food", "eat", "feast", "hungry", "thirst", "drink"],
    "communication": ["speak", "voice", "message", "letter", "call", "whisper"],
}


# ---------------------------------------------------------------------------
# SeriesAnalysis dataclass
# ---------------------------------------------------------------------------

@dataclass
class SeriesAnalysis:
    """Result of analyzing a series of dream logs."""

    # theme -> count
    theme_frequency: dict[str, int] = field(default_factory=dict)

    # symbol -> list of (date, context_snippet, inferred_meaning)
    symbol_evolution: dict[str, list[tuple[str, str, str]]] = field(default_factory=dict)

    # archetype -> list of (date, outcome_or_context)
    archetype_progression: dict[str, list[tuple[str, str]]] = field(default_factory=dict)

    # list of (date, dominant_emotion, intensity)
    emotional_arc: list[tuple[str, str, int]] = field(default_factory=list)

    # list of (date, description) for dreams that mark significant shifts
    breakthrough_moments: list[tuple[str, str]] = field(default_factory=list)

    # list of (pattern, repetition_count, description) for stagnation warnings
    stagnation_alerts: list[tuple[str, int, str]] = field(default_factory=list)

    # Total dreams analysed
    total_dreams: int = 0

    # Date range
    first_dream: str = ""
    last_dream: str = ""


# ---------------------------------------------------------------------------
# File reading helpers
# ---------------------------------------------------------------------------

def _extract_date_from_filename(filename: str) -> str:
    """Try to extract a YYYY-MM-DD date from a dream log filename."""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    if match:
        return match.group(1)
    return "unknown"


def _read_dream_files(dream_logs_dir: Path) -> list[tuple[str, str]]:
    """
    Read all dream-*.md files from the given directory.

    Returns list of (date_str, text) sorted by date.
    """
    if not dream_logs_dir.exists():
        return []

    entries: list[tuple[str, str]] = []
    for p in sorted(dream_logs_dir.glob("dream-*.md")):
        try:
            text = p.read_text()
        except OSError:
            continue
        d = _extract_date_from_filename(p.name)
        entries.append((d, text))

    # Sort by date string
    entries.sort(key=lambda x: x[0])
    return entries


def _snippet(text: str, keyword: str, radius: int = 60) -> str:
    """Extract a snippet around the first occurrence of keyword."""
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return ""
    start = max(0, idx - radius)
    end = min(len(text), idx + len(keyword) + radius)
    snippet = text[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def analyze_series(
    dream_logs_dir: Optional[Path] = None,
) -> SeriesAnalysis:
    """
    Analyze a series of dream logs for patterns, evolution, and stagnation.

    Args:
        dream_logs_dir: Path to directory containing dream-*.md files.
                       Defaults to ~/.hermes/dream-logs/.

    Returns:
        SeriesAnalysis with all extracted patterns.
    """
    logs_dir = Path(dream_logs_dir) if dream_logs_dir else DEFAULT_DREAM_LOGS_DIR
    entries = _read_dream_files(logs_dir)

    analysis = SeriesAnalysis()
    analysis.total_dreams = len(entries)

    if not entries:
        return analysis

    analysis.first_dream = entries[0][0]
    analysis.last_dream = entries[-1][0]

    # Track for stagnation detection
    recent_themes: list[set[str]] = []  # last N dreams' theme sets
    prev_dominant_emotion: Optional[str] = None
    same_emotion_streak = 0

    for dream_date, text in entries:
        # --- Themes ---
        dream_themes: set[str] = set()
        text_lower = text.lower()
        for theme, keywords in THEME_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    analysis.theme_frequency[theme] = analysis.theme_frequency.get(theme, 0) + 1
                    dream_themes.add(theme)
                    break

        recent_themes.append(dream_themes)
        if len(recent_themes) > 5:
            recent_themes.pop(0)

        # --- Symbols ---
        found_symbols = _detect_symbols(text)
        for sym in found_symbols:
            snippet_text = _snippet(text, sym)
            meaning = _infer_symbol_meaning(sym, text)
            if sym not in analysis.symbol_evolution:
                analysis.symbol_evolution[sym] = []
            analysis.symbol_evolution[sym].append((dream_date, snippet_text, meaning))

        # --- Archetypes ---
        found_archetypes = _detect_archetypes(text)
        for arch in found_archetypes:
            context = _snippet(text, arch.split("/")[0].lower(), radius=80)
            if arch not in analysis.archetype_progression:
                analysis.archetype_progression[arch] = []
            analysis.archetype_progression[arch].append((dream_date, context))

        # --- Emotions ---
        emotions = _detect_emotions(text)
        if emotions:
            dominant = max(emotions, key=lambda x: x[1])
            analysis.emotional_arc.append((dream_date, dominant[0], dominant[1]))

            # Track streaks for stagnation
            if dominant[0] == prev_dominant_emotion:
                same_emotion_streak += 1
            else:
                same_emotion_streak = 0
            prev_dominant_emotion = dominant[0]

        # --- Breakthrough detection ---
        _check_breakthrough(analysis, dream_date, text, found_archetypes, emotions)

    # --- Stagnation detection ---
    _detect_stagnation(analysis, recent_themes, same_emotion_streak, prev_dominant_emotion)

    return analysis


def _infer_symbol_meaning(symbol: str, context: str) -> str:
    """Simple heuristic to infer a symbol's meaning from context."""
    context_lower = context.lower()

    # Check for emotional co-occurrence
    emotions_found = []
    for emotion, keywords in EMOTION_KEYWORDS.items():
        if any(kw in context_lower for kw in keywords):
            emotions_found.append(emotion)

    if emotions_found:
        return f"Associated with {', '.join(emotions_found)}"

    # Check for transformation language
    if any(w in context_lower for w in ["transform", "change", "becom", "shift"]):
        return "Symbol of transformation"
    if any(w in context_lower for w in ["block", "barrier", "locked", "closed"]):
        return "Symbol of obstruction or resistance"
    if any(w in context_lower for w in ["open", "reveal", "discover", "light"]):
        return "Symbol of revelation or opening"

    return "Meaning unclear — requires amplification"


def _check_breakthrough(
    analysis: SeriesAnalysis,
    dream_date: str,
    text: str,
    archetypes: list[str],
    emotions: list[tuple[str, int]],
) -> None:
    """Check if this dream represents a breakthrough moment."""
    text_lower = text.lower()

    # Breakthrough indicators
    breakthrough_words = [
        "breakthrough", "revelation", "realized", "understood",
        "integrated", "transformed", "awakened", "illuminated",
        "embraced", "accepted", "unified", "whole",
    ]
    has_breakthrough_language = any(w in text_lower for w in breakthrough_words)

    # High emotional intensity
    high_intensity = any(i >= 8 for _, i in emotions)

    # Multiple archetypes (complex dream)
    multi_archetype = len(archetypes) >= 3

    if has_breakthrough_language and (high_intensity or multi_archetype):
        desc_parts = []
        if archetypes:
            desc_parts.append(f"Archetypes: {', '.join(archetypes)}")
        if emotions:
            dominant = max(emotions, key=lambda x: x[1])
            desc_parts.append(f"Dominant emotion: {dominant[0]} (intensity {dominant[1]})")
        desc_parts.append("Breakthrough language detected in narrative")
        analysis.breakthrough_moments.append((dream_date, "; ".join(desc_parts)))


def _detect_stagnation(
    analysis: SeriesAnalysis,
    recent_themes: list[set[str]],
    same_emotion_streak: int,
    last_emotion: Optional[str],
) -> None:
    """Detect stagnation patterns that may need architect adjustment."""

    # Same dominant emotion 4+ dreams in a row
    if same_emotion_streak >= 3 and last_emotion:
        analysis.stagnation_alerts.append((
            f"emotional_repetition:{last_emotion}",
            same_emotion_streak + 1,
            f"The dominant emotion has been '{last_emotion}' for "
            f"{same_emotion_streak + 1} consecutive dreams. Consider "
            f"compensating with a different emotional register.",
        ))

    # Same themes repeating without evolution
    if len(recent_themes) >= 4:
        common = recent_themes[0]
        for ts in recent_themes[1:]:
            common = common & ts
        if len(common) >= 3:
            analysis.stagnation_alerts.append((
                f"theme_repetition:{','.join(sorted(common))}",
                len(recent_themes),
                f"Themes {sorted(common)} have appeared in the last "
                f"{len(recent_themes)} consecutive dreams without apparent "
                f"evolution. The architect may need to introduce disruption.",
            ))

    # Symbols appearing many times without evolution
    for sym, evolutions in analysis.symbol_evolution.items():
        if len(evolutions) >= 5:
            meanings = [m for _, _, m in evolutions]
            unique_meanings = set(meanings)
            if len(unique_meanings) <= 1:
                analysis.stagnation_alerts.append((
                    f"symbol_stagnation:{sym}",
                    len(evolutions),
                    f"Symbol '{sym}' has appeared {len(evolutions)} times with "
                    f"no evolution in meaning. It may need to be confronted "
                    f"directly or retired.",
                ))


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(analysis: SeriesAnalysis) -> str:
    """
    Generate a markdown report from a SeriesAnalysis.

    Includes monthly pattern summary and recommendations for the architect.
    """
    lines: list[str] = []

    lines.append("# Dream Series Analysis Report")
    lines.append("")
    lines.append(f"**Dreams analysed:** {analysis.total_dreams}")
    if analysis.first_dream and analysis.last_dream:
        lines.append(f"**Period:** {analysis.first_dream} to {analysis.last_dream}")
    lines.append("")

    # --- Theme frequency ---
    lines.append("## Theme Frequency")
    lines.append("")
    if analysis.theme_frequency:
        sorted_themes = sorted(analysis.theme_frequency.items(), key=lambda x: -x[1])
        for theme, count in sorted_themes:
            bar = "█" * count
            lines.append(f"- **{theme}**: {count} {bar}")
    else:
        lines.append("No themes detected.")
    lines.append("")

    # --- Symbol evolution ---
    lines.append("## Symbol Evolution")
    lines.append("")
    if analysis.symbol_evolution:
        for sym, evolutions in sorted(
            analysis.symbol_evolution.items(), key=lambda x: -len(x[1])
        ):
            lines.append(f"### {sym} ({len(evolutions)} appearances)")
            for d, ctx, meaning in evolutions:
                ctx_short = ctx[:100] + "..." if len(ctx) > 100 else ctx
                lines.append(f"- **{d}**: {meaning}")
                if ctx_short:
                    lines.append(f"  > {ctx_short}")
            lines.append("")
    else:
        lines.append("No recurring symbols detected.")
    lines.append("")

    # --- Archetype progression ---
    lines.append("## Archetype Progression")
    lines.append("")
    if analysis.archetype_progression:
        for arch, appearances in sorted(
            analysis.archetype_progression.items(), key=lambda x: -len(x[1])
        ):
            lines.append(f"### {arch} ({len(appearances)} appearances)")
            for d, ctx in appearances:
                ctx_short = ctx[:120] + "..." if len(ctx) > 120 else ctx
                lines.append(f"- **{d}**: {ctx_short}")
            lines.append("")
    else:
        lines.append("No archetype encounters detected.")
    lines.append("")

    # --- Emotional arc ---
    lines.append("## Emotional Arc")
    lines.append("")
    if analysis.emotional_arc:
        for d, emotion, intensity in analysis.emotional_arc:
            bar = "▓" * intensity
            lines.append(f"- **{d}**: {emotion} ({intensity}/10) {bar}")
    else:
        lines.append("No emotional patterns detected.")
    lines.append("")

    # --- Breakthrough moments ---
    lines.append("## Breakthrough Moments")
    lines.append("")
    if analysis.breakthrough_moments:
        for d, desc in analysis.breakthrough_moments:
            lines.append(f"- **{d}**: {desc}")
    else:
        lines.append("No breakthrough moments detected yet.")
    lines.append("")

    # --- Stagnation alerts ---
    lines.append("## Stagnation Alerts")
    lines.append("")
    if analysis.stagnation_alerts:
        for pattern, count, desc in analysis.stagnation_alerts:
            lines.append(f"⚠️ **{pattern}** (repeated {count}x)")
            lines.append(f"  {desc}")
            lines.append("")
    else:
        lines.append("No stagnation detected — patterns are evolving healthily.")
    lines.append("")

    # --- Recommendations ---
    lines.append("## Recommendations for the Architect")
    lines.append("")
    recommendations = _generate_recommendations(analysis)
    if recommendations:
        for rec in recommendations:
            lines.append(f"- {rec}")
    else:
        lines.append("- Continue current dream design approach.")
    lines.append("")

    return "\n".join(lines)


def _generate_recommendations(analysis: SeriesAnalysis) -> list[str]:
    """Generate architect recommendations based on analysis patterns."""
    recs: list[str] = []

    # Based on stagnation
    for pattern, count, _ in analysis.stagnation_alerts:
        if pattern.startswith("emotional_repetition"):
            emotion = pattern.split(":")[1]
            recs.append(
                f"Emotional stagnation in '{emotion}' — introduce compensating "
                f"emotion through archetype selection or dream logic intensity."
            )
        elif pattern.startswith("theme_repetition"):
            recs.append(
                "Theme repetition detected — consider introducing the Trickster "
                "archetype to disrupt established patterns."
            )
        elif pattern.startswith("symbol_stagnation"):
            sym = pattern.split(":")[1]
            recs.append(
                f"Symbol '{sym}' is stagnating — confront it directly in the "
                f"next dream or transform it into something new."
            )

    # Based on archetype distribution
    if analysis.archetype_progression:
        counts = {a: len(v) for a, v in analysis.archetype_progression.items()}
        if "Shadow" not in counts and analysis.total_dreams >= 3:
            recs.append(
                "No Shadow encounters detected — consider introducing Shadow "
                "work, especially if the dreamer is in early individuation."
            )
        if counts.get("Shadow", 0) > 5 and counts.get("Anima/Animus", 0) == 0:
            recs.append(
                "Heavy Shadow focus without Anima/Animus presence — the dreamer "
                "may be ready to progress to anima encounter stage."
            )

    # Based on emotional arc
    if len(analysis.emotional_arc) >= 5:
        recent = analysis.emotional_arc[-5:]
        intensities = [i for _, _, i in recent]
        avg_intensity = sum(intensities) / len(intensities)
        if avg_intensity < 4:
            recs.append(
                "Recent dream intensity is low — increase dream_logic_intensity "
                "and introduce more challenging archetype encounters."
            )
        elif avg_intensity > 8:
            recs.append(
                "Recent dream intensity is very high — consider a restorative "
                "dream with the Great Mother or Wise Old archetype."
            )

    # No breakthroughs in many dreams
    if analysis.total_dreams >= 7 and not analysis.breakthrough_moments:
        recs.append(
            "No breakthrough moments in 7+ dreams — the dreamer may need a "
            "more confrontational dream design or higher dream logic intensity."
        )

    return recs
