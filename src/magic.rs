use serde::Deserialize;
use tracing::{debug, warn};

use crate::action::extract_code_fence;
use crate::agent::{Agent, NeedChanges};
use crate::config::Config;

// ---------------------------------------------------------------------------
// Interpreter prompt
// ---------------------------------------------------------------------------

pub fn build_interpreter_prompt(
    agent:        &Agent,
    intent:       &str,
    location_name: &str,
    others_nearby: &[String],
    config:       &Config,
) -> String {
    let others = if others_nearby.is_empty() {
        "None nearby".to_string()
    } else {
        others_nearby.join(", ")
    };

    let world_notes = format!(
        "Hunger: {:.0}/100, Energy: {:.0}/100",
        agent.needs.hunger, agent.needs.energy
    );

    format!(
        r#"You are the Interpreter of Intent in the world of Nephara. A being has spoken
a desire upon reality, and reality must respond.

SPEAKER: {name}
NUMEN (magical clarity, 1-10): {numen}
LOCATION: {location}
NEARBY: {others}
WORLD STATE NOTES: {world_notes}

THE SPOKEN INTENT:
"{intent}"

Your task:
1. Identify the PRIMARY EFFECT — what the speaker most likely meant.
2. Analyze every word for SECONDARY MEANINGS — synonyms, metaphors, double
   meanings, emotional undertones, etymological echoes. List 2-3.
3. Based on Numen score, determine how the intent manifests:
   - Numen 1-3: Secondary meanings DOMINATE. Reality is creative and willful.
   - Numen 4-6: MIXED. Primary effect occurs, but secondary meanings also manifest.
   - Numen 7-9: CLEAN. Primary dominates. Secondary effects are subtle, poetic.
   - Numen 10: MASTERFUL. Almost exactly as meant. Secondary effects are beautiful.
4. Determine duration in ticks (1-4, more ambitious = longer).
5. Determine need changes for the caster (energy always drains by {energy_drain}).

CRITICAL: The spell ALWAYS SUCCEEDS. Never say "nothing happens." Every intent
produces something interesting. Wild misinterpretations should feel like stories,
not punishment.

No direct harm to others. No world-breaking effects. Effects are local and temporary.

Respond with ONLY a JSON object:
{{
  "primary_effect": "What happens as intended",
  "interpretations": ["secondary meaning 1", "secondary meaning 2"],
  "secondary_effect": "What else happens due to the words' other meanings",
  "duration_ticks": 2,
  "need_changes": {{"fun": 10, "energy": -8}},
  "memory_entry": "One-line summary for the caster's memory"
}}"#,
        name        = agent.identity.name,
        numen       = agent.attributes.numen,
        location    = location_name,
        others      = others,
        world_notes = world_notes,
        intent      = intent,
        energy_drain = config.actions.cast_intent.energy_drain.unwrap_or(8.0),
    )
}

// ---------------------------------------------------------------------------
// Interpreter response
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
pub struct InterpretedIntent {
    pub primary_effect:   String,
    pub interpretations:  Vec<String>,
    pub secondary_effect: String,
    pub duration_ticks:   u32,
    pub need_changes:     RawNeedChanges,
    pub memory_entry:     String,
}

/// Serde target for the raw need changes map from the LLM.
#[derive(Debug, Deserialize, Default)]
pub struct RawNeedChanges {
    #[serde(default)] pub hunger:  Option<f32>,
    #[serde(default)] pub energy:  Option<f32>,
    #[serde(default)] pub fun:     Option<f32>,
    #[serde(default)] pub social:  Option<f32>,
    #[serde(default)] pub hygiene: Option<f32>,
}

impl InterpretedIntent {
    pub fn to_need_changes(&self, config: &Config) -> NeedChanges {
        // Always apply the configured energy drain; LLM may or may not include it
        let llm_energy = self.need_changes.energy.unwrap_or(0.0);
        let drain      = config.actions.cast_intent.energy_drain.unwrap_or(8.0);
        // Use whichever is more negative
        let energy = if llm_energy < -drain { llm_energy } else { -drain };

        NeedChanges {
            hunger:  self.need_changes.hunger,
            energy:  Some(energy),
            fun:     self.need_changes.fun,
            social:  self.need_changes.social,
            hygiene: self.need_changes.hygiene,
        }
    }

    /// Clamp duration to configured bounds.
    pub fn clamped_duration(&self, config: &Config) -> u32 {
        let min = config.actions.cast_intent.min_duration_ticks.unwrap_or(1);
        let max = config.actions.cast_intent.max_duration_ticks.unwrap_or(4);
        self.duration_ticks.clamp(min, max)
    }
}

// ---------------------------------------------------------------------------
// Response parsing — same cascading approach as action parser
// ---------------------------------------------------------------------------

pub fn parse_interpreter_response(raw: &str) -> Option<InterpretedIntent> {
    let stripped = crate::action::strip_thinking_tags(raw);
    let raw = stripped.as_str();
    debug!(target: "magic", chars = raw.len(), raw = %raw, "Interpreter raw response");

    if let Ok(v) = serde_json::from_str::<InterpretedIntent>(raw.trim()) {
        debug!(target: "magic", primary = %v.primary_effect, duration = v.duration_ticks, "Interpreter parsed");
        return Some(v);
    }

    // Extract from code fence
    if let Some(json) = extract_code_fence(raw) {
        if let Ok(v) = serde_json::from_str::<InterpretedIntent>(&json) {
            debug!(target: "magic", primary = %v.primary_effect, duration = v.duration_ticks, "Interpreter parsed");
            return Some(v);
        }
    }

    warn!("Failed to parse interpreter response. Raw: {}", &raw[..raw.len().min(300)]);
    None
}

