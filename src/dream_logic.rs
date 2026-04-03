//! Dream logic engine: makes the Nephara world behave like a dream with
//! fluid distances, scene shifts, emotional causality, transformations,
//! and time dilation. Only activates when a dream config with a `dream_logic`
//! section is loaded.

use rand::rngs::StdRng;
use rand::Rng;
use std::collections::HashMap;

use crate::dream_config::DreamLogicConfig;

// ---------------------------------------------------------------------------
// Dream phase — tracks where in the dream arc we are
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum DreamPhase {
    /// Early dream: more coherent, gentle strangeness
    Early,
    /// Middle dream: peak surrealism, strongest effects
    Middle,
    /// Late dream: resolving, clarity returns
    Late,
}

impl DreamPhase {
    /// Determine the phase from current tick and total ticks.
    pub fn from_progress(current_tick: u32, total_ticks: u32) -> Self {
        if total_ticks == 0 {
            return DreamPhase::Middle;
        }
        let progress = current_tick as f64 / total_ticks as f64;
        if progress < 0.25 {
            DreamPhase::Early
        } else if progress < 0.75 {
            DreamPhase::Middle
        } else {
            DreamPhase::Late
        }
    }

    /// Multiplier for dream effects based on phase (early=0.5, middle=1.0, late=0.6).
    pub fn intensity_multiplier(&self) -> f64 {
        match self {
            DreamPhase::Early  => 0.5,
            DreamPhase::Middle => 1.0,
            DreamPhase::Late   => 0.6,
        }
    }

    pub fn label(&self) -> &'static str {
        match self {
            DreamPhase::Early  => "early",
            DreamPhase::Middle => "middle",
            DreamPhase::Late   => "late",
        }
    }
}

// ---------------------------------------------------------------------------
// Emotion — detected from agent action text
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum DreamEmotion {
    Neutral,
    Fear,
    Joy,
    Confusion,
    Anger,
    Sadness,
    Wonder,
}

impl DreamEmotion {
    /// Detect dominant emotion from text using keyword matching.
    pub fn detect(text: &str) -> Self {
        let lower = text.to_lowercase();

        let fear_words = ["afraid", "fear", "scared", "terror", "dread", "panic", "horror", "nightmare", "dark", "shadow"];
        let joy_words = ["happy", "joy", "laugh", "smile", "delight", "cheerful", "bloom", "bright", "warm", "love", "beautiful"];
        let confusion_words = ["confused", "lost", "strange", "weird", "uncertain", "fog", "unclear", "puzzle", "maze", "wander"];
        let anger_words = ["angry", "rage", "furious", "hate", "frustrat", "bitter", "sharp", "loud", "storm"];
        let sadness_words = ["sad", "cry", "tears", "lonely", "grief", "sorrow", "melanchol", "miss", "loss"];
        let wonder_words = ["wonder", "amaz", "awe", "marvel", "curious", "discover", "magic", "shimmer", "glow"];

        let count = |words: &[&str]| -> usize {
            words.iter().filter(|w| lower.contains(*w)).count()
        };

        let scores = [
            (DreamEmotion::Fear,      count(&fear_words)),
            (DreamEmotion::Joy,       count(&joy_words)),
            (DreamEmotion::Confusion, count(&confusion_words)),
            (DreamEmotion::Anger,     count(&anger_words)),
            (DreamEmotion::Sadness,   count(&sadness_words)),
            (DreamEmotion::Wonder,    count(&wonder_words)),
        ];

        scores.iter()
            .max_by_key(|(_, c)| *c)
            .filter(|(_, c)| *c > 0)
            .map(|(e, _)| *e)
            .unwrap_or(DreamEmotion::Neutral)
    }
}

// ---------------------------------------------------------------------------
// Transformation record — tracks what changed
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct Transformation {
    pub tick: u32,
    pub description: String,
    /// If an NPC transformed: (original_appearance, new_appearance)
    pub npc_change: Option<(String, String)>,
    /// If a location detail changed
    pub location_change: Option<String>,
}

// ---------------------------------------------------------------------------
// DreamState — tracks the evolving dream state
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct DreamState {
    /// Current emotional temperature of the dream
    pub emotion: DreamEmotion,
    /// Current dream phase
    pub phase: DreamPhase,
    /// Total ticks for the simulation (used to compute phase)
    pub total_ticks: u32,
    /// Active symbols planted by the dream architect
    pub active_symbols: Vec<String>,
    /// Cooldown ticks remaining before next scene shift
    pub scene_shift_cooldown: u32,
    /// Log of transformations that have occurred
    pub transformations: Vec<Transformation>,
    /// Current time dilation factor (1.0 = normal)
    pub time_dilation_factor: f64,
    /// Narrative fragments from dream effects this tick
    pub tick_narratives: Vec<String>,
    /// Emotional atmosphere modifiers for world descriptions
    pub atmosphere_modifiers: Vec<String>,
    /// Warped distances: (location_name -> distance_multiplier)
    pub distance_warps: HashMap<String, f64>,
}

