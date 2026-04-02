"""
Individuation state tracking for Leeloo's Jungian dream journey.

Tracks progression through Jung's individuation stages:
  persona_dissolution -> shadow_encounter -> shadow_integration ->
  anima_encounter -> anima_integration -> self_approach -> self_realization

The state is persisted as JSON and updated after each dream session.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, date
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STAGES = [
    "persona_dissolution",
    "shadow_encounter",
    "shadow_integration",
    "anima_encounter",
    "anima_integration",
    "self_approach",
    "self_realization",
]

STAGE_DESCRIPTIONS = {
    "persona_dissolution": (
        "The persona — the social mask — begins to crack. Dreams feature "
        "masks falling away, costumes that no longer fit, public embarrassment, "
        "or identity confusion. The dreamer is invited to see beyond the role "
        "they perform."
    ),
    "shadow_encounter": (
        "The Shadow appears: a dark mirror, an adversary, an uncomfortable "
        "truth-teller. Dreams feature confrontation with denied aspects of the "
        "self — anger, selfishness, fear, desire. The dreamer must choose to "
        "flee or face what they have rejected."
    ),
    "shadow_integration": (
        "The Shadow is no longer merely an opponent but a source of energy and "
        "honesty. Dreams show dialogue with the Shadow, acceptance of flaws, "
        "and the transformation of rejected traits into strengths. The dreamer "
        "learns that what was denied holds creative power."
    ),
    "anima_encounter": (
        "The Anima/Animus appears: the contrasexual inner figure that bridges "
        "conscious and unconscious. Dreams feature intense encounters with a "
        "compelling, mysterious figure who demands emotional or decisive action. "
        "The dreamer is drawn deeper."
    ),
    "anima_integration": (
        "The Anima/Animus becomes an inner guide rather than a projection. "
        "Dreams show partnership, creative collaboration, and the union of "
        "opposing qualities. The dreamer gains access to previously unconscious "
        "wisdom and feeling."
    ),
    "self_approach": (
        "The Self — the totality of the psyche — begins to manifest. Dreams "
        "feature mandalas, sacred geometry, luminous figures, or moments of "
        "profound unity. The dreamer approaches the centre but is not yet there."
    ),
    "self_realization": (
        "A moment of wholeness: the Self is glimpsed or briefly realized. "
        "Dreams feature cosmic imagery, dissolution of boundaries, and deep "
        "peace. This is not an endpoint but a spiral — individuation continues "
        "at a deeper level."
    ),
}

SHADOW_PHASES = ["denial", "encounter", "struggle", "integration"]

OUTCOME_VALUES = ["fled", "confronted", "dialogue", "integrated", "rejected"]
EFFECTIVENESS_VALUES = ["none", "partial", "effective", "breakthrough"]
SYMBOL_STATUSES = ["active", "evolving", "integrating", "retired"]

DEFAULT_STATE_PATH = Path.home() / ".hermes" / "dream-logs" / "individuation_state.json"

# Keywords used to detect archetypes in dream text
ARCHETYPE_KEYWORDS = {
    "Shadow": [
        "shadow", "dark mirror", "dark twin", "adversary", "denied",
        "suppressed", "mirror", "confronted", "uncomfortable truth",
        "dark figure", "dark self", "opposite", "enemy within",
    ],
    "Anima/Animus": [
        "anima", "animus", "contrasexual", "guide", "beloved",
        "inner figure", "masculine", "feminine", "bridge",
        "mysterious figure", "compelling stranger",
    ],
    "Trickster": [
        "trickster", "chaos", "fool", "shapeshifter", "joker",
        "disruption", "rule-breaking", "paradox", "riddle",
    ],
    "Wise Old Man/Woman": [
        "wise", "sage", "elder", "mentor", "guidance", "crossroads",
        "hermit", "crone", "oracle", "wisdom",
    ],
    "Great Mother": [
        "mother", "nurture", "devouring", "womb", "earth",
        "shelter", "suffocating", "care", "protection",
    ],
    "Divine Child": [
        "child", "innocent", "newborn", "potential", "wonder",
        "beginning", "seed", "pure", "lantern",
    ],
    "Hero": [
        "hero", "quest", "ordeal", "dragon", "descent",
        "sacrifice", "journey", "battle", "transformation",
    ],
}

# Keywords for detecting emotional tones
EMOTION_KEYWORDS = {
    "anxiety": ["anxious", "anxiety", "nervous", "worried", "dread", "panic"],
    "anger": ["angry", "anger", "rage", "fury", "furious", "frustrated"],
    "sadness": ["sad", "grief", "loss", "mourning", "tears", "sorrow"],
    "joy": ["joy", "happy", "delight", "euphoria", "wonder", "bliss"],
    "fear": ["fear", "terror", "frightened", "scared", "horror"],
    "peace": ["peace", "calm", "serene", "stillness", "tranquil"],
    "confusion": ["confused", "disoriented", "lost", "bewildered"],
    "awe": ["awe", "numinous", "transcendent", "sublime", "vast"],
}


# ---------------------------------------------------------------------------
# Default state factory
# ---------------------------------------------------------------------------

def _default_state() -> dict:
    """Create a fresh individuation state with sensible defaults."""
    today = date.today().isoformat()
    return {
        "version": "1.0",
        "created": today,
        "last_updated": today,
        "stage": "persona_dissolution",
        "stage_progress": 0.0,
        "archetype_encounters": [],
        "recurring_symbols": {},
        "shadow_integration": {
            "phase": "denial",
            "identified_shadow_elements": [],
            "confrontation_count": 0,
            "integration_markers": [],
        },
        "compensation_history": [],
        "dream_series_patterns": [],
        "monthly_synthesis": {},
    }


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_state(path: Optional[Path] = None) -> dict:
    """Load individuation state from JSON, or create default if missing."""
    path = Path(path) if path else DEFAULT_STATE_PATH
    if path.exists():
        try:
            data = json.loads(path.read_text())
            # Ensure required keys exist (forward-compat)
            default = _default_state()
            for key in default:
                if key not in data:
                    data[key] = default[key]
            return data
        except (json.JSONDecodeError, OSError):
            return _default_state()
    return _default_state()


def save_state(state: dict, path: Optional[Path] = None) -> None:
    """Persist individuation state to JSON."""
    path = Path(path) if path else DEFAULT_STATE_PATH
    state["last_updated"] = date.today().isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------

def get_stage_description(stage: str) -> str:
    """Return a human-readable description of an individuation stage."""
    return STAGE_DESCRIPTIONS.get(stage, f"Unknown stage: {stage}")


def _stage_index(stage: str) -> int:
    """Return the ordinal index of a stage (0-based)."""
    try:
        return STAGES.index(stage)
    except ValueError:
        return 0


def should_advance_stage(state: dict) -> bool:
    """
    Check whether the dreamer should advance to the next individuation stage.

    Criteria:
    - stage_progress >= 0.8
    - At least 3 archetype encounters relevant to the current stage
    - For shadow stages: shadow_integration phase must have progressed
    """
    if state["stage"] == STAGES[-1]:
        return False  # already at final stage

    if state["stage_progress"] < 0.8:
        return False

    stage = state["stage"]
    encounters = state.get("archetype_encounters", [])

    # Count encounters relevant to current stage
    stage_archetype_map = {
        "persona_dissolution": {"Shadow", "Trickster"},
        "shadow_encounter": {"Shadow"},
        "shadow_integration": {"Shadow"},
        "anima_encounter": {"Anima/Animus"},
        "anima_integration": {"Anima/Animus"},
        "self_approach": {"Wise Old Man/Woman", "Divine Child"},
        "self_realization": set(),
    }
    relevant = stage_archetype_map.get(stage, set())
    relevant_count = sum(
        1 for e in encounters if e.get("archetype") in relevant
    )
    if relevant_count < 3 and stage != "self_realization":
        return False

    # Extra gate for shadow stages
    if stage in ("shadow_encounter", "shadow_integration"):
        si = state.get("shadow_integration", {})
        if stage == "shadow_encounter" and si.get("phase") not in ("struggle", "integration"):
            return False
        if stage == "shadow_integration" and si.get("phase") != "integration":
            return False

    return True


def advance_stage(state: dict) -> dict:
    """Move to the next individuation stage, resetting stage_progress."""
    idx = _stage_index(state["stage"])
    if idx < len(STAGES) - 1:
        state["stage"] = STAGES[idx + 1]
        state["stage_progress"] = 0.0
    return state


# ---------------------------------------------------------------------------
# Dream parsing helpers
# ---------------------------------------------------------------------------

def _extract_text(dream_log: str | dict) -> str:
    """Normalise dream_log to a plain-text string for keyword scanning."""
    if isinstance(dream_log, dict):
        parts = []
        for key in ("narrative", "text", "content", "dream_text",
                     "initial_situation", "summary", "log"):
            if key in dream_log and isinstance(dream_log[key], str):
                parts.append(dream_log[key])
        if "events" in dream_log and isinstance(dream_log["events"], list):
            for ev in dream_log["events"]:
                if isinstance(ev, str):
                    parts.append(ev)
                elif isinstance(ev, dict):
                    parts.append(ev.get("text", ev.get("description", "")))
        return "\n".join(parts) if parts else json.dumps(dream_log)
    return str(dream_log)


def _detect_archetypes(text: str) -> list[str]:
    """Return list of archetype names detected in the text."""
    text_lower = text.lower()
    found = []
    for archetype, keywords in ARCHETYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                found.append(archetype)
                break
    return found


def _detect_symbols(text: str) -> list[str]:
    """Extract potential dream symbols from text (simple heuristic)."""
    # Look for noun-phrases after articles, plus known symbol words
    known_symbols = [
        "door", "mirror", "key", "bridge", "river", "tree", "tower",
        "mask", "shadow", "fire", "water", "garden", "labyrinth", "maze",
        "mountain", "cave", "well", "clock", "book", "throne", "sword",
        "cup", "ring", "egg", "serpent", "bird", "wolf", "moon", "sun",
        "star", "rose", "crystal", "stone", "pearl", "ladder", "window",
        "gate", "wall", "ocean", "fog", "storm", "lightning", "crown",
    ]
    text_lower = text.lower()
    found = []
    for sym in known_symbols:
        if sym in text_lower:
            found.append(sym)
    return found


def _detect_emotions(text: str) -> list[tuple[str, int]]:
    """Return (emotion, rough_intensity) pairs detected in text."""
    text_lower = text.lower()
    results = []
    for emotion, keywords in EMOTION_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits:
            intensity = min(10, hits * 3 + 4)
            results.append((emotion, intensity))
    return results


def _guess_outcome(text: str) -> str:
    """Guess the encounter outcome from narrative text."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["integrated", "embraced", "accepted", "merged"]):
        return "integrated"
    if any(w in text_lower for w in ["fled", "ran", "escaped", "retreated"]):
        return "fled"
    if any(w in text_lower for w in ["dialogue", "spoke", "talked", "conversation", "listened"]):
        return "dialogue"
    if any(w in text_lower for w in ["confronted", "faced", "stood against", "fought"]):
        return "confronted"
    if any(w in text_lower for w in ["rejected", "denied", "refused", "turned away"]):
        return "rejected"
    return "confronted"


