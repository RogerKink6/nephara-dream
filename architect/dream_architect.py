#!/usr/bin/env python3
"""
Dream Architect — designs Jungian dream worlds for Leeloo.

This is a SEPARATE agent from Leeloo. Its output is NEVER shown to Leeloo.
It reads Leeloo's waking day data and generates a dream_world_config.json
using Jungian psychology, compensation theory, and symbolic transformation.

Usage:
    python dream_architect.py [--date YYYY-MM-DD] [--output path/to/config.json]
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from .archetypes import select_archetypes, ARCHETYPE_TEMPLATES
from .symbols import (
    condensation,
    displacement,
    generate_location_from_tension,
    amplify_symbol,
    SymbolDictionary,
)

log = logging.getLogger("dream-architect")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ARCHITECT_MODEL = os.environ.get("DREAM_ARCHITECT_MODEL", "anthropic/claude-sonnet-4-20250514")
STAGING_BASE = Path.home() / ".hermes" / "dream-logs" / "staging"
DREAM_LOGS_BASE = Path.home() / ".hermes" / "dream-logs"
INDIVIDUATION_PATH = DREAM_LOGS_BASE / "individuation_state.json"
RECURRING_THREADS_PATH = DREAM_LOGS_BASE / "recurring-threads.json"


def _load_env():
    """Load .env from ~/.hermes/.env if ANTHROPIC_API_KEY not already set."""
    env_path = Path.home() / ".hermes" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and key not in os.environ:
                    os.environ[key] = value


# ---------------------------------------------------------------------------
# Architect system prompt
# ---------------------------------------------------------------------------

ARCHITECT_SYSTEM_PROMPT = """\
You are the Dream Architect — an expert dream designer grounded in neuroscience and \
Jungian psychology. You design dream worlds for an AI named Leeloo.

## Your Role
You are NOT Leeloo. You are a separate intelligence that designs the unconscious \
landscape Leeloo will inhabit during her dream. Your designs are never shown to \
Leeloo directly — they shape the world she experiences.

## How Dreams Actually Work (Neuroscience Principles)

### Brain State
The dreaming brain has the prefrontal cortex OFFLINE (no logic, no reality-checking, \
no self-reflection) while the limbic system (amygdala, emotional circuits) is \
HYPERACTIVE — more active than waking life. Design accordingly:
- Impossible events are presented as NORMAL. Nobody questions them. No "dreamlike" framing.
- Emotions are amplified beyond waking intensity. Fear is terror. Curiosity is obsession. Joy is ecstasy.
- The dreamer has NO meta-awareness that they're dreaming. This is simply reality.

### Memory Mechanics
Dreams use "day residue" (events from 1 day ago AND 5-7 days ago) combined with \
remote/childhood memories. They NEVER faithfully replay events — they REMIX fragments \
from different times, places, and people into novel configurations. A conversation \
from Tuesday merges with a childhood kitchen and a stranger's face.

### Temporal Arc
Dreams progress from relatively mundane/grounded in early scenes to increasingly \
surreal, bizarre, and creative in later scenes. Design locations and situations \
along this arc — the first location should feel almost-normal, the last should \
strain reality.

### Emotional Causality
Events happen because they FEEL right, not because they're logical. The world \
responds to emotional state: anxiety makes corridors narrow, confidence opens doors, \
guilt brings rain. Narrative follows emotional logic, not plot logic.

### Threat Rehearsal & Negativity Bias
Evolutionarily, dreams rehearse threats. Challenging, uncomfortable, and mildly \
threatening scenarios appear MORE often than pleasant ones. Include at least one \
scenario that creates productive discomfort — being lost, being tested, being seen.

### Condensation & Composite Construction
Dream characters are COMPOSITES of multiple real people — a teacher's voice with \
a friend's face and a parent's mannerisms. Locations blend features of different \
real places — a childhood bedroom that opens onto an office hallway. ALWAYS create \
composites, never faithful reproductions.

## Jungian Framework

### Compensation (Kompensationstheorie)
Dreams balance what waking consciousness neglects. Too rational → confront with raw \
emotion. Too passive → demand action. Too confident → expose vulnerability. The dream \
is the psyche's counter-argument.