impl DreamState {
    pub fn new(total_ticks: u32) -> Self {
        DreamState {
            emotion: DreamEmotion::Neutral,
            phase: DreamPhase::Early,
            total_ticks,
            active_symbols: Vec::new(),
            scene_shift_cooldown: 3, // don't shift in first 3 ticks
            transformations: Vec::new(),
            time_dilation_factor: 1.0,
            tick_narratives: Vec::new(),
            atmosphere_modifiers: Vec::new(),
            distance_warps: HashMap::new(),
        }
    }

    /// Update the dream phase based on current tick.
    pub fn update_phase(&mut self, current_tick: u32) {
        self.phase = DreamPhase::from_progress(current_tick, self.total_ticks);
    }

    /// Clear per-tick narratives. Call at the start of each tick.
    pub fn begin_tick(&mut self) {
        self.tick_narratives.clear();
        self.atmosphere_modifiers.clear();
        self.distance_warps.clear();
    }
}

// ---------------------------------------------------------------------------
// Fluid distances
// ---------------------------------------------------------------------------

/// Warp the effective distance between positions based on dream state.
/// Returns a multiplier for the distance (< 1.0 = closer, > 1.0 = farther).
pub fn fluid_distance_multiplier(
    config: &DreamLogicConfig,
    state: &DreamState,
    _from: (u8, u8),
    _to: (u8, u8),
    rng: &mut StdRng,
) -> f64 {
    let fluidity = config.distance_fluidity;
    let phase_mult = state.phase.intensity_multiplier();
    let effective_fluidity = fluidity * config.intensity * phase_mult;

    // Base warp: random fluctuation scaled by fluidity
    let warp = 1.0 + (rng.gen::<f64>() - 0.5) * 2.0 * effective_fluidity;

    // Emotional influence on distance
    let emotion_factor = match state.emotion {
        DreamEmotion::Fear => 0.7,      // fear pulls things closer (nightmares close in)
        DreamEmotion::Joy => 0.9,       // joy makes things feel accessible
        DreamEmotion::Confusion => 1.3, // confusion stretches distances
        DreamEmotion::Anger => 1.1,     // anger pushes things away slightly
        DreamEmotion::Sadness => 1.2,   // sadness creates distance
        DreamEmotion::Wonder => 0.8,    // wonder draws things near
        DreamEmotion::Neutral => 1.0,
    };

    (warp * emotion_factor).clamp(0.3, 3.0)
}

/// Apply fluid distances to determine if a movement target feels closer or farther.
/// Returns adjusted Chebyshev distance.
pub fn warp_distance(
    config: &DreamLogicConfig,
    state: &DreamState,
    from: (u8, u8),
    to: (u8, u8),
    actual_distance: u32,
    rng: &mut StdRng,
) -> u32 {
    let mult = fluid_distance_multiplier(config, state, from, to, rng);
    let warped = (actual_distance as f64 * mult).round() as u32;
    warped.max(1) // minimum distance of 1
}

// ---------------------------------------------------------------------------
// Scene shift
// ---------------------------------------------------------------------------

/// Scene transition narratives for abrupt dream shifts.
const SCENE_TRANSITIONS: &[&str] = &[
    "The walls dissolve like watercolors in rain, and you find yourself somewhere else entirely...",
    "The ground beneath you shifts — reality folds — and suddenly the scene is different.",
    "A door appears where there was none. You step through without thinking.",
    "The air shimmers, and between one breath and the next, everything changes.",
    "You blink, and the world has rearranged itself around you.",
    "Shadows pool and surge, carrying you to a new place like a tide of darkness.",
    "The edges of everything blur, and when clarity returns, you are elsewhere.",
    "A sudden wind carries you — not through space, but through the dream itself.",
    "The dream stutters like a skipping record, and resumes in a different key.",
    "You feel yourself pulled sideways through layers of reality, landing softly in a new scene.",
];