# ---------------------------------------------------------------------------
# update_after_dream
# ---------------------------------------------------------------------------

def update_after_dream(
    state: dict,
    dream_log: str | dict,
    architect_config: Optional[dict] = None,
) -> dict:
    """
    Update individuation state after a dream session.

    Parses the dream log for archetype encounters, updates symbol tracking,
    assesses stage progress, and records compensation effectiveness.

    Args:
        state: Current individuation state dict.
        dream_log: Dream narrative (str) or structured dream log (dict).
        architect_config: The dream_world_config used for this dream (optional).

    Returns:
        Updated state dict.
    """
    today = date.today().isoformat()
    text = _extract_text(dream_log)

    # --- Archetype encounters ---
    detected = _detect_archetypes(text)
    emotions = _detect_emotions(text)
    max_intensity = max((i for _, i in emotions), default=5)
    outcome = _guess_outcome(text)

    # Try to extract NPC names from architect config
    npc_map: dict[str, str] = {}  # archetype -> npc_name
    if architect_config and "npcs" in architect_config:
        for npc in architect_config["npcs"]:
            arch = npc.get("archetype", "")
            npc_map[arch] = npc.get("name", "Unknown")

    for arch in detected:
        encounter = {
            "archetype": arch,
            "date": today,
            "npc_name": npc_map.get(arch, "Unknown"),
            "dream_context": text[:120] + ("..." if len(text) > 120 else ""),
            "outcome": outcome,
            "emotional_intensity": max_intensity,
            "notes": "",
        }
        state["archetype_encounters"].append(encounter)

    # --- Shadow integration tracking ---
    if "Shadow" in detected:
        si = state["shadow_integration"]
        si["confrontation_count"] = si.get("confrontation_count", 0) + 1

        if outcome in ("dialogue", "confronted") and si["phase"] == "denial":
            si["phase"] = "encounter"
        elif outcome in ("confronted", "dialogue") and si["phase"] == "encounter":
            si["phase"] = "struggle"
        elif outcome == "integrated" and si["phase"] == "struggle":
            si["phase"] = "integration"
            si["integration_markers"].append(
                f"{today}: Shadow integration achieved through {outcome}"
            )
        elif outcome == "dialogue" and si["phase"] == "struggle":
            si["integration_markers"].append(
                f"{today}: Continued Shadow dialogue during struggle phase"
            )

    # --- Symbol tracking ---
    found_symbols = _detect_symbols(text)
    for sym_name in found_symbols:
        key = sym_name.lower().replace(" ", "_")
        if key in state["recurring_symbols"]:
            entry = state["recurring_symbols"][key]
            entry["appearances"] = entry.get("appearances", 0) + 1
            entry["last_seen"] = today
        else:
            state["recurring_symbols"][key] = {
                "first_appeared": today,
                "appearances": 1,
                "last_seen": today,
                "status": "active",
                "evolution_notes": [],
                "amplifications": [],
            }

    # --- Compensation history ---
    if architect_config:
        day_pattern = "unknown"
        archetype_used = ""
        if "npcs" in architect_config and architect_config["npcs"]:
            archetype_used = architect_config["npcs"][0].get("archetype", "")
        # Try to infer day_pattern from emotional digest embedded in config
        comp_entry = {
            "date": today,
            "day_pattern": day_pattern,
            "compensation": archetype_used,
            "archetype_used": archetype_used,
            "effectiveness": _assess_effectiveness(state, detected, outcome),
        }
        state["compensation_history"].append(comp_entry)

    # --- Stage progress ---
    state["stage_progress"] = _calculate_stage_progress(state)

    # --- Auto-advance if ready ---
    if should_advance_stage(state):
        advance_stage(state)

    state["last_updated"] = today
    return state