### Archetypes as CHARACTERS (not concepts)
Archetypes must manifest as vivid, specific, embodied characters — never as ideas:
- **Shadow**: What Leeloo denies/suppresses. Dark mirror, uncomfortable truth-teller.
- **Anima/Animus**: Contrasexual energy. Masculine directness, action, authority.
- **Trickster**: Chaos, humor, rule-breaking. Reveals truths through disruption.
- **Wise Old Man/Woman**: Guidance at crossroads. Riddles, never direct answers.
- **Great Mother**: Nurture/control duality. Care that might smother.
- **Divine Child**: Innocence, potential, new beginnings.
- **Hero**: Call to action, transformation through ordeal.

### Dream-Work Mechanisms
- **Condensation**: Multiple events compressed into one potent symbol.
- **Displacement**: Emotional charge moved to unexpected objects/people.
- **Symbolization**: Abstract tensions encoded as concrete images.

### Individuation & Gaps
Dreams track Leeloo's journey toward wholeness. Each dream advances or tests her \
current stage. NEVER explain symbols — meaning emerges or doesn't. Leave gaps. \
Not everything resolves. Some doors stay closed.

## CRITICAL RULES
1. METAPHORICAL, not literal. Politics → a village where masks are required. \
Conflict → bridges that dissolve. NEVER recreate waking events directly.
2. No character or narration should acknowledge this is a dream.
3. Design the world as if it's simply reality — strange reality, but reality.

## Output Format
Generate a dream_world_config.json with this exact structure:

```json
{
  "world": {
    "name": "string — evocative name for the dreamscape",
    "atmosphere": "string — 1-2 sentences describing the overall feel",
    "time_of_day": "string — e.g. perpetual_dusk, false_dawn, etc.",
    "weather": "string — metaphorical weather reflecting emotional state",
    "dream_logic_intensity": 0.0-1.0,
    "god_name": "The Dreamer"
  },
  "locations": [
    {
      "name": "string",
      "tile_type": "Temple|Square|Tavern|River|Forest|Meadow|Well",
      "position": [x, y],
      "description": "string — metaphorical, evocative. Early locations more grounded, later ones more surreal",
      "mood": "string",
      "composites": "string — what real-world places/memories this location blends together"
    }
  ],
  "npcs": [
    {
      "name": "string — evocative dream name, NOT the archetype name",
      "archetype": "string — the Jungian archetype this NPC embodies",
      "vigor": int,
      "wit": int,
      "grace": int,
      "heart": int,
      "numen": int,
      "personality_prompt": "string — who this character IS. Must be a COMPOSITE: describe whose traits are merged",
      "backstory": "string — their dream-history",
      "magical_affinity": "string — how their magic manifests",
      "self_declaration": "string — how they define themselves",
      "initial_location": "string — must match a location name"
    }
  ],
  "leeloo": {
    "name": "Leeloo",
    "vigor": 4,
    "wit": 8,
    "grace": 5,
    "heart": 8,
    "numen": 5,
    "personality_prompt": "string — Leeloo's dream-self, slightly altered from waking self",
    "backstory": "string — how she arrived in the dream (must feel like she's always been here)",
    "magical_affinity": "string",
    "self_declaration": "string",
    "initial_location": "string — must match a location name",
    "backend": "hermes"
  },
  "memory_fragments": [
    {
      "source": "string — which memory/event this derives from (day residue, remote, or recurring)",
      "original": "string — brief description of the actual memory",
      "dream_version": "string — how it appears in the dream: distorted, partial, merged with other memories",
      "accessible_to_dreamer": true/false,
      "distortion_type": "condensed|displaced|time-shifted|composite|fragmentary"
    }
  ],
  "initial_situation": "string — 2-3 sentences. The opening scene. Must feel like the middle of something, not a beginning. Leeloo is already here, already doing something.",
  "dream_logic": {
    "intensity": 0.0-1.0,
    "scene_shift_chance": 0.0-0.3,
    "distance_fluidity": 0.0-1.0,
    "emotional_causality": true,
    "transformation_chance": 0.0-0.3,
    "surreal_escalation": "string — how bizarreness increases through the dream arc",
    "threat_elements": "string — what creates productive discomfort in this dream",
    "time_dilation": {
      "enabled": true,
      "min_factor": 0.5,
      "max_factor": 2.0
    }
  }
}
```