// ---------------------------------------------------------------------------
// Fallback InterpretedIntent when parsing fails
// ---------------------------------------------------------------------------

pub fn fallback_intent(intent: &str, energy_drain: f32) -> InterpretedIntent {
    InterpretedIntent {
        primary_effect:  format!("Something stirs in response to \"{}\".", intent),
        interpretations: vec!["the world listens in its own way".into()],
        secondary_effect: "A faint warmth brushes those nearby.".into(),
        duration_ticks:  1,
        need_changes:    RawNeedChanges { energy: Some(-energy_drain), fun: Some(5.0), ..Default::default() },
        memory_entry:    format!("Cast intent: \"{}\". Reality trembled faintly.", intent),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // -----------------------------------------------------------------------
    // parse_interpreter_response cascade
    // -----------------------------------------------------------------------

    #[test]
    fn parse_interpreter_response_valid_json() {
        let raw = r#"{"primary_effect":"A warmth settles.","interpretations":["warmth as belonging","warmth as memory"],"secondary_effect":"Those nearby feel welcome.","duration_ticks":2,"need_changes":{"fun":10,"energy":-8,"social":5},"memory_entry":"Cast intent: warmth."}"#;
        let result = parse_interpreter_response(raw);
        assert!(result.is_some(), "valid JSON should parse successfully");
        let ii = result.unwrap();
        assert_eq!(ii.duration_ticks, 2);
        assert!(!ii.primary_effect.is_empty());
    }

    #[test]
    fn parse_interpreter_response_code_fenced() {
        let raw = "```json\n{\"primary_effect\":\"Light bends.\",\"interpretations\":[\"light as clarity\"],\"secondary_effect\":\"A crow watches.\",\"duration_ticks\":1,\"need_changes\":{\"fun\":8,\"energy\":-8},\"memory_entry\":\"Cast intent: light.\"}\n```";
        let result = parse_interpreter_response(raw);
        assert!(result.is_some(), "code-fenced JSON should parse successfully");
    }

    #[test]
    fn parse_interpreter_response_returns_none_on_garbage() {
        let result = parse_interpreter_response("this is not json at all !! xyz");
        assert!(result.is_none(), "garbage input should return None");
    }

    #[test]
    fn parse_interpreter_response_think_tags_stripped() {
        let raw = r#"<think>Let me think about this carefully.</think>{"primary_effect":"Rain arrives.","interpretations":["rain as change"],"secondary_effect":"Birds take flight.","duration_ticks":1,"need_changes":{"fun":12,"energy":-8},"memory_entry":"Cast intent: rain."}"#;
        let result = parse_interpreter_response(raw);
        assert!(result.is_some(), "think-tag-wrapped JSON should parse after stripping");
        let ii = result.unwrap();
        assert!(!ii.primary_effect.is_empty());
    }

    // -----------------------------------------------------------------------
    // Energy drain enforcement
    // -----------------------------------------------------------------------

    #[test]
    fn interpreted_intent_energy_drain_enforced_when_llm_returns_less() {
        let config = crate::config::load("config/world.toml").expect("config should load");
        let drain = config.actions.cast_intent.energy_drain.unwrap_or(8.0);
        // LLM returns -2.0 (less negative than drain), should be enforced to -drain
        let ii = InterpretedIntent {
            primary_effect:   "test".to_string(),
            interpretations:  vec![],
            secondary_effect: "test".to_string(),
            duration_ticks:   1,
            need_changes:     RawNeedChanges { energy: Some(-2.0), ..Default::default() },
            memory_entry:     "test".to_string(),
        };
        let changes = ii.to_need_changes(&config);
        let energy = changes.energy.expect("energy should be Some");
        assert_eq!(energy, -drain,
            "LLM returned -2.0 but drain is {}, so energy should be -{}", drain, drain);
    }

    #[test]
    fn interpreted_intent_energy_drain_lets_larger_drain_through() {
        let config = crate::config::load("config/world.toml").expect("config should load");
        let drain = config.actions.cast_intent.energy_drain.unwrap_or(8.0);
        // LLM returns a more-negative value than drain (e.g. -12.0)
        let large_drain = -(drain + 4.0);
        let ii = InterpretedIntent {
            primary_effect:   "test".to_string(),
            interpretations:  vec![],
            secondary_effect: "test".to_string(),
            duration_ticks:   1,
            need_changes:     RawNeedChanges { energy: Some(large_drain), ..Default::default() },
            memory_entry:     "test".to_string(),
        };
        let changes = ii.to_need_changes(&config);
        let energy = changes.energy.expect("energy should be Some");
        assert_eq!(energy, large_drain,
            "LLM drain {} is larger than configured {}, should pass through", large_drain, -drain);
    }

    // -----------------------------------------------------------------------
    // fallback_intent
    // -----------------------------------------------------------------------

    #[test]
    fn fallback_intent_contains_intent_string() {
        let intent = "I seek warmth";
        let fi = fallback_intent(intent, 8.0);
        assert!(fi.primary_effect.contains(intent),
            "primary_effect should contain the intent string");
        assert_eq!(fi.need_changes.energy, Some(-8.0));
        assert_eq!(fi.duration_ticks, 1);
    }
}