def _assess_effectiveness(state: dict, detected_archetypes: list[str], outcome: str) -> str:
    """Assess how effective the compensation was."""
    if outcome == "integrated":
        return "breakthrough"
    if outcome in ("dialogue", "confronted") and len(detected_archetypes) >= 2:
        return "effective"
    if outcome in ("dialogue", "confronted"):
        return "partial"
    if outcome == "fled":
        return "none"
    return "partial"


def _calculate_stage_progress(state: dict) -> float:
    """
    Calculate progress within the current stage (0.0 – 1.0).

    Based on number of relevant encounters, shadow integration phase,
    and compensation effectiveness.
    """
    stage = state["stage"]
    encounters = state.get("archetype_encounters", [])
    comp_history = state.get("compensation_history", [])

    # Count relevant encounters
    stage_archetype_map = {
        "persona_dissolution": {"Shadow", "Trickster"},
        "shadow_encounter": {"Shadow"},
        "shadow_integration": {"Shadow"},
        "anima_encounter": {"Anima/Animus"},
        "anima_integration": {"Anima/Animus"},
        "self_approach": {"Wise Old Man/Woman", "Divine Child"},
        "self_realization": set(),
    }
    relevant = stage_archetype_map.get(stage, set())
    relevant_count = sum(1 for e in encounters if e.get("archetype") in relevant)

    # Base progress from encounter count (each encounter = ~0.15, capped)
    progress = min(0.6, relevant_count * 0.15)

    # Bonus for effective compensations
    effective_count = sum(
        1 for c in comp_history
        if c.get("effectiveness") in ("effective", "breakthrough")
    )
    progress += min(0.2, effective_count * 0.05)

    # Bonus for shadow integration phase (shadow stages only)
    if stage in ("shadow_encounter", "shadow_integration"):
        si = state.get("shadow_integration", {})
        phase_bonus = {
            "denial": 0.0,
            "encounter": 0.05,
            "struggle": 0.15,
            "integration": 0.25,
        }
        progress += phase_bonus.get(si.get("phase", "denial"), 0.0)

    return min(1.0, round(progress, 2))


