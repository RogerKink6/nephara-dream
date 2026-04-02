"""
Dream symbol generation using Freudian/Jungian dream-work mechanisms.

Implements condensation, displacement, and location generation from tensions.
Manages a persistent personal symbol dictionary that evolves across dreams.
"""

from __future__ import annotations

import json
import hashlib
import random
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Symbol generation functions (dream-work mechanisms)
# ---------------------------------------------------------------------------

def condensation(events: list[str]) -> dict:
    """
    Compress multiple day events into a single dream symbol.

    Freud's Verdichtung: multiple latent thoughts are fused into one manifest
    dream element. The symbol carries traces of all source events.

    Args:
        events: List of event descriptions from the day.

    Returns:
        A symbol dict with name, description, source_events, and associations.
    """
    if not events:
        return {
            "name": "the void",
            "description": "An empty space that hums with potential.",
            "source_events": [],
            "mechanism": "condensation",
            "associations": ["absence", "potential", "silence"],
        }

    # Extract key nouns/concepts from events (simple keyword extraction)
    all_words = []
    for event in events:
        words = [w.strip(".,!?;:'\"()") for w in event.lower().split()]
        # Filter to meaningful words (skip short/common ones)
        meaningful = [w for w in words if len(w) > 3 and w not in STOP_WORDS]
        all_words.extend(meaningful)

    # Find recurring themes
    word_freq: dict[str, int] = {}
    for w in all_words:
        word_freq[w] = word_freq.get(w, 0) + 1

    # Use most frequent words as basis for the symbol
    top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
    core_concepts = [w for w, _ in top_words] if top_words else ["something"]

    # Generate a condensed symbol using concept fusion templates
    template = random.choice(CONDENSATION_TEMPLATES)
    symbol_name = template["name_pattern"].format(
        concept1=core_concepts[0],
        concept2=core_concepts[1] if len(core_concepts) > 1 else "dream",
    )
    symbol_desc = template["desc_pattern"].format(
        concept1=core_concepts[0],
        concept2=core_concepts[1] if len(core_concepts) > 1 else "memory",
        count=len(events),
    )

    # Generate associations from all source concepts
    associations = core_concepts[:5] + _amplification_hints(core_concepts[:3])

    return {
        "name": symbol_name,
        "description": symbol_desc,
        "source_events": events,
        "mechanism": "condensation",
        "associations": associations,
    }


def displacement(event: str, charge: str) -> dict:
    """
    Move emotional charge from its original object to an unexpected one.

    Freud's Verschiebung: the emotional intensity is displaced from the
    significant element to a seemingly trivial one, disguising the source.

    Args:
        event: The original event description.
        charge: The emotional charge (e.g., "anger", "desire", "fear").

    Returns:
        A symbol dict with displaced emotional meaning.
    """
    # Map emotional charges to displacement targets
    charge_lower = charge.lower()
    targets = DISPLACEMENT_TARGETS.get(charge_lower, DISPLACEMENT_TARGETS["default"])
    target = random.choice(targets)

    return {
        "name": target["name"],
        "description": target["description"].format(charge=charge),
        "original_event": event,
        "displaced_charge": charge,
        "mechanism": "displacement",
        "associations": target["associations"] + [charge_lower],
    }


def generate_location_from_tension(tension: str) -> dict:
    """
    Generate a dream location configuration from an unresolved tension.

    The location metaphorically encodes the tension — it is NOT a literal
    representation but a symbolic space where the tension can be explored.

    Args:
        tension: Description of an unresolved tension from the day.

    Returns:
        A location config dict compatible with dream_world_config.json.
    """
    # Hash the tension to deterministically select a template
    h = int(hashlib.md5(tension.encode()).hexdigest()[:8], 16)

    template = LOCATION_TEMPLATES[h % len(LOCATION_TEMPLATES)]

    # Generate position (semi-random but deterministic per tension)
    x = 5 + (h % 20)
    y = 5 + ((h >> 8) % 20)

    return {
        "name": template["name"],
        "tile_type": template["tile_type"],
        "position": [x, y],
        "description": template["description"],
        "mood": template["mood"],
        "source_tension": tension,
    }


