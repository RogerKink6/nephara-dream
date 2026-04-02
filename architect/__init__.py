"""Dream Architect — designs Jungian dream worlds for Leeloo based on her waking day."""

from .archetypes import ARCHETYPE_TEMPLATES, select_archetypes
from .symbols import (
    condensation,
    displacement,
    generate_location_from_tension,
    SymbolDictionary,
)
from .dream_architect import DreamArchitect
from .individuation import (
    load_state as load_individuation_state,
    save_state as save_individuation_state,
    update_after_dream,
    get_stage_description,
    should_advance_stage,
    advance_stage,
    generate_monthly_synthesis,
)
from .dream_series import analyze_series, generate_report, SeriesAnalysis

__all__ = [
    "ARCHETYPE_TEMPLATES",
    "select_archetypes",
    "condensation",
    "displacement",
    "generate_location_from_tension",
    "SymbolDictionary",
    "DreamArchitect",
    "load_individuation_state",
    "save_individuation_state",
    "update_after_dream",
    "get_stage_description",
    "should_advance_stage",
    "advance_stage",
    "generate_monthly_synthesis",
    "analyze_series",
    "generate_report",
    "SeriesAnalysis",
]