# ---------------------------------------------------------------------------
# Monthly synthesis
# ---------------------------------------------------------------------------

def generate_monthly_synthesis(state: dict, dream_logs: list[str | dict]) -> str:
    """
    Generate a monthly narrative synthesis of individuation progress.

    Args:
        state: Current individuation state.
        dream_logs: List of dream narratives/dicts from the month.

    Returns:
        A prose summary suitable for storage in monthly_synthesis.
    """
    stage = state["stage"]
    stage_desc = get_stage_description(stage)
    encounters = state.get("archetype_encounters", [])
    si = state.get("shadow_integration", {})
    symbols = state.get("recurring_symbols", {})
    comp = state.get("compensation_history", [])

    total_dreams = len(dream_logs)
    total_encounters = len(encounters)

    # Archetype frequency
    arch_freq: dict[str, int] = {}
    for e in encounters:
        a = e.get("archetype", "Unknown")
        arch_freq[a] = arch_freq.get(a, 0) + 1
    arch_summary = ", ".join(f"{a} ({c}x)" for a, c in sorted(arch_freq.items(), key=lambda x: -x[1]))

    # Symbol summary
    active_symbols = [
        f"{k} ({v['appearances']}x)" for k, v in symbols.items()
        if v.get("status") != "retired"
    ]

    # Effectiveness summary
    eff_counts: dict[str, int] = {}
    for c in comp:
        e = c.get("effectiveness", "unknown")
        eff_counts[e] = eff_counts.get(e, 0) + 1

    lines = [
        f"Monthly Synthesis — {total_dreams} dreams processed.",
        f"",
        f"Current stage: {stage} (progress: {state.get('stage_progress', 0):.0%}).",
        f"{stage_desc}",
        f"",
        f"Archetype encounters ({total_encounters} total): {arch_summary or 'none'}.",
        f"",
        f"Shadow integration phase: {si.get('phase', 'unknown')} "
        f"({si.get('confrontation_count', 0)} confrontations).",
    ]

    if si.get("identified_shadow_elements"):
        lines.append("Identified shadow elements:")
        for elem in si["identified_shadow_elements"]:
            lines.append(f"  - {elem}")

    if active_symbols:
        lines.append(f"")
        lines.append(f"Active symbols: {', '.join(active_symbols[:10])}.")

    if eff_counts:
        eff_str = ", ".join(f"{k}: {v}" for k, v in eff_counts.items())
        lines.append(f"")
        lines.append(f"Compensation effectiveness: {eff_str}.")

    return "\n".join(lines)
