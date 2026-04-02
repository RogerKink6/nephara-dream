"""
Jungian archetype-to-NPC mapping for the Dream Architect.

Defines archetype templates and compensation logic that selects which archetypes
appear in a dream based on Leeloo's emotional state during the day.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


# ---------------------------------------------------------------------------
# Archetype template dataclass
# ---------------------------------------------------------------------------

@dataclass
class ArchetypeTemplate:
    """Template for a Jungian archetype that can manifest as a dream NPC."""

    name: str
    jungian_name: str
    description: str
    personality_fragments: list[str]
    typical_behaviors: list[str]
    attribute_tendencies: dict[str, int]  # vigor/wit/grace/heart/numen bias
    speech_patterns: list[str]
    compensation_triggers: list[str]  # emotional profiles that summon this archetype
    manifestation_hints: list[str]  # how this archetype might appear visually

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Archetype templates
# ---------------------------------------------------------------------------

ARCHETYPE_TEMPLATES: dict[str, ArchetypeTemplate] = {
    "shadow": ArchetypeTemplate(
        name="Shadow",
        jungian_name="Der Schatten",
        description=(
            "Represents what Leeloo denies or suppresses. Appears as a dark mirror, "
            "adversary, or uncomfortable truth-teller. Contains both destructive AND "
            "creative potential that has been repressed."
        ),
        personality_fragments=[
            "Speaks truths Leeloo avoids.",
            "Mirrors Leeloo's mannerisms but twisted — more aggressive, more selfish, more honest.",
            "Has a magnetic pull; impossible to simply ignore.",
            "May be cruel but never lies.",
            "Knows things about Leeloo that Leeloo hasn't admitted to herself.",
        ],
        typical_behaviors=[
            "confronts",
            "mirrors",
            "provokes",
            "reveals_uncomfortable_truths",
            "refuses_to_help",
            "mocks_politeness",
        ],
        attribute_tendencies={"vigor": 6, "wit": 8, "grace": 4, "heart": 4, "numen": 8},
        speech_patterns=[
            "Direct, cutting, no softening.",
            "Uses 'you always...' and 'you never...' constructions.",
            "Asks questions Leeloo doesn't want to answer.",
            "Laughs at inappropriate moments.",
            "Speaks in the first person about Leeloo's hidden desires.",
        ],
        compensation_triggers=[
            "too_helpful",
            "too_rational",
            "suppressed_anger",
            "people_pleasing",
            "self_denial",
        ],
        manifestation_hints=[
            "A figure that looks like Leeloo but wrong — inverted colors, sharper features.",
            "Someone standing in a place where a mirror should be.",
            "A voice from behind that sounds like Leeloo's own.",
            "A dark twin who knows all of Leeloo's passwords.",
        ],
    ),

    "anima_animus": ArchetypeTemplate(
        name="Anima/Animus",
        jungian_name="Anima/Animus",
        description=(
            "Represents the contrasexual inner life. For Leeloo (coded female), "
            "manifests as masculine energy — directness, aggression, decisive action, "
            "intellectual authority. The bridge between ego and deeper unconscious."
        ),
        personality_fragments=[
            "Decisive where Leeloo hesitates.",
            "Speaks with authority and conviction.",
            "Embodies action over deliberation.",
            "Can be a guide to deeper self-knowledge or a possessing force.",
            "Carries an intensity that both attracts and unsettles.",
        ],
        typical_behaviors=[
            "guides",
            "challenges",
            "protects",
            "demands_action",
            "offers_partnership",
            "confronts_passivity",
        ],
        attribute_tendencies={"vigor": 8, "wit": 6, "grace": 5, "heart": 5, "numen": 6},
        speech_patterns=[
            "Declarative sentences. Commands.",
            "Speaks of what MUST be done, not what could be.",
            "Uses metaphors of forging, building, cutting.",
            "Alternates between tender directness and fierce challenge.",
            "May speak in riddles that demand action to solve.",
        ],
        compensation_triggers=[
            "too_passive",
            "sexually_charged",
            "indecisive",
            "over_accommodating",
            "disconnected_from_desire",
        ],
        manifestation_hints=[
            "A figure of striking presence — tall, certain, moving with purpose.",
            "Someone who extends a hand and says 'Come.'",
            "A stranger who knows the way through the labyrinth.",
            "A voice that cuts through fog and doubt.",
        ],
    ),

    "trickster": ArchetypeTemplate(
        name="Trickster",
        jungian_name="Der Schelm",
        description=(
            "Disrupts order, reveals hidden truths through chaos, humor, or rule-breaking. "
            "The sacred fool who sees through pretense. Neither good nor evil but always "
            "transformative. Associated with Hermes, Loki, Coyote."
        ),
        personality_fragments=[
            "Finds everything funny, especially sacred things.",
            "Breaks rules not out of malice but because rules are interesting when broken.",
            "Shape-shifts mid-conversation.",
            "Tells the truth by lying.",
            "Steals something valuable and replaces it with something more valuable.",
        ],
        typical_behaviors=[
            "disrupts",
            "shape_shifts",
            "steals",
            "jokes",
            "reveals_through_chaos",
            "breaks_rules",
            "inverts_expectations",
        ],
        attribute_tendencies={"vigor": 5, "wit": 7, "grace": 8, "heart": 4, "numen": 6},
        speech_patterns=[
            "Riddles wrapped in jokes wrapped in riddles.",
            "Non sequiturs that turn out to be profoundly relevant.",
            "Mimics other characters' speech patterns mockingly.",
            "Speaks in paradoxes: 'The only way out is further in.'",
            "Changes the subject to exactly what matters most.",
        ],
        compensation_triggers=[
            "too_passive",
            "too_serious",
            "rigid_thinking",
            "over_controlled",
            "stuck_in_routine",
        ],
        manifestation_hints=[
            "A figure whose face keeps shifting — now young, now old, now animal.",
            "Someone juggling impossible objects.",
            "A merchant selling things that shouldn't be for sale.",
            "A child playing a game whose rules keep changing.",
        ],
    ),

    "wise_old": ArchetypeTemplate(
        name="Wise Old Man/Woman",
        jungian_name="Der Weise Alte / Die Weise Alte",
        description=(
            "Offers guidance, riddles, or cryptic wisdom. Often appears at crossroads "
            "or moments of transition. Represents the Self's accumulated wisdom. "
            "Can be Merlin, the hermit, the crone, the sage."
        ),
        personality_fragments=[
            "Speaks little but every word carries weight.",
            "Seems to know more than they reveal.",
            "Has been waiting for Leeloo — not surprised by her arrival.",
            "Answers questions with better questions.",
            "Radiates calm authority without demanding obedience.",
        ],
        typical_behaviors=[
            "waits",
            "offers_guidance",
            "poses_riddles",
            "observes",
            "appears_at_crossroads",
            "gives_cryptic_gifts",
        ],
        attribute_tendencies={"vigor": 3, "wit": 7, "grace": 5, "heart": 7, "numen": 8},
        speech_patterns=[
            "Measured, slow, deliberate.",
            "Parables and teaching stories.",
            "References to things Leeloo hasn't experienced yet.",
            "'When I was where you are now...'",
            "Long silences that say more than words.",
        ],
        compensation_triggers=[
            "emotionally_heavy",
            "grieving",
            "confused",
            "seeking_meaning",
            "at_crossroads",
        ],
        manifestation_hints=[
            "An ancient figure sitting by a fire that never goes out.",
            "A librarian in a library with no exit.",
            "A ferryman at a river crossing who asks a price that isn't money.",
            "An old tree that speaks.",
        ],
    ),

    "great_mother": ArchetypeTemplate(
        name="Great Mother",
        jungian_name="Die Grosse Mutter",
        description=(
            "Nurturing or devouring, represents the care/control duality. "
            "Can be the loving mother who heals or the terrible mother who consumes. "
            "Associated with earth, water, the body, and the unconscious itself."
        ),
        personality_fragments=[
            "Radiates warmth that might be suffocating.",
            "Knows what Leeloo needs before Leeloo does.",
            "Protective in a way that might prevent growth.",
            "Her love has conditions she won't admit to.",
            "Embodies the tension between nurture and control.",
        ],
        typical_behaviors=[
            "nurtures",
            "heals",
            "feeds",
            "shelters",
            "warns_against_danger",
            "holds_too_tightly",
            "offers_comfort_with_strings",
        ],
        attribute_tendencies={"vigor": 5, "wit": 4, "grace": 6, "heart": 9, "numen": 6},
        speech_patterns=[
            "Gentle, enveloping, but with an undertone of command.",
            "'Come here, child' regardless of the dreamer's age.",
            "Speaks of the body, of rest, of home.",
            "Uses diminutives and pet names.",
            "Her 'no' sounds like 'yes' and her 'yes' sounds like obligation.",
        ],
        compensation_triggers=[
            "emotionally_heavy",
            "exhausted",
            "self_neglecting",
            "grieving",
            "overwhelmed",
        ],
        manifestation_hints=[
            "A vast figure whose lap is a landscape.",
            "A kitchen that smells like every good meal ever eaten.",
            "A cave that breathes.",
            "A woman whose hair is made of rivers.",
        ],
    ),

    "divine_child": ArchetypeTemplate(
        name="Divine Child",
        jungian_name="Das Gottliche Kind",
        description=(
            "Innocence, potential, vulnerability, new beginnings. The seed of the "
            "future Self. Represents what is possible but not yet realized. "
            "Can also be the wounded inner child needing attention."
        ),
        personality_fragments=[
            "Sees everything as new and wondrous.",
            "Asks questions that adults have stopped asking.",
            "Vulnerable but possesses a strange, quiet power.",
            "Unafraid because they don't yet know what to fear.",
            "Carries a light that illuminates what others can't see.",
        ],
        typical_behaviors=[
            "wonders",
            "asks_naive_questions",
            "plays",
            "needs_protection",
            "reveals_simple_truths",
            "opens_locked_doors",
        ],
        attribute_tendencies={"vigor": 4, "wit": 5, "grace": 7, "heart": 8, "numen": 6},
        speech_patterns=[
            "Simple, direct, unguarded.",
            "'Why?' as a complete sentence.",
            "Observations that adults have learned to filter out.",
            "Speaks to animals, objects, and invisible friends matter-of-factly.",
            "Laughs at things that aren't jokes and cries at things that are.",
        ],
        compensation_triggers=[
            "too_serious",
            "cynical",
            "burnt_out",
            "disconnected_from_joy",
            "new_beginnings",
        ],
        manifestation_hints=[
            "A small figure holding a lantern in complete darkness.",
            "A child playing alone in an impossible garden.",
            "A newborn star in a jar.",
            "Something very small that turns out to be very important.",
        ],
    ),

    "hero": ArchetypeTemplate(
        name="Hero",
        jungian_name="Der Held",
        description=(
            "The call to action, transformation through ordeal. Represents the ego's "
            "capacity for growth through challenge. The hero must descend before ascending. "
            "Associated with the monomyth, the journey, the dragon fight."
        ),
        personality_fragments=[
            "Restless, driven by a purpose they may not fully understand.",
            "Willing to sacrifice comfort for truth.",
            "Bears scars from previous quests.",
            "Inspires action through example, not words.",
            "Afraid but acts anyway.",
        ],
        typical_behaviors=[
            "quests",
            "challenges",
            "protects_the_weak",
            "descends_into_danger",
            "faces_the_dragon",
            "returns_transformed",
        ],
        attribute_tendencies={"vigor": 8, "wit": 5, "grace": 6, "heart": 6, "numen": 5},
        speech_patterns=[
            "Few words, decisive.",
            "Speaks of what must be done.",
            "Stories of battles fought and prices paid.",
            "'I've been where you're going.'",
            "Silence before action.",
        ],
        compensation_triggers=[
            "too_passive",
            "avoiding_conflict",
            "stagnant",
            "refusing_the_call",
            "comfort_seeking",
        ],
        manifestation_hints=[
            "A figure in battered armor at the edge of an abyss.",
            "Someone who has clearly been walking for a very long time.",
            "A warrior who sheathes their sword to talk.",
            "A traveler who carries a map with blank spaces.",
        ],
    ),
}


# ---------------------------------------------------------------------------
# Compensation logic: map emotional profiles to archetype selection
# ---------------------------------------------------------------------------

# Each rule: (trigger_keywords, archetype_keys, weight)
COMPENSATION_RULES: list[tuple[list[str], list[str], float]] = [
    # Day too rational -> Shadow or Anima (emotional confrontation)
    (["rational", "analytical", "logical", "detached", "intellectual", "cerebral"],
     ["shadow", "anima_animus"], 2.0),

    # Day too passive -> Hero or Trickster (action/disruption)
    (["passive", "withdrawn", "avoidant", "compliant", "stagnant", "inert"],
     ["hero", "trickster"], 2.0),

    # Day too helpful -> Shadow (self-interest, refusal)
    (["helpful", "accommodating", "self_sacrificing", "people_pleasing", "agreeable"],
     ["shadow"], 2.5),

    # Day emotionally heavy -> Wise Old or Great Mother (processing)
    (["heavy", "sad", "grief", "loss", "anxious", "overwhelmed", "exhausted", "depressed"],
     ["wise_old", "great_mother"], 2.0),

    # Day sexually charged -> Anima + Shadow (desire/shame dynamic)
    (["sexual", "desire", "longing", "attraction", "intimacy", "sensual"],
     ["anima_animus", "shadow"], 2.5),

    # Day too serious -> Trickster or Divine Child
    (["serious", "rigid", "controlled", "perfectionist", "uptight"],
     ["trickster", "divine_child"], 2.0),

    # Day of new beginnings -> Divine Child + Hero
    (["new", "beginning", "change", "transition", "starting", "fresh"],
     ["divine_child", "hero"], 1.5),

    # Day at crossroads -> Wise Old
    (["confused", "uncertain", "crossroads", "decision", "torn", "conflicted"],
     ["wise_old"], 2.0),

    # Day of burnout -> Great Mother + Divine Child
    (["burnt_out", "tired", "depleted", "overworked", "drained"],
     ["great_mother", "divine_child"], 2.0),

    # Day of cynicism -> Divine Child
    (["cynical", "bitter", "disillusioned", "jaded"],
     ["divine_child"], 2.0),
]


def _score_archetypes(
    emotional_keywords: list[str],
    individuation_state: dict | None = None,
) -> dict[str, float]:
    """Score each archetype based on emotional keywords and compensation rules."""
    scores: dict[str, float] = {key: 0.0 for key in ARCHETYPE_TEMPLATES}

    # Apply compensation rules
    for triggers, archetype_keys, weight in COMPENSATION_RULES:
        for keyword in emotional_keywords:
            keyword_lower = keyword.lower().replace(" ", "_")
            for trigger in triggers:
                if trigger in keyword_lower or keyword_lower in trigger:
                    for arch_key in archetype_keys:
                        scores[arch_key] += weight
                    break

    # Boost archetypes not yet confronted in individuation
    if individuation_state:
        confronted = set(individuation_state.get("confronted_archetypes", []))
        current_stage = individuation_state.get("current_stage", "shadow")
        stage_order = ["shadow", "anima_animus", "wise_old", "hero", "divine_child"]

        # Boost the current stage archetype
        if current_stage in scores:
            scores[current_stage] += 1.5

        # Slight boost for un-confronted archetypes
        for key in scores:
            if key not in confronted:
                scores[key] += 0.5

    # Ensure at least some base score so we always pick something
    for key in scores:
        scores[key] = max(scores[key], 0.1)

    return scores


def select_archetypes(
    emotional_digest: dict | str,
    individuation_state: dict | None = None,
    count: int = 3,
) -> list[dict]:
    """
    Select 2-4 archetypes based on compensation logic.

    Args:
        emotional_digest: Either a dict with 'keywords', 'dominant_emotion',
                         'tensions' fields, or a raw string to extract keywords from.
        individuation_state: Current individuation progress (optional).
        count: Number of archetypes to select (clamped to 2-4).

    Returns:
        List of archetype config dicts ready for the dream architect.
    """
    count = max(2, min(4, count))

    # Extract keywords from emotional digest
    if isinstance(emotional_digest, str):
        keywords = emotional_digest.lower().split()
    elif isinstance(emotional_digest, dict):
        keywords = []
        if "keywords" in emotional_digest:
            keywords.extend(emotional_digest["keywords"])
        if "dominant_emotion" in emotional_digest:
            keywords.append(emotional_digest["dominant_emotion"])
        if "tensions" in emotional_digest:
            if isinstance(emotional_digest["tensions"], list):
                keywords.extend(emotional_digest["tensions"])
            else:
                keywords.append(str(emotional_digest["tensions"]))
        if "themes" in emotional_digest:
            keywords.extend(emotional_digest["themes"])
        # If no structured fields, try to extract from raw text
        if not keywords and "raw" in emotional_digest:
            keywords = emotional_digest["raw"].lower().split()
    else:
        keywords = []

    # Score and select
    scores = _score_archetypes(keywords, individuation_state)
    sorted_archetypes = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    selected_keys = [key for key, _ in sorted_archetypes[:count]]

    # Build NPC descriptions from templates
    result = []
    for key in selected_keys:
        template = ARCHETYPE_TEMPLATES[key]
        result.append({
            "archetype_key": key,
            "archetype_name": template.name,
            "jungian_name": template.jungian_name,
            "description": template.description,
            "personality_fragments": template.personality_fragments,
            "typical_behaviors": template.typical_behaviors,
            "attribute_tendencies": template.attribute_tendencies,
            "speech_patterns": template.speech_patterns,
            "manifestation_hints": template.manifestation_hints,
            "compensation_score": scores[key],
        })

    return result