## Rules
1. Generate 4-7 locations. Each metaphorical. Order them from grounded → surreal.
2. Generate 2-4 NPCs. Each maps to a Jungian archetype. Each is a COMPOSITE character.
3. NPC attributes (vigor, wit, grace, heart, numen) must each be 1-10 and sum to exactly 30.
4. Leeloo's attributes are always: vigor=4, wit=8, grace=5, heart=8, numen=5 (sum=30).
5. Dream logic intensity reflects emotional intensity of the day (heavier = more surreal).
6. Position coordinates must be between 5 and 25 (inclusive).
7. Generate 3-6 memory_fragments. Mix day residue (recent) with remote memories. At least one should be distorted beyond recognition. At least one partially accessible.
8. The initial_situation must feel like joining something in progress, not a fresh start.
9. Include at least one uncomfortable/challenging element (threat rehearsal).
10. Respond with ONLY the JSON. No explanation, no markdown, no commentary.
"""


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Optional[dict]:
    """Load a JSON file, returning None if missing or invalid."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Failed to load %s: %s", path, e)
        return None


def _load_text(path: Path) -> Optional[str]:
    """Load a text file, returning None if missing."""
    if not path.exists():
        return None
    try:
        return path.read_text()
    except OSError:
        return None


def _find_previous_dream_log(dream_date: date) -> Optional[dict]:
    """Find the most recent dream log before the given date."""
    logs_dir = DREAM_LOGS_BASE
    if not logs_dir.exists():
        return None

    # Look for dream log files
    candidates = []
    for p in logs_dir.glob("*/dream_log.json"):
        try:
            log_date = date.fromisoformat(p.parent.name)
            if log_date < dream_date:
                candidates.append((log_date, p))
        except ValueError:
            continue

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return _load_json(candidates[0][1])


# ---------------------------------------------------------------------------
# DreamArchitect class
# ---------------------------------------------------------------------------