# ---------------------------------------------------------------------------
# Amplification hints
# ---------------------------------------------------------------------------

def _amplification_hints(concepts: list[str]) -> list[str]:
    """
    Generate mythological/cultural/personal associations for concepts.

    Jung's amplification: enriching a dream symbol by gathering parallel
    images from mythology, fairy tales, religion, and culture.
    """
    hints = []
    for concept in concepts:
        concept_lower = concept.lower()
        for keyword, associations in AMPLIFICATION_DATABASE.items():
            if keyword in concept_lower or concept_lower in keyword:
                hints.extend(associations[:2])
                break
    return hints


def amplify_symbol(symbol: dict) -> list[str]:
    """
    Generate amplification hints for a given dream symbol.

    Returns a list of mythological/cultural associations to enrich
    interpretation during the dream log phase.
    """
    hints = []
    name = symbol.get("name", "")
    associations = symbol.get("associations", [])

    # Amplify from name
    hints.extend(_amplification_hints([name]))

    # Amplify from associations
    for assoc in associations[:5]:
        hints.extend(_amplification_hints([assoc]))

    # Deduplicate
    seen = set()
    unique_hints = []
    for h in hints:
        if h not in seen:
            seen.add(h)
            unique_hints.append(h)

    return unique_hints


# ---------------------------------------------------------------------------
# Personal symbol dictionary (persistent across dreams)
# ---------------------------------------------------------------------------