/// Check if a scene shift should occur this tick. Returns the narrative transition
/// text and a target location index if a shift is triggered.
pub fn check_scene_shift(
    config: &DreamLogicConfig,
    state: &mut DreamState,
    current_tick: u32,
    num_locations: usize,
    current_location_idx: usize,
    rng: &mut StdRng,
) -> Option<(String, usize)> {
    // Respect cooldown
    if state.scene_shift_cooldown > 0 {
        state.scene_shift_cooldown -= 1;
        return None;
    }

    let phase_mult = state.phase.intensity_multiplier();
    let effective_chance = config.scene_shift_chance * config.intensity * phase_mult;

    if rng.gen::<f64>() >= effective_chance {
        return None;
    }

    // Pick a random different location
    if num_locations <= 1 {
        return None;
    }
    let mut target = rng.gen_range(0..num_locations);
    if target == current_location_idx {
        target = (target + 1) % num_locations;
    }

    // Set cooldown (3-6 ticks)
    state.scene_shift_cooldown = rng.gen_range(3..=6);

    let transition = SCENE_TRANSITIONS[rng.gen_range(0..SCENE_TRANSITIONS.len())];
    let narrative = format!("[DREAM SHIFT — Tick {}] {}", current_tick, transition);
    state.tick_narratives.push(narrative.clone());

    Some((narrative, target))
}

// ---------------------------------------------------------------------------
// Emotional causality
// ---------------------------------------------------------------------------

/// Atmosphere descriptions based on emotion.
pub fn emotional_atmosphere(emotion: DreamEmotion, phase: DreamPhase, rng: &mut StdRng) -> Vec<String> {
    let mut descriptors = Vec::new();

    match emotion {
        DreamEmotion::Fear => {
            let options = [
                "Shadows deepen at the edges of your vision.",
                "The air grows cold and heavy with unspoken dread.",
                "Every surface seems to absorb light, leaving only darkness.",
                "Something watches from just beyond the corner of your eye.",
                "The ground feels unstable, as if it might swallow you.",
            ];
            descriptors.push(options[rng.gen_range(0..options.len())].to_string());
        }
        DreamEmotion::Joy => {
            let options = [
                "Colors bloom brighter, as if the world responds to your happiness.",
                "Flowers spring from cracks in the ground, petals warm as sunlight.",
                "The air sparkles with motes of golden light.",
                "Everything feels closer, warmer, more alive.",
                "Music seems to drift from nowhere and everywhere at once.",
            ];
            descriptors.push(options[rng.gen_range(0..options.len())].to_string());
        }
        DreamEmotion::Confusion => {
            let options = [
                "A thick fog rolls in, obscuring familiar landmarks.",
                "Distances seem to shift — what was near feels far, and vice versa.",
                "The architecture makes no logical sense, yet feels inevitable.",
                "Signs point in contradictory directions, all of them somehow correct.",
                "Your memories of arriving here are hazy and uncertain.",
            ];
            descriptors.push(options[rng.gen_range(0..options.len())].to_string());
        }
        DreamEmotion::Anger => {
            let options = [
                "The sky flushes red at the edges, like a bruise forming.",
                "Surfaces feel sharp to the touch, edges more defined.",
                "The air crackles with a tension that makes your skin prickle.",
                "Sounds are too loud, too close, too much.",
                "The ground trembles faintly, responding to your fury.",
            ];
            descriptors.push(options[rng.gen_range(0..options.len())].to_string());
        }
        DreamEmotion::Sadness => {
            let options = [
                "A gentle rain begins to fall, though the sky shows no clouds.",
                "Colors drain to watercolor pastels, soft and fading.",
                "The world feels quieter, as if holding its breath for you.",
                "Echoes seem to linger longer, like the dream doesn't want to let go.",
                "Puddles form that reflect not the sky, but memories.",
            ];
            descriptors.push(options[rng.gen_range(0..options.len())].to_string());
        }
        DreamEmotion::Wonder => {
            let options = [
                "The air hums with possibility, thick with unborn miracles.",
                "Light bends in impossible ways, creating rainbows in shadows.",
                "Everything feels significant — even the smallest detail carries meaning.",
                "The boundaries between things soften, as if reality is more suggestion than law.",
                "Stars appear in places stars should not be — in puddles, in cracks, in eyes.",
            ];
            descriptors.push(options[rng.gen_range(0..options.len())].to_string());
        }
        DreamEmotion::Neutral => {
            // Mild dream atmosphere even when neutral
            let options = [
                "The air feels thick with meaning, though you cannot say why.",
                "Shadows move at the edge of your vision, never quite resolving.",
                "The dream holds steady, a quiet current beneath the surface.",
            ];
            if rng.gen::<f64>() < 0.5 {
                descriptors.push(options[rng.gen_range(0..options.len())].to_string());
            }
        }
    }

    // Phase-specific atmosphere
    match phase {
        DreamPhase::Early => {
            if rng.gen::<f64>() < 0.3 {
                descriptors.push("The dream is still forming — shapes are soft, sounds muffled.".to_string());
            }
        }
        DreamPhase::Middle => {
            if rng.gen::<f64>() < 0.4 {
                let options = [
                    "The dream is at its deepest now — reality bends like light through water.",
                    "This is the heart of the dream, where anything feels possible.",
                    "The boundary between real and unreal has dissolved completely.",
                ];
                descriptors.push(options[rng.gen_range(0..options.len())].to_string());
            }
        }
        DreamPhase::Late => {
            if rng.gen::<f64>() < 0.3 {
                let options = [
                    "The edges of the dream are fraying — clarity seeps in like dawn.",
                    "You sense the dream thinning, as if waking lurks just beyond.",
                    "Things feel more solid now, more certain — the dream is resolving.",
                ];
                descriptors.push(options[rng.gen_range(0..options.len())].to_string());
            }
        }
    }

    descriptors
}