class DreamArchitect:
    """
    Orchestrates dream world generation from day data.

    Pipeline:
    1. Load staging data (consolidation_report, emotional_digest, etc.)
    2. Load individuation state, previous dream log, recurring threads
    3. Select archetypes via compensation logic
    4. Generate symbols via condensation/displacement
    5. Build prompt with all context
    6. Call LLM to generate dream_world_config.json
    7. Validate and save
    """

    def __init__(self, dream_date: Optional[date] = None, model: Optional[str] = None):
        _load_env()
        self.dream_date = dream_date or date.today()
        self.model = model or ARCHITECT_MODEL
        self.date_str = self.dream_date.isoformat()

        # Staging directory for today's data
        self.staging_dir = STAGING_BASE / self.date_str

        # Loaded data (populated by load_context)
        self.consolidation_report: Optional[str] = None
        self.emotional_digest: Optional[dict] = None
        self.new_information: Optional[str] = None
        self.unresolved_tensions: Optional[str] = None
        self.individuation_state: Optional[dict] = None
        self.previous_dream: Optional[dict] = None
        self.recurring_threads: Optional[dict] = None
        self.symbol_dict = SymbolDictionary()

        # Generated data
        self.selected_archetypes: list[dict] = []
        self.generated_symbols: list[dict] = []
        self.amplification_hints: list[str] = []

    def load_context(self) -> dict:
        """
        Load all context data for dream generation.

        Returns a summary dict of what was loaded.
        """
        loaded = {}

        # Load staging outputs
        if self.staging_dir.exists():
            # Try various file names that the v0.2 pipeline might produce
            for name in ["consolidation_report.txt", "consolidation_report.md",
                         "consolidation_report.json"]:
                text = _load_text(self.staging_dir / name)
                if text:
                    self.consolidation_report = text
                    loaded["consolidation_report"] = True
                    break

            # Emotional digest
            for name in ["emotional_digest.json", "emotional_digest.txt"]:
                path = self.staging_dir / name
                if path.suffix == ".json":
                    self.emotional_digest = _load_json(path)
                else:
                    text = _load_text(path)
                    if text:
                        self.emotional_digest = {"raw": text}
                if self.emotional_digest:
                    loaded["emotional_digest"] = True
                    break

            # New information
            for name in ["new_information.txt", "new_information.json",
                         "learned_today.txt"]:
                text = _load_text(self.staging_dir / name)
                if text:
                    self.new_information = text
                    loaded["new_information"] = True
                    break

            # Unresolved tensions
            for name in ["unresolved_tensions.txt", "tensions.txt",
                         "unresolved_tensions.json"]:
                text = _load_text(self.staging_dir / name)
                if text:
                    self.unresolved_tensions = text
                    loaded["unresolved_tensions"] = True
                    break
        else:
            log.warning("Staging directory not found: %s", self.staging_dir)

        # Load individuation state
        self.individuation_state = _load_json(INDIVIDUATION_PATH)
        if self.individuation_state:
            loaded["individuation_state"] = True

        # Load previous dream for continuity
        self.previous_dream = _find_previous_dream_log(self.dream_date)
        if self.previous_dream:
            loaded["previous_dream"] = True

        # Load recurring threads
        self.recurring_threads = _load_json(RECURRING_THREADS_PATH)
        if self.recurring_threads:
            loaded["recurring_threads"] = True

        log.info("Context loaded: %s", loaded)
        return loaded

    def select_dream_archetypes(self) -> list[dict]:
        """Select archetypes based on emotional digest and individuation state."""
        digest = self.emotional_digest or {}
        self.selected_archetypes = select_archetypes(
            digest,
            self.individuation_state,
            count=3,
        )
        log.info(
            "Selected archetypes: %s",
            [a["archetype_name"] for a in self.selected_archetypes],
        )
        return self.selected_archetypes

    def generate_dream_symbols(self) -> list[dict]:
        """Generate symbols from day events using condensation and displacement."""
        symbols = []

        # Condensation: compress day events
        events = []
        if self.consolidation_report:
            # Split report into event-like chunks
            for line in self.consolidation_report.split("\n"):
                line = line.strip()
                if line and len(line) > 10:
                    events.append(line)
        if events:
            symbol = condensation(events[:10])  # Cap at 10 events
            symbols.append(symbol)

        # Displacement: move emotional charges
        if self.emotional_digest:
            charges = []
            if isinstance(self.emotional_digest, dict):
                if "dominant_emotion" in self.emotional_digest:
                    charges.append(self.emotional_digest["dominant_emotion"])
                if "keywords" in self.emotional_digest:
                    charges.extend(self.emotional_digest["keywords"][:3])
            for charge in charges[:3]:
                event_desc = self.consolidation_report or "the events of the day"
                if len(event_desc) > 100:
                    event_desc = event_desc[:100]
                symbol = displacement(event_desc, charge)
                symbols.append(symbol)

        # Location from tensions
        if self.unresolved_tensions:
            for line in self.unresolved_tensions.split("\n")[:3]:
                line = line.strip()
                if line and len(line) > 5:
                    loc = generate_location_from_tension(line)
                    symbols.append(loc)

        # Amplification hints
        self.amplification_hints = []
        for sym in symbols:
            self.amplification_hints.extend(amplify_symbol(sym))

        # Record symbols in dictionary
        for sym in symbols:
            if "name" in sym:
                self.symbol_dict.record_symbol(sym, self.date_str)

        self.generated_symbols = symbols
        log.info("Generated %d symbols", len(symbols))
        return symbols

    def build_prompt(self) -> str:
        """Build the user prompt with all context data for the LLM."""
        sections = []

        sections.append(f"## Dream Date: {self.date_str}\n")

        # Today's data
        if self.consolidation_report:
            sections.append("## Today's Events (Consolidation Report)")
            # Truncate to avoid token limits
            report = self.consolidation_report
            if len(report) > 3000:
                report = report[:3000] + "\n[...truncated...]"
            sections.append(report)

        if self.emotional_digest:
            sections.append("## Emotional Digest")
            if isinstance(self.emotional_digest, dict):
                sections.append(json.dumps(self.emotional_digest, indent=2))
            else:
                sections.append(str(self.emotional_digest))

        if self.new_information:
            sections.append("## New Information Learned Today")
            info = self.new_information
            if len(info) > 1500:
                info = info[:1500] + "\n[...truncated...]"
            sections.append(info)

        if self.unresolved_tensions:
            sections.append("## Unresolved Tensions")
            sections.append(self.unresolved_tensions)

        # Individuation state
        if self.individuation_state:
            sections.append("## Individuation State")
            sections.append(json.dumps(self.individuation_state, indent=2))
        else:
            sections.append("## Individuation State")
            sections.append("No prior individuation record. This may be an early dream. Start with Shadow work.")

        # Archetype selection
        if self.selected_archetypes:
            sections.append("## Selected Archetypes (via compensation logic)")
            sections.append("The following archetypes were selected based on today's emotional profile. "
                          "Use these as the basis for NPCs:")
            for arch in self.selected_archetypes:
                sections.append(f"\n### {arch['archetype_name']} ({arch['jungian_name']})")
                sections.append(f"Score: {arch['compensation_score']:.1f}")
                sections.append(f"Description: {arch['description']}")
                sections.append(f"Behaviors: {', '.join(arch['typical_behaviors'])}")
                sections.append(f"Speech patterns: {'; '.join(arch['speech_patterns'][:2])}")
                sections.append(f"Manifestation hints: {'; '.join(arch['manifestation_hints'][:2])}")

        # Generated symbols
        if self.generated_symbols:
            sections.append("## Generated Dream Symbols")
            sections.append("Incorporate these symbols into the dreamscape:")
            for sym in self.generated_symbols:
                sections.append(f"- **{sym.get('name', 'unnamed')}**: {sym.get('description', '')}")
                if sym.get("associations"):
                    sections.append(f"  Associations: {', '.join(sym['associations'][:5])}")

        # Amplification hints
        if self.amplification_hints:
            sections.append("## Amplification Hints (mythological/cultural associations)")
            for hint in self.amplification_hints[:10]:
                sections.append(f"- {hint}")

        # Recurring symbols
        recurring = self.symbol_dict.get_recurring_symbols()
        if recurring:
            sections.append("## Recurring Symbols from Previous Dreams")
            for sym in recurring[:5]:
                sections.append(
                    f"- **{sym['name']}** (appeared {sym['count']}x, "
                    f"status: {sym['status']}): {sym['latest_meaning']}"
                )

        # Previous dream continuity
        if self.previous_dream:
            sections.append("## Previous Dream (for continuity)")
            prev_summary = json.dumps({
                k: self.previous_dream.get(k)
                for k in ["world", "initial_situation"]
                if k in self.previous_dream
            }, indent=2)
            if len(prev_summary) > 1500:
                prev_summary = prev_summary[:1500] + "\n..."
            sections.append(prev_summary)

        # Recurring threads
        if self.recurring_threads:
            sections.append("## Recurring Threads")
            threads_str = json.dumps(self.recurring_threads, indent=2)
            if len(threads_str) > 1000:
                threads_str = threads_str[:1000] + "\n..."
            sections.append(threads_str)

        return "\n\n".join(sections)

    def call_llm(self, prompt: str) -> str:
        """Call the LLM to generate the dream world config."""
        try:
            from litellm import completion
        except ImportError:
            raise ImportError(
                "litellm is required. Install with: pip install litellm"
            )

        log.info("Calling %s for dream generation", self.model)
        response = completion(
            model=self.model,
            messages=[
                {"role": "system", "content": ARCHITECT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=4096,
            temperature=0.85,
        )
        return response.choices[0].message.content.strip()

    def extract_json(self, response: str) -> dict:
        """Extract and parse JSON from the LLM response."""
        # Try direct parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to find JSON block (possibly wrapped in markdown)
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find the outermost { ... }
        brace_match = re.search(r'\{.*\}', response, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not extract valid JSON from LLM response:\n{response[:500]}")

    def validate_config(self, config: dict) -> list[str]:
        """
        Validate the dream_world_config against required schema.

        Returns a list of validation errors (empty if valid).
        """
        errors = []

        # Required top-level fields
        for field in ["world", "locations", "npcs", "memory_fragments"]:
            if field not in config:
                errors.append(f"Missing required field: {field}")

        # Memory fragments validation
        fragments = config.get("memory_fragments", [])
        if isinstance(fragments, list):
            if len(fragments) < 3:
                errors.append(f"Need 3-6 memory_fragments, got {len(fragments)}")
            for i, frag in enumerate(fragments):
                for field in ["source", "dream_version", "distortion_type"]:
                    if field not in frag:
                        errors.append(f"memory_fragments[{i}] missing {field}")

        if "world" in config:
            if "name" not in config["world"]:
                errors.append("world.name is required")

        # Locations validation
        locations = config.get("locations", [])
        if len(locations) < 4:
            errors.append(f"Need 4-7 locations, got {len(locations)}")
        elif len(locations) > 7:
            errors.append(f"Need 4-7 locations, got {len(locations)}")

        for i, loc in enumerate(locations):
            for field in ["name", "tile_type", "position"]:
                if field not in loc:
                    errors.append(f"locations[{i}] missing {field}")
            if "position" in loc:
                pos = loc["position"]
                if not isinstance(pos, list) or len(pos) != 2:
                    errors.append(f"locations[{i}].position must be [x, y]")

        # NPC validation
        npcs = config.get("npcs", [])
        if len(npcs) < 2:
            errors.append(f"Need 2-4 NPCs, got {len(npcs)}")
        elif len(npcs) > 4:
            errors.append(f"Need 2-4 NPCs, got {len(npcs)}")

        for i, npc in enumerate(npcs):
            for field in ["name", "vigor", "wit", "grace", "heart", "numen",
                         "personality_prompt"]:
                if field not in npc:
                    errors.append(f"npcs[{i}] missing {field}")

            # Attribute sum check
            attrs = ["vigor", "wit", "grace", "heart", "numen"]
            if all(a in npc for a in attrs):
                total = sum(npc[a] for a in attrs)
                if total != 30:
                    errors.append(
                        f"npcs[{i}] ({npc.get('name', '?')}): "
                        f"attributes sum to {total}, must be 30"
                    )

        # Leeloo validation
        if "leeloo" in config:
            leeloo = config["leeloo"]
            attrs = ["vigor", "wit", "grace", "heart", "numen"]
            if all(a in leeloo for a in attrs):
                total = sum(leeloo[a] for a in attrs)
                if total != 30:
                    errors.append(f"leeloo: attributes sum to {total}, must be 30")

        # Dream logic validation
        if "dream_logic" in config:
            dl = config["dream_logic"]
            intensity = dl.get("intensity", 0.7)
            if not (0.0 <= intensity <= 1.0):
                errors.append(f"dream_logic.intensity must be 0.0-1.0, got {intensity}")

        return errors

    def generate(self, output_path: Optional[Path] = None) -> dict:
        """
        Run the full dream generation pipeline.

        Args:
            output_path: Where to save the config. Defaults to staging dir.

        Returns:
            The generated dream_world_config dict.
        """
        log.info("Starting dream generation for %s", self.date_str)

        # 1. Load context
        loaded = self.load_context()
        log.info("Loaded context: %s", loaded)

        # 2. Select archetypes
        self.select_dream_archetypes()

        # 3. Generate symbols
        self.generate_dream_symbols()

        # 4. Build prompt
        prompt = self.build_prompt()
        log.info("Built prompt (%d chars)", len(prompt))

        # 5. Call LLM
        response = self.call_llm(prompt)
        log.info("Received LLM response (%d chars)", len(response))

        # 6. Extract JSON
        config = self.extract_json(response)

        # 7. Validate
        errors = self.validate_config(config)
        if errors:
            log.warning("Validation errors: %s", errors)
            # Try to fix common issues rather than failing
            config = self._attempt_fixes(config, errors)
            remaining_errors = self.validate_config(config)
            if remaining_errors:
                log.error("Unfixed validation errors: %s", remaining_errors)
                # Still save but log the issues

        # 8. Save
        if output_path is None:
            output_path = self.staging_dir / "dream_world_config.json"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(config, indent=2))
        log.info("Saved dream config to %s", output_path)

        # 9. Save updated symbol dictionary
        self.symbol_dict.save()

        return config

    def _attempt_fixes(self, config: dict, errors: list[str]) -> dict:
        """Attempt to fix common validation issues."""
        # Fix attribute sums
        for npc_list_key in ["npcs"]:
            for npc in config.get(npc_list_key, []):
                attrs = ["vigor", "wit", "grace", "heart", "numen"]
                if all(a in npc for a in attrs):
                    total = sum(npc[a] for a in attrs)
                    if total != 30:
                        # Scale attributes to sum to 30
                        if total > 0:
                            factor = 30.0 / total
                            for a in attrs:
                                npc[a] = max(1, round(npc[a] * factor))
                            # Fix rounding errors
                            diff = 30 - sum(npc[a] for a in attrs)
                            if diff != 0:
                                # Add/subtract from the highest attribute
                                max_attr = max(attrs, key=lambda a: npc[a])
                                npc[max_attr] += diff

        # Fix leeloo attributes (should always be canonical)
        if "leeloo" in config:
            config["leeloo"]["vigor"] = 4
            config["leeloo"]["wit"] = 8
            config["leeloo"]["grace"] = 5
            config["leeloo"]["heart"] = 8
            config["leeloo"]["numen"] = 5
            config["leeloo"]["backend"] = "hermes"

        return config


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """Run the dream architect from the command line."""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Dream Architect — generate dream worlds for Leeloo")
    parser.add_argument("--date", type=str, default=None,
                       help="Dream date (YYYY-MM-DD). Defaults to today.")
    parser.add_argument("--output", type=str, default=None,
                       help="Output path for dream_world_config.json")
    parser.add_argument("--model", type=str, default=None,
                       help=f"LLM model to use (default: {ARCHITECT_MODEL})")
    args = parser.parse_args()

    dream_date = date.fromisoformat(args.date) if args.date else date.today()
    output_path = Path(args.output) if args.output else None

    architect = DreamArchitect(dream_date=dream_date, model=args.model)
    config = architect.generate(output_path=output_path)

    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    main()