class SymbolDictionary:
    """
    Persistent dictionary of dream symbols that evolves across dreams.

    Tracks which symbols have appeared, their meanings, how they've evolved,
    and when they should be retired (fully integrated).
    """

    DEFAULT_PATH = Path.home() / ".hermes" / "dream-logs" / "symbol_dictionary.json"

    def __init__(self, path: Optional[Path] = None):
        self.path = path or self.DEFAULT_PATH
        self.symbols: dict[str, dict] = {}
        self._load()

    def _load(self):
        """Load symbol dictionary from disk if it exists."""
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                self.symbols = data.get("symbols", {})
            except (json.JSONDecodeError, KeyError):
                self.symbols = {}

    def save(self):
        """Save symbol dictionary to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "symbols": self.symbols,
            "last_updated": datetime.now().isoformat(),
            "version": "1.0",
        }
        self.path.write_text(json.dumps(data, indent=2))

    def record_symbol(self, symbol: dict, dream_date: str):
        """
        Record a symbol's appearance in a dream.

        Tracks occurrences, evolving meanings, and integration status.
        """
        name = symbol.get("name", "unknown")
        key = name.lower().replace(" ", "_")

        if key not in self.symbols:
            self.symbols[key] = {
                "name": name,
                "first_appeared": dream_date,
                "occurrences": [],
                "meanings": [],
                "status": "active",  # active, evolving, integrating, retired
                "evolution_notes": [],
            }

        entry = self.symbols[key]
        entry["occurrences"].append({
            "date": dream_date,
            "mechanism": symbol.get("mechanism", "unknown"),
            "associations": symbol.get("associations", []),
        })

        # Track meaning evolution
        desc = symbol.get("description", "")
        if desc and (not entry["meanings"] or entry["meanings"][-1] != desc):
            entry["meanings"].append(desc)
            if len(entry["meanings"]) > 1:
                entry["status"] = "evolving"
                entry["evolution_notes"].append(
                    f"{dream_date}: meaning shifted from previous appearance"
                )

        # Check for retirement (appeared 7+ times and meaning has stabilized)
        if (len(entry["occurrences"]) >= 7
                and len(entry["meanings"]) > 0
                and entry["status"] != "retired"):
            # If meaning hasn't changed in last 3 appearances, consider integration
            recent_meanings = entry["meanings"][-3:]
            if len(set(recent_meanings)) == 1:
                entry["status"] = "integrating"
                entry["evolution_notes"].append(
                    f"{dream_date}: meaning stabilized, beginning integration"
                )

    def get_recurring_symbols(self, min_occurrences: int = 2) -> list[dict]:
        """Get symbols that have appeared multiple times."""
        recurring = []
        for key, entry in self.symbols.items():
            if len(entry["occurrences"]) >= min_occurrences:
                recurring.append({
                    "name": entry["name"],
                    "count": len(entry["occurrences"]),
                    "status": entry["status"],
                    "latest_meaning": entry["meanings"][-1] if entry["meanings"] else "",
                    "first_appeared": entry["first_appeared"],
                    "evolution_notes": entry["evolution_notes"],
                })
        return sorted(recurring, key=lambda x: x["count"], reverse=True)

    def get_active_symbols(self) -> list[dict]:
        """Get symbols that are still active (not retired)."""
        return [
            {"name": e["name"], "status": e["status"],
             "count": len(e["occurrences"]),
             "latest_meaning": e["meanings"][-1] if e["meanings"] else ""}
            for e in self.symbols.values()
            if e["status"] != "retired"
        ]

    def should_retire(self, symbol_name: str) -> bool:
        """Check if a symbol should be retired (fully integrated)."""
        key = symbol_name.lower().replace(" ", "_")
        entry = self.symbols.get(key)
        if not entry:
            return False
        return entry["status"] == "integrating" and len(entry["occurrences"]) >= 10

    def retire_symbol(self, symbol_name: str):
        """Mark a symbol as retired (fully integrated into consciousness)."""
        key = symbol_name.lower().replace(" ", "_")
        if key in self.symbols:
            self.symbols[key]["status"] = "retired"
            self.symbols[key]["evolution_notes"].append(
                f"{datetime.now().strftime('%Y-%m-%d')}: symbol retired (integrated)"
            )


# ---------------------------------------------------------------------------
# Static data: templates, targets, stop words
# ---------------------------------------------------------------------------

STOP_WORDS = {
    "the", "and", "for", "that", "this", "with", "from", "have", "been",
    "were", "they", "their", "about", "would", "could", "should", "will",
    "just", "more", "some", "than", "into", "what", "when", "where", "which",
    "there", "then", "them", "these", "those", "also", "very", "much",
    "like", "each", "make", "made", "does", "doing", "being", "having",
}

CONDENSATION_TEMPLATES = [
    {
        "name_pattern": "the {concept1}-{concept2} vessel",
        "desc_pattern": (
            "An object that holds {count} stories at once — it shimmers with "
            "{concept1} and hums with {concept2}."
        ),
    },
    {
        "name_pattern": "the garden of {concept1}",
        "desc_pattern": (
            "A garden where {concept1} grows as flowers and {concept2} runs as water. "
            "It contains {count} seasons simultaneously."
        ),
    },
    {
        "name_pattern": "the {concept1} mirror",
        "desc_pattern": (
            "A mirror that reflects not faces but {concept1} and {concept2}. "
            "Looking into it, you see {count} versions of truth at once."
        ),
    },
    {
        "name_pattern": "the bridge of {concept2}",
        "desc_pattern": (
            "A bridge built from {concept1} and {concept2}, spanning {count} "
            "impossible distances at once."
        ),
    },
    {
        "name_pattern": "the {concept1} key",
        "desc_pattern": (
            "A key made of solidified {concept1} that unlocks doors made of "
            "{concept2}. It was forged from {count} different fires."
        ),
    },
]

DISPLACEMENT_TARGETS = {
    "anger": [
        {"name": "a cracking teacup", "description": "A porcelain teacup developing a fracture that pulses with {charge}.",
         "associations": ["fragility", "pressure", "breaking_point", "domesticity"]},
        {"name": "red thread", "description": "A thread that keeps knotting itself, humming with {charge}.",
         "associations": ["connection", "tension", "entanglement", "fate"]},
        {"name": "a sharpening stone", "description": "A stone that sharpens itself, grinding with {charge}.",
         "associations": ["preparation", "edge", "patience", "violence"]},
    ],
    "fear": [
        {"name": "a closing door", "description": "A door slowly closing on its own, imbued with {charge}.",
         "associations": ["loss", "opportunity", "entrapment", "threshold"]},
        {"name": "descending fog", "description": "A fog that swallows landmarks, thick with {charge}.",
         "associations": ["obscurity", "disorientation", "the_unknown", "breath"]},
        {"name": "a ticking clock", "description": "A clock whose ticking grows louder, resonating with {charge}.",
         "associations": ["time", "mortality", "urgency", "heartbeat"]},
    ],
    "desire": [
        {"name": "a warm stone", "description": "A stone that radiates warmth from within, charged with {charge}.",
         "associations": ["heat", "hidden_fire", "touch", "patience"]},
        {"name": "an open window", "description": "A window letting in scented air, carrying {charge}.",
         "associations": ["possibility", "invitation", "breath", "yearning"]},
        {"name": "a ripening fruit", "description": "A fruit on the verge of perfect ripeness, heavy with {charge}.",
         "associations": ["maturity", "sweetness", "timing", "consumption"]},
    ],
    "sadness": [
        {"name": "a wilting flower", "description": "A flower losing petals one by one, each falling with {charge}.",
         "associations": ["impermanence", "beauty", "letting_go", "seasons"]},
        {"name": "rain on glass", "description": "Rain tracing patterns on a window, each drop carrying {charge}.",
         "associations": ["tears", "cleansing", "barrier", "observation"]},
        {"name": "an empty chair", "description": "A chair still warm from someone who left, holding {charge}.",
         "associations": ["absence", "presence", "memory", "waiting"]},
    ],
    "joy": [
        {"name": "a spinning top", "description": "A top that spins impossibly long, radiating {charge}.",
         "associations": ["momentum", "play", "balance", "perpetual_motion"]},
        {"name": "sunlight through leaves", "description": "Dappled light that dances and shifts, infused with {charge}.",
         "associations": ["nature", "impermanence", "beauty", "filtering"]},
    ],
    "shame": [
        {"name": "a stain that spreads", "description": "A mark on fabric that slowly grows, saturated with {charge}.",
         "associations": ["exposure", "indelibility", "visibility", "covering"]},
        {"name": "a too-bright light", "description": "A light that reveals too much, blazing with {charge}.",
         "associations": ["exposure", "scrutiny", "truth", "hiding"]},
    ],
    "default": [
        {"name": "a shifting stone", "description": "A stone that changes weight depending on who holds it, charged with {charge}.",
         "associations": ["burden", "relativity", "grounding", "transformation"]},
        {"name": "a sound from nowhere", "description": "A sound with no source that changes pitch, resonating with {charge}.",
         "associations": ["the_invisible", "perception", "haunting", "attention"]},
    ],
}

LOCATION_TEMPLATES = [
    {
        "name": "The Threshold Room",
        "tile_type": "Temple",
        "description": "A room with two doors and no walls. One door leads back, one leads forward. The floor is made of decisions.",
        "mood": "liminal",
    },
    {
        "name": "The Whispering Archive",
        "tile_type": "Temple",
        "description": "Shelves of books that rewrite themselves as you read. The librarian is always just out of sight.",
        "mood": "contemplative",
    },
    {
        "name": "The Inverted Garden",
        "tile_type": "Forest",
        "description": "A garden where roots grow upward and flowers bloom underground. What's buried here wants to be found.",
        "mood": "mysterious",
    },
    {
        "name": "The Tidal Plaza",
        "tile_type": "Square",
        "description": "A plaza that floods with memories at high tide and dries to reveal patterns at low tide.",
        "mood": "cyclical",
    },
    {
        "name": "The Forge of Echoes",
        "tile_type": "Tavern",
        "description": "A workshop where broken things are remade into something different. The anvil rings with old conversations.",
        "mood": "transformative",
    },
    {
        "name": "The Crystalline Depths",
        "tile_type": "Well",
        "description": "A well so deep it contains a sky at the bottom. Climbing down is the same as climbing up.",
        "mood": "paradoxical",
    },
    {
        "name": "The Meadow of First Things",
        "tile_type": "Meadow",
        "description": "A meadow where everything is being experienced for the first time. The grass remembers no footsteps.",
        "mood": "innocent",
    },
    {
        "name": "The River of Parallel Selves",
        "tile_type": "River",
        "description": "A river where each ripple shows a different version of the dreamer. Some versions wave. Some turn away.",
        "mood": "reflective",
    },
    {
        "name": "The Mask Market",
        "tile_type": "Square",
        "description": "A market where everyone wears masks and the masks are more honest than the faces beneath.",
        "mood": "revelatory",
    },
    {
        "name": "The Dissolving Bridge",
        "tile_type": "River",
        "description": "A bridge that dissolves behind you as you cross. There is only forward. The water below is made of what you've released.",
        "mood": "committed",
    },
    {
        "name": "The Hollow Mountain",
        "tile_type": "Temple",
        "description": "A mountain that is empty inside, containing a single room where echoes take on physical form.",
        "mood": "resonant",
    },
    {
        "name": "The Night Garden",
        "tile_type": "Forest",
        "description": "A garden that only exists after dark. Its flowers open to reveal tiny scenes from forgotten days.",
        "mood": "nostalgic",
    },
]

AMPLIFICATION_DATABASE = {
    "water": ["river Styx (boundary between worlds)", "baptismal waters (transformation)", "the flood (overwhelming emotion)"],
    "fire": ["Prometheus (stolen knowledge)", "the phoenix (rebirth)", "Agni (purification)"],
    "bridge": ["Bifrost (connection between worlds)", "the Chinvat Bridge (judgment)", "pontifex (bridge-builder)"],
    "mirror": ["Narcissus (self-reflection)", "the magic mirror (truth-telling)", "Alice's looking-glass (inversion)"],
    "key": ["Hecate's keys (crossroads)", "Peter's keys (authority/access)", "skeleton key (universal truth)"],
    "door": ["Janus (transitions)", "the Gates of Horn and Ivory (true/false dreams)", "the narrow gate (transformation)"],
    "garden": ["Eden (innocence/fall)", "Gethsemane (anguished decision)", "the alchemical garden (growth of the soul)"],
    "tree": ["Yggdrasil (world axis)", "the Bodhi tree (enlightenment)", "the Tree of Knowledge (forbidden wisdom)"],
    "stone": ["philosopher's stone (transformation)", "Sisyphus's boulder (futile labor)", "the foundation stone (grounding)"],
    "child": ["the Divine Child (puer aeternus)", "Moses in the bulrushes (hidden potential)", "the Christ child (incarnation of the Self)"],
    "shadow": ["Peter Pan's shadow (lost shadow = lost soul)", "the doppelganger (the other self)", "Plato's cave (illusion)"],
    "light": ["Lucifer (light-bearer, fallen knowledge)", "the holy grail (illumination)", "enlightenment (satori)"],
    "dark": ["the nigredo (alchemical darkness)", "the dark night of the soul (St. John of the Cross)", "Jonah's whale (descent)"],
    "mask": ["persona (Jung's social mask)", "the Greek theatrical mask (dramatic identity)", "Noh masks (archetypal emotion)"],
    "river": ["Lethe (forgetting)", "the Ganges (purification)", "Heraclitus (you never step in the same river twice)"],
    "mountain": ["Mount Sinai (revelation)", "Mount Meru (cosmic center)", "the mountain in alchemy (the Great Work)"],
    "cave": ["Plato's cave (illusion vs reality)", "the labyrinth (the unconscious)", "the womb (rebirth)"],
    "flower": ["the lotus (purity from mud)", "the rose (love and secrecy — sub rosa)", "cherry blossoms (impermanence)"],
    "clock": ["Chronos (time devouring)", "the Doomsday Clock (collective anxiety)", "the hourglass (mortality)"],
    "book": ["the Book of Life (totality of self)", "the Akashic records (cosmic memory)", "the unwritten book (potential)"],
}