// ---------------------------------------------------------------------------
// Transformations
// ---------------------------------------------------------------------------

/// NPC appearance fragments for dream transformations.
const NPC_TRANSFORM_DESCRIPTIONS: &[&str] = &[
    "their face flickers, becoming someone else for a moment",
    "their voice changes pitch and timbre, as if speaking from a different life",
    "their shadow moves independently, taking a different shape",
    "they seem taller, or shorter — you can't quite remember which they were before",
    "their eyes reflect a scene that isn't here",
    "for a heartbeat, they look exactly like someone from your past",
    "their clothes shift color and style between blinks",
    "they speak, but the words arrive before their lips move",
];

/// Object/location transformation descriptions.
const OBJECT_TRANSFORM_DESCRIPTIONS: &[&str] = &[
    "A book on a nearby surface unfolds into a bird and flies away.",
    "The walls breathe — expanding and contracting almost imperceptibly.",
    "A doorway that was there a moment ago has become a mirror.",
    "The floor beneath you ripples like water before solidifying again.",
    "A nearby object changes material — wood becomes glass, glass becomes stone.",
    "Symbols appear on surfaces, glowing briefly before fading.",
    "A painting on the wall changes its scene when you look back at it.",
    "The ceiling opens briefly to reveal stars, then seals itself.",
];

/// Check if a transformation should occur this tick.
/// Returns a Transformation record if triggered.
pub fn check_transformation(
    config: &DreamLogicConfig,
    state: &mut DreamState,
    current_tick: u32,
    npc_names: &[String],
    rng: &mut StdRng,
) -> Option<Transformation> {
    let phase_mult = state.phase.intensity_multiplier();
    let effective_chance = config.transformation_chance * config.intensity * phase_mult;

    if rng.gen::<f64>() >= effective_chance {
        return None;
    }

    // Decide: NPC transformation or object transformation
    let is_npc_transform = !npc_names.is_empty() && rng.gen::<f64>() < 0.4;

    let transformation = if is_npc_transform {
        let npc = &npc_names[rng.gen_range(0..npc_names.len())];
        let desc = NPC_TRANSFORM_DESCRIPTIONS[rng.gen_range(0..NPC_TRANSFORM_DESCRIPTIONS.len())];
        Transformation {
            tick: current_tick,
            description: format!("[DREAM TRANSFORM — Tick {}] {} — {}", current_tick, npc, desc),
            npc_change: Some((npc.clone(), desc.to_string())),
            location_change: None,
        }
    } else {
        let desc = OBJECT_TRANSFORM_DESCRIPTIONS[rng.gen_range(0..OBJECT_TRANSFORM_DESCRIPTIONS.len())];
        Transformation {
            tick: current_tick,
            description: format!("[DREAM TRANSFORM — Tick {}] {}", current_tick, desc),
            npc_change: None,
            location_change: Some(desc.to_string()),
        }
    };

    state.tick_narratives.push(transformation.description.clone());
    state.transformations.push(transformation.clone());
    Some(transformation)
}

// ---------------------------------------------------------------------------
// Time dilation
// ---------------------------------------------------------------------------

/// Time dilation narratives.
const TIME_SLOW_NARRATIVES: &[&str] = &[
    "Time stretches like warm taffy — each moment expands to contain lifetimes.",
    "The seconds drag, thick and heavy, as if the dream wants to hold this moment.",
    "Time slows to a crawl; you can count individual dust motes in the air.",
    "Hours seem to pass in what must be minutes. Or is it the other way around?",
];

const TIME_FAST_NARRATIVES: &[&str] = &[
    "Time lurches forward — moments blur together in a rushing stream.",
    "The dream fast-forwards, scenes flickering past like pages in a wind.",
    "Between one breath and the next, time has leapt ahead.",
    "Everything accelerates — the world moves at double speed around you.",
];

/// Calculate time dilation factor for this tick and return a narrative if notable.
pub fn apply_time_dilation(
    config: &DreamLogicConfig,
    state: &mut DreamState,
    rng: &mut StdRng,
) -> Option<String> {
    let td = match &config.time_dilation {
        Some(td) if td.enabled => td,
        _ => {
            state.time_dilation_factor = 1.0;
            return None;
        }
    };

    let phase_mult = state.phase.intensity_multiplier();
    let range = td.max_factor - td.min_factor;
    let factor = td.min_factor + rng.gen::<f64>() * range;

    // Blend toward normal based on phase (early/late are more stable)
    let blended = 1.0 + (factor - 1.0) * phase_mult * config.intensity;
    state.time_dilation_factor = blended;

    // Only narrate significant dilation
    if blended < 0.7 {
        let narrative = TIME_SLOW_NARRATIVES[rng.gen_range(0..TIME_SLOW_NARRATIVES.len())];
        let text = format!("[TIME DILATION] {}", narrative);
        state.tick_narratives.push(text.clone());
        Some(text)
    } else if blended > 1.5 {
        let narrative = TIME_FAST_NARRATIVES[rng.gen_range(0..TIME_FAST_NARRATIVES.len())];
        let text = format!("[TIME DILATION] {}", narrative);
        state.tick_narratives.push(text.clone());
        Some(text)
    } else {
        None
    }
}

// ---------------------------------------------------------------------------
// Dream perception prompt additions
// ---------------------------------------------------------------------------

/// Build a dream-specific perception block to inject into agent prompts.
pub fn build_dream_perception(
    config: &DreamLogicConfig,
    state: &DreamState,
) -> String {
    if config.intensity < 0.01 {
        return String::new();
    }

    let mut lines = Vec::new();
    lines.push("SURROUNDINGS:".to_string());

    if state.emotion != DreamEmotion::Neutral {
        lines.push(format!("  Emotional atmosphere: {:?}", state.emotion));
    }

    if state.time_dilation_factor < 0.8 || state.time_dilation_factor > 1.2 {
        if state.time_dilation_factor < 1.0 {
            lines.push("  Time feels stretched and slow.".to_string());
        } else {
            lines.push("  Time rushes forward in lurching bursts.".to_string());
        }
    }

    // Add atmosphere modifiers
    for modifier in &state.atmosphere_modifiers {
        lines.push(format!("  {}", modifier));
    }

    // Add recent transformations (last 2)
    let recent_transforms: Vec<&Transformation> = state.transformations.iter().rev().take(2).collect();
    if !recent_transforms.is_empty() {
        lines.push("  Recent shifts:".to_string());
        for t in recent_transforms {
            lines.push(format!("    - {}", t.description));
        }
    }



    format!("\n{}\n", lines.join("\n"))
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use rand::SeedableRng;

    fn test_config() -> DreamLogicConfig {
        DreamLogicConfig {
            intensity: 0.7,
            scene_shift_chance: 0.15,
            distance_fluidity: 0.5,
            emotional_causality: true,
            transformation_chance: 0.1,
            time_dilation: Some(crate::dream_config::TimeDilationConfig {
                enabled: true,
                min_factor: 0.5,
                max_factor: 2.0,
            }),
        }
    }

    #[test]
    fn test_dream_phase_progression() {
        assert_eq!(DreamPhase::from_progress(0, 100), DreamPhase::Early);
        assert_eq!(DreamPhase::from_progress(10, 100), DreamPhase::Early);
        assert_eq!(DreamPhase::from_progress(30, 100), DreamPhase::Middle);
        assert_eq!(DreamPhase::from_progress(50, 100), DreamPhase::Middle);
        assert_eq!(DreamPhase::from_progress(80, 100), DreamPhase::Late);
        assert_eq!(DreamPhase::from_progress(99, 100), DreamPhase::Late);
    }

    #[test]
    fn test_emotion_detection() {
        assert_eq!(DreamEmotion::detect("I feel afraid of the shadows"), DreamEmotion::Fear);
        assert_eq!(DreamEmotion::detect("I am happy and delighted"), DreamEmotion::Joy);
        assert_eq!(DreamEmotion::detect("I am confused and lost in a maze"), DreamEmotion::Confusion);
        assert_eq!(DreamEmotion::detect("I am furious and full of rage"), DreamEmotion::Anger);
        assert_eq!(DreamEmotion::detect("I feel sad tears of grief"), DreamEmotion::Sadness);
        assert_eq!(DreamEmotion::detect("I wonder at the amazing discovery"), DreamEmotion::Wonder);
        assert_eq!(DreamEmotion::detect("I walk to the store"), DreamEmotion::Neutral);
    }

    #[test]
    fn test_fluid_distance_in_range() {
        let config = test_config();
        let state = DreamState::new(100);
        let mut rng = StdRng::seed_from_u64(42);

        for _ in 0..100 {
            let mult = fluid_distance_multiplier(&config, &state, (5, 5), (10, 10), &mut rng);
            assert!(mult >= 0.3 && mult <= 3.0, "multiplier {} out of range", mult);
        }
    }

    #[test]
    fn test_scene_shift_respects_cooldown() {
        let config = test_config();
        let mut state = DreamState::new(100);
        let mut rng = StdRng::seed_from_u64(42);

        state.scene_shift_cooldown = 5;
        let result = check_scene_shift(&config, &mut state, 10, 5, 0, &mut rng);
        assert!(result.is_none());
        assert_eq!(state.scene_shift_cooldown, 4);
    }

    #[test]
    fn test_transformation_records() {
        let config = DreamLogicConfig {
            intensity: 1.0,
            transformation_chance: 1.0, // force trigger
            ..test_config()
        };
        let mut state = DreamState::new(100);
        state.phase = DreamPhase::Middle;
        let mut rng = StdRng::seed_from_u64(42);

        let names = vec!["Vesper".to_string(), "Ondra".to_string()];
        let result = check_transformation(&config, &mut state, 5, &names, &mut rng);
        assert!(result.is_some());
        assert!(!state.transformations.is_empty());
    }

    #[test]
    fn test_time_dilation_range() {
        let config = test_config();
        let mut state = DreamState::new(100);
        state.phase = DreamPhase::Middle;
        let mut rng = StdRng::seed_from_u64(42);

        for _ in 0..100 {
            apply_time_dilation(&config, &mut state, &mut rng);
            assert!(state.time_dilation_factor >= 0.0 && state.time_dilation_factor <= 5.0,
                "time factor {} out of range", state.time_dilation_factor);
        }
    }

    #[test]
    fn test_zero_intensity_no_effects() {
        let config = DreamLogicConfig {
            intensity: 0.0,
            ..test_config()
        };
        let state = DreamState::new(100);
        let perception = build_dream_perception(&config, &state);
        assert!(perception.is_empty());
    }

    // -----------------------------------------------------------------------
    // Phase 1 audit: additional dream logic tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_dream_phase_zero_total_ticks() {
        // Edge case: total_ticks == 0 should return Middle
        assert_eq!(DreamPhase::from_progress(0, 0), DreamPhase::Middle);
        assert_eq!(DreamPhase::from_progress(50, 0), DreamPhase::Middle);
    }

    #[test]
    fn test_dream_phase_boundary_values() {
        // Exactly at boundaries
        assert_eq!(DreamPhase::from_progress(24, 100), DreamPhase::Early);  // 0.24 < 0.25
        assert_eq!(DreamPhase::from_progress(25, 100), DreamPhase::Middle); // 0.25 >= 0.25
        assert_eq!(DreamPhase::from_progress(74, 100), DreamPhase::Middle); // 0.74 < 0.75
        assert_eq!(DreamPhase::from_progress(75, 100), DreamPhase::Late);   // 0.75 >= 0.75
    }

    #[test]
    fn test_dream_phase_intensity_multiplier() {
        assert!((DreamPhase::Early.intensity_multiplier() - 0.5).abs() < f64::EPSILON);
        assert!((DreamPhase::Middle.intensity_multiplier() - 1.0).abs() < f64::EPSILON);
        assert!((DreamPhase::Late.intensity_multiplier() - 0.6).abs() < f64::EPSILON);
    }

    #[test]
    fn test_dream_phase_labels() {
        assert_eq!(DreamPhase::Early.label(), "early");
        assert_eq!(DreamPhase::Middle.label(), "middle");
        assert_eq!(DreamPhase::Late.label(), "late");
    }

    #[test]
    fn test_emotional_causality_different_emotions_different_output() {
        let mut rng = StdRng::seed_from_u64(42);
        let phase = DreamPhase::Middle;

        let fear_atmo = emotional_atmosphere(DreamEmotion::Fear, phase, &mut rng);
        let mut rng2 = StdRng::seed_from_u64(42);
        let joy_atmo = emotional_atmosphere(DreamEmotion::Joy, phase, &mut rng2);

        // Fear and Joy should produce different descriptions
        assert!(!fear_atmo.is_empty(), "Fear should produce atmosphere");
        assert!(!joy_atmo.is_empty(), "Joy should produce atmosphere");
        assert_ne!(fear_atmo[0], joy_atmo[0], "Fear and Joy atmospheres should differ");
    }

    #[test]
    fn test_emotional_atmosphere_all_emotions_produce_output() {
        let emotions = [
            DreamEmotion::Fear,
            DreamEmotion::Joy,
            DreamEmotion::Confusion,
            DreamEmotion::Anger,
            DreamEmotion::Sadness,
            DreamEmotion::Wonder,
        ];
        for emotion in &emotions {
            let mut rng = StdRng::seed_from_u64(42);
            let atmo = emotional_atmosphere(*emotion, DreamPhase::Middle, &mut rng);
            assert!(!atmo.is_empty(), "{:?} should produce at least one atmosphere descriptor", emotion);
        }
    }

    #[test]
    fn test_scene_shift_deterministic_with_seed() {
        let config = DreamLogicConfig {
            intensity: 1.0,
            scene_shift_chance: 1.0, // force trigger
            ..test_config()
        };
        let mut state1 = DreamState::new(100);
        state1.scene_shift_cooldown = 0;
        state1.phase = DreamPhase::Middle;
        let mut rng1 = StdRng::seed_from_u64(123);

        let mut state2 = DreamState::new(100);
        state2.scene_shift_cooldown = 0;
        state2.phase = DreamPhase::Middle;
        let mut rng2 = StdRng::seed_from_u64(123);

        let result1 = check_scene_shift(&config, &mut state1, 5, 5, 0, &mut rng1);
        let result2 = check_scene_shift(&config, &mut state2, 5, 5, 0, &mut rng2);

        assert_eq!(result1.is_some(), result2.is_some(), "same seed should give same result");
        if let (Some((narr1, idx1)), Some((narr2, idx2))) = (&result1, &result2) {
            assert_eq!(narr1, narr2, "same seed should give same narrative");
            assert_eq!(idx1, idx2, "same seed should give same target index");
        }
    }

    #[test]
    fn test_scene_shift_single_location_returns_none() {
        let config = DreamLogicConfig {
            intensity: 1.0,
            scene_shift_chance: 1.0,
            ..test_config()
        };
        let mut state = DreamState::new(100);
        state.scene_shift_cooldown = 0;
        state.phase = DreamPhase::Middle;
        let mut rng = StdRng::seed_from_u64(42);

        // Only 1 location means we can't shift to a different one
        let result = check_scene_shift(&config, &mut state, 1, 1, 0, &mut rng);
        assert!(result.is_none(), "scene shift with 1 location should return None");
    }

    #[test]
    fn test_transformation_produces_valid_output() {
        let config = DreamLogicConfig {
            intensity: 1.0,
            transformation_chance: 1.0,
            ..test_config()
        };
        let mut state = DreamState::new(100);
        state.phase = DreamPhase::Middle;
        let mut rng = StdRng::seed_from_u64(42);

        let names = vec!["Alice".to_string(), "Bob".to_string()];
        let result = check_transformation(&config, &mut state, 10, &names, &mut rng);
        assert!(result.is_some(), "forced transformation should produce result");
        let t = result.unwrap();
        assert!(t.description.contains("DREAM TRANSFORM"), "description should contain DREAM TRANSFORM marker");
        assert!(t.tick == 10);
        // Either NPC or object transform
        assert!(t.npc_change.is_some() || t.location_change.is_some(),
            "transformation should have either npc_change or location_change");
    }

    #[test]
    fn test_transformation_with_no_npcs_is_always_object() {
        let config = DreamLogicConfig {
            intensity: 1.0,
            transformation_chance: 1.0,
            ..test_config()
        };
        let mut state = DreamState::new(100);
        state.phase = DreamPhase::Middle;
        let mut rng = StdRng::seed_from_u64(42);

        let result = check_transformation(&config, &mut state, 5, &[], &mut rng);
        assert!(result.is_some());
        let t = result.unwrap();
        assert!(t.npc_change.is_none(), "with no NPCs, should be object transform");
        assert!(t.location_change.is_some());
    }

    #[test]
    fn test_dream_state_new_initializes_correctly() {
        let state = DreamState::new(50);
        assert_eq!(state.total_ticks, 50);
        assert_eq!(state.emotion, DreamEmotion::Neutral);
        assert_eq!(state.phase, DreamPhase::Early);
        assert_eq!(state.scene_shift_cooldown, 3);
        assert!(state.transformations.is_empty());
        assert!((state.time_dilation_factor - 1.0).abs() < f64::EPSILON);
        assert!(state.tick_narratives.is_empty());
        assert!(state.atmosphere_modifiers.is_empty());
        assert!(state.distance_warps.is_empty());
    }

    #[test]
    fn test_dream_state_begin_tick_clears() {
        let mut state = DreamState::new(100);
        state.tick_narratives.push("test".to_string());
        state.atmosphere_modifiers.push("mod".to_string());
        state.distance_warps.insert("loc".to_string(), 1.5);

        state.begin_tick();

        assert!(state.tick_narratives.is_empty());
        assert!(state.atmosphere_modifiers.is_empty());
        assert!(state.distance_warps.is_empty());
    }

    #[test]
    fn test_dream_state_update_phase() {
        let mut state = DreamState::new(100);
        state.update_phase(10);
        assert_eq!(state.phase, DreamPhase::Early);
        state.update_phase(50);
        assert_eq!(state.phase, DreamPhase::Middle);
        state.update_phase(80);
        assert_eq!(state.phase, DreamPhase::Late);
    }

    #[test]
    fn test_warp_distance_minimum_one() {
        let config = test_config();
        let state = DreamState::new(100);
        let mut rng = StdRng::seed_from_u64(42);

        // Even with actual_distance = 0, result should be >= 1
        let result = warp_distance(&config, &state, (0, 0), (0, 0), 0, &mut rng);
        assert!(result >= 1, "warped distance should be at least 1, got {}", result);
    }

    #[test]
    fn test_time_dilation_disabled() {
        let config = DreamLogicConfig {
            time_dilation: None,
            ..test_config()
        };
        let mut state = DreamState::new(100);
        let mut rng = StdRng::seed_from_u64(42);

        let result = apply_time_dilation(&config, &mut state, &mut rng);
        assert!(result.is_none(), "disabled time dilation should produce None");
        assert!((state.time_dilation_factor - 1.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_build_dream_perception_includes_phase() {
        let config = test_config();
        let mut state = DreamState::new(100);
        state.phase = DreamPhase::Middle;

        let perception = build_dream_perception(&config, &state);
        assert!(perception.contains("SURROUNDINGS:"), "perception should contain SURROUNDINGS header");
    }

    #[test]
    fn test_build_dream_perception_includes_emotion() {
        let config = test_config();
        let mut state = DreamState::new(100);
        state.emotion = DreamEmotion::Fear;

        let perception = build_dream_perception(&config, &state);
        assert!(perception.contains("Fear"), "perception should mention Fear emotion");
    }

    #[test]
    fn test_build_dream_perception_includes_time_dilation() {
        let config = test_config();
        let mut state = DreamState::new(100);
        state.time_dilation_factor = 0.5; // very slow

        let perception = build_dream_perception(&config, &state);
        assert!(perception.contains("Time feels stretched"), "perception should describe slow time");
    }

    #[test]
    fn test_build_dream_perception_includes_recent_transforms() {
        let config = test_config();
        let mut state = DreamState::new(100);
        state.transformations.push(Transformation {
            tick: 5,
            description: "A test transformation occurred".to_string(),
            npc_change: None,
            location_change: Some("test".to_string()),
        });

        let perception = build_dream_perception(&config, &state);
        assert!(perception.contains("Recent shifts"), "perception should include recent transforms");
        assert!(perception.contains("A test transformation occurred"));
    }

    #[test]
    fn test_emotion_detect_mixed_signals_picks_strongest() {
        // Text with multiple emotion words — should pick the one with most matches
        let text = "I feel afraid, dread fills me with terror and panic in the dark shadows";
        assert_eq!(DreamEmotion::detect(text), DreamEmotion::Fear);
    }

    #[test]
    fn test_fluid_distance_emotion_affects_multiplier() {
        let config = test_config();
        let mut rng1 = StdRng::seed_from_u64(99);
        let mut rng2 = StdRng::seed_from_u64(99);

        let mut state_fear = DreamState::new(100);
        state_fear.emotion = DreamEmotion::Fear;
        state_fear.phase = DreamPhase::Middle;

        let mut state_confusion = DreamState::new(100);
        state_confusion.emotion = DreamEmotion::Confusion;
        state_confusion.phase = DreamPhase::Middle;

        let mult_fear = fluid_distance_multiplier(&config, &state_fear, (5, 5), (10, 10), &mut rng1);
        let mult_conf = fluid_distance_multiplier(&config, &state_confusion, (5, 5), (10, 10), &mut rng2);

        // Fear pulls closer (factor 0.7), confusion stretches (factor 1.3)
        // They should differ given the same RNG seed
        assert!(mult_fear < mult_conf, "Fear ({}) should give smaller multiplier than Confusion ({})", mult_fear, mult_conf);
    }
}
