use rand::rngs::StdRng;
use rand::Rng;
use serde::{Deserialize, Serialize};
use tracing::debug;

use crate::agent::{Attributes, NeedChanges, Needs};
use crate::config::{ActionConfig, Config};

// ---------------------------------------------------------------------------
// Structured output schema builder
// ---------------------------------------------------------------------------

/// Build a JSON schema that constrains the LLM's action response to valid
/// canonical action names only. Pass this to Ollama's `format` field.
pub fn build_action_schema(canonical_names: &[&str]) -> serde_json::Value {
    serde_json::json!({
        "type": "object",
        "required": ["action", "reason", "description"],
        "properties": {
            "action":      { "type": "string", "enum": canonical_names },
            "target":      { "type": ["string", "null"] },
            "intent":      { "type": "string", "default": "" },
            "reason":      { "type": "string" },
            "description": { "type": "string" }
        }
    })
}

// ---------------------------------------------------------------------------
// Action enum
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Action {
    Eat,
    Cook,
    Sleep,
    Rest,
    Forage,
    Fish,
    Exercise,
    Chat { target_name: String },
    Bathe,
    Explore,
    Play,
    Move { destination: String },
    CastIntent { intent: String },
    Pray { prayer: String },
    Praise { praise_text: String },
    Compose { haiku: String },
    ReadOracle,
    /// Gossip about another agent (FEAT-22).
    Gossip { about: String, rumor: String },
    /// Meditate — rest-like, restores energy + fun, auto-success.
    Meditate,
    /// Teach another nearby agent, sharing knowledge (both get social/fun boost).
    Teach { about: String, lesson: String },
    /// Admire a nearby agent (FEAT-24).
    Admire { admired_name: String },
    /// Fallback when requested action fails validation.
    Wander,
}

impl Action {
    pub fn name(&self) -> &'static str {
        match self {
            Action::Eat         => "Eat",
            Action::Cook        => "Cook",
            Action::Sleep       => "Sleep",
            Action::Rest        => "Rest",
            Action::Forage      => "Forage",
            Action::Fish        => "Fish",
            Action::Exercise    => "Exercise",
            Action::Chat { .. } => "Chat",
            Action::Bathe       => "Bathe",
            Action::Explore     => "Explore",
            Action::Play        => "Play",
            Action::Move { .. } => "Move",
            Action::CastIntent { .. } => "Cast Intent",
            Action::Pray { .. }       => "Pray",
            Action::Praise { .. }     => "Praise",
            Action::Compose { .. }    => "Compose",
            Action::ReadOracle        => "Read Oracle",
            Action::Gossip { .. }     => "Gossip",
            Action::Meditate          => "Meditate",
            Action::Teach { .. }      => "Teach",
            Action::Admire { .. }     => "Admire",
            Action::Wander            => "Wander",
        }
    }

    pub fn display(&self) -> String {
        match self {
            Action::Chat { target_name }       => format!("Chat with {}", target_name),
            Action::Move { destination }       => format!("Move > {}", destination),
            Action::CastIntent { intent }      => format!("Cast Intent: \"{}\"", intent),
            Action::Pray { prayer }            => format!("Pray: \"{}\"", prayer),
            Action::Praise { praise_text }     => format!("Praise: \"{}\"", praise_text),
            Action::Compose { haiku }          => format!("Compose: \"{}\"", haiku),
            Action::ReadOracle                 => "Read Oracle".to_string(),
            Action::Gossip { about, .. }       => format!("Gossip about {}", about),
            Action::Teach { about, .. }        => format!("Teach {}", about),
            Action::Admire { admired_name }    => format!("Admire {}", admired_name),
            other => other.name().to_string(),
        }
    }
}

// ---------------------------------------------------------------------------
// Outcome tier
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq)]
pub enum OutcomeTier {
    CriticalFail,
    Fail,
    Success,
    CriticalSuccess,
}

impl OutcomeTier {
    pub fn label(&self) -> &'static str {
        match self {
            OutcomeTier::CriticalFail    => "Critical Fail",
            OutcomeTier::Fail            => "Fail",
            OutcomeTier::Success         => "Success",
            OutcomeTier::CriticalSuccess => "Critical Success",
        }
    }

    /// Multiplier applied to need changes.
    pub fn multiplier(&self) -> f32 {
        match self {
            OutcomeTier::CriticalFail    => 0.5,
            OutcomeTier::Fail            => 0.0,
            OutcomeTier::Success         => 1.0,
            OutcomeTier::CriticalSuccess => 1.5,
        }
    }
}

// ---------------------------------------------------------------------------
// Action resolution result
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct Resolution {
    pub action:       Action,
    pub tier:         OutcomeTier,
    pub roll:         u32,
    pub modifier:     i32,
    pub penalty:      i32,
    pub total:        i32,
    pub dc:           u32,
    pub need_changes: NeedChanges,
    pub duration:     u32,
    /// The governing attribute name (e.g. "vigor"). Empty for auto-success actions.
    pub attribute:    &'static str,
}

impl Resolution {
    pub fn check_line(&self) -> String {
        if self.dc == 0 { return String::new(); }
        let attr = self.attribute_label();
        let mod_val = self.modifier + self.penalty;
        let mod_str = if mod_val > 0 {
            format!("+{}", mod_val)
        } else if mod_val < 0 {
            format!("{}", mod_val)
        } else {
            String::new()
        };
        if attr.is_empty() {
            format!("d20({}){}={} vs DC {} | {}", self.roll, mod_str, self.total, self.dc, self.tier.label())
        } else {
            format!("{} d20({}){}={} vs DC {} | {}", attr, self.roll, mod_str, self.total, self.dc, self.tier.label())
        }
    }

    fn attribute_label(&self) -> String {
        match &self.action {
            Action::Cook     => "Wit".into(),
            Action::Forage   => "Grace".into(),
            Action::Fish     => "Grace".into(),
            Action::Exercise => "Vigor".into(),
            Action::Chat { .. } => "Heart".into(),
            Action::Explore  => "Vigor".into(),
            _ => String::new(),
        }
    }
}

// ---------------------------------------------------------------------------
// Resolution logic
// ---------------------------------------------------------------------------

/// Build base NeedChanges from an ActionConfig.
fn base_changes(cfg: &ActionConfig) -> NeedChanges {
    NeedChanges {
        hunger:  cfg.hunger_restore,
        energy:  cfg.energy_restore.map(|v| v).or_else(|| cfg.energy_drain.map(|d| -d)),
        fun:     cfg.fun_restore,
        social:  cfg.social_restore,
        hygiene: cfg.hygiene_restore,
    }
}

/// Returns the governing attribute name for a given action (empty string for auto-success actions).
pub fn action_attribute(action: &Action) -> &'static str {
    match action {
        Action::Cook        => "wit",
        Action::Forage      => "grace",
        Action::Fish        => "grace",
        Action::Exercise    => "vigor",
        Action::Chat { .. } => "heart",
        Action::Explore     => "vigor",
        _                   => "",
    }
}

/// Resolve a non-magic action. Returns a Resolution.
/// `extra_dc` is added to the effective DC (use for storm bonus, neglect debuff, etc.).
/// `specialty_modifier` is added to the total roll (use for specialty bonus, etc.).
pub fn resolve(
    action:             &Action,
    attributes:         &Attributes,
    needs:              &Needs,
    config:             &Config,
    is_night:           bool,
    extra_dc:           u32,
    rng:                &mut StdRng,
    specialty_modifier: i32,
) -> Resolution {
    let (cfg, attr_name) = action_cfg_and_attr(action, config);
    let base_dc          = effective_dc(action, cfg, is_night, config);
    let base             = base_changes(cfg);

    // Auto-success actions (base dc = 0, ignoring extra_dc overrides)
    if base_dc == 0 {
        let duration = cfg.duration_ticks.unwrap_or(1);
        return Resolution {
            action: action.clone(),
            tier: OutcomeTier::Success,
            roll: 0, modifier: 0, penalty: 0, total: 0, dc: 0,
            need_changes: base,
            duration,
            attribute: attr_name,
        };
    }

    let dc       = base_dc + extra_dc;
    let roll     = rng.gen_range(1u32..=20);
    let modifier = attributes.modifier(attr_name);
    let penalty  = needs.penalty(config, attr_name);
    let total    = roll as i32 + modifier + penalty + specialty_modifier;

    let tier = if roll == config.resolution.crit_fail {
        OutcomeTier::CriticalFail
    } else if roll == config.resolution.crit_success {
        OutcomeTier::CriticalSuccess
    } else if total >= dc as i32 {
        OutcomeTier::Success
    } else {
        OutcomeTier::Fail
    };

    let need_changes = base.scale(tier.multiplier());

    if specialty_modifier != 0 {
        debug!(target: "action",
            action = %action.name(), roll = roll, modifier = modifier,
            penalty = penalty, specialty_modifier = specialty_modifier,
            total = total, dc = dc, tier = ?tier,
            "d20 resolution (with specialty bonus)");
    } else {
        debug!(target: "action",
            action = %action.name(), roll = roll, modifier = modifier,
            penalty = penalty, total = total, dc = dc, tier = ?tier,
            "d20 resolution");
    }

    Resolution {
        action: action.clone(),
        tier,
        roll, modifier, penalty, total, dc,
        need_changes,
        duration: 1,
        attribute: attr_name,
    }
}

fn effective_dc(action: &Action, cfg: &ActionConfig, is_night: bool, config: &Config) -> u32 {
    let base = cfg.dc;
    if base == 0 { return 0; }
    let night_bonus = match action {
        Action::Forage | Action::Explore if is_night => config.resolution.night_dc_bonus as u32,
        _ => 0,
    };
    base + night_bonus
}

/// Returns (ActionConfig, attribute_name) for the given action.
pub fn action_cfg_and_attr<'a>(action: &Action, config: &'a Config) -> (&'a ActionConfig, &'static str) {
    match action {
        Action::Eat         => (&config.actions.eat,         ""),
        Action::Cook        => (&config.actions.cook,        "wit"),
        Action::Sleep       => (&config.actions.sleep,       ""),
        Action::Rest        => (&config.actions.rest,        ""),
        Action::Forage      => (&config.actions.forage,      "grace"),
        Action::Fish        => (&config.actions.fish,        "grace"),
        Action::Exercise    => (&config.actions.exercise,    "vigor"),
        Action::Chat { .. } => (&config.actions.chat,        "heart"),
        Action::Bathe       => (&config.actions.bathe,       ""),
        Action::Explore     => (&config.actions.explore,     "vigor"),
        Action::Play        => (&config.actions.play,        ""),
        Action::Move { .. }      => (&config.actions.rest,        ""), // placeholder; move has no needs
        Action::CastIntent{ .. } => (&config.actions.cast_intent, "numen"),
        Action::Pray { .. }      => (&config.actions.pray,        ""),
        Action::Praise { .. }    => (&config.actions.praise,      ""),
        Action::Compose { .. }   => (&config.actions.compose,     ""),
        Action::ReadOracle       => (&config.actions.read_oracle,  ""),
        Action::Gossip { .. }    => (&config.actions.gossip,       ""),
        Action::Meditate         => (&config.actions.meditate,     ""),
        Action::Teach { .. }     => (&config.actions.teach,        "heart"),
        Action::Admire { .. }    => (&config.actions.admire,       "heart"),
        Action::Wander           => (&config.actions.rest,        ""),
    }
}

// ---------------------------------------------------------------------------
// Strip thinking-model tags
// ---------------------------------------------------------------------------

/// Remove `<think>...</think>` blocks emitted by chain-of-thought models
/// (e.g. qwen3) so the parsers below only see the actual JSON payload.
pub fn strip_thinking_tags(s: &str) -> String {
    let mut result = s.to_string();
    loop {
        match (result.find("<think>"), result.find("</think>")) {
            (Some(start), Some(end)) if end > start => {
                let close_end = end + "</think>".len();
                result = format!("{}{}", &result[..start], &result[close_end..]);
            }
            _ => break,
        }
    }
    result.trim().to_string()
}

// ---------------------------------------------------------------------------
// Parse LLM response JSON into an Action
// ---------------------------------------------------------------------------

#[derive(Deserialize, Default)]
struct ActionResponse {
    action:      Option<String>,
    target:      Option<String>,
    intent:      Option<String>,
    reason:      Option<String>,
    description: Option<String>,
}

/// Cascading parser: JSON → code-fence extraction → regex → Wander default.
/// Returns (action, reason, description).
pub fn parse_response(raw: &str) -> (Action, Option<String>, Option<String>) {
    let stripped = strip_thinking_tags(raw);
    let raw = stripped.as_str();
    // 1. Try direct JSON parse
    if let Some(t) = try_parse_json(raw) {
        debug!(target: "action", action = ?t.0, "Action parsed from LLM output");
        return t;
    }
    // 2. Extract from ```json ... ``` code fence
    if let Some(json) = extract_code_fence(raw) {
        if let Some(t) = try_parse_json(&json) {
            debug!(target: "action", action = ?t.0, "Action parsed from LLM output");
            return t;
        }
    }
    // 3. Extract action name with regex-like scan
    if let Some(action_name) = extract_action_field(raw) {
        let a = action_from_name(&action_name, None, None);
        debug!(target: "action", action = ?a, "Action parsed from LLM output");
        return (a, None, None);
    }
    // 4. Default
    tracing::warn!("Could not parse LLM response, defaulting to Wander. Raw: {}", &raw[..raw.len().min(200)]);
    (Action::Wander, None, None)
}

fn try_parse_json(s: &str) -> Option<(Action, Option<String>, Option<String>)> {
    let s = s.trim();
    let parsed: ActionResponse = serde_json::from_str(s).ok()?;
    let name        = parsed.action?;
    let action      = action_from_name(&name, parsed.target.as_deref(), parsed.intent.as_deref());
    let reason      = parsed.reason.filter(|r| !r.is_empty());
    let description = parsed.description.filter(|d| !d.is_empty());
    Some((action, reason, description))
}

pub fn extract_code_fence(s: &str) -> Option<String> {
    let start = s.find("```")?;
    let rest  = &s[start + 3..];
    // skip optional language tag
    let rest  = rest.trim_start_matches(|c: char| c.is_alphabetic());
    let end   = rest.find("```")?;
    Some(rest[..end].trim().to_string())
}

fn extract_action_field(s: &str) -> Option<String> {
    // Look for "action": "something"
    let key = "\"action\"";
    let pos  = s.find(key)?;
    let rest = &s[pos + key.len()..];
    let colon = rest.find(':')? + 1;
    let rest  = rest[colon..].trim();
    if rest.starts_with('"') {
        let inner = &rest[1..];
        let end   = inner.find('"')?;
        return Some(inner[..end].to_string());
    }
    None
}

pub fn action_from_name(name: &str, target: Option<&str>, intent: Option<&str>) -> Action {

    match name.to_lowercase().replace('_', " ").trim() {
        "eat"                         => Action::Eat,
        "cook"                        => Action::Cook,
        "sleep"                       => Action::Sleep,
        "rest"                        => Action::Rest,
        "forage"                      => Action::Forage,
        "fish"                        => Action::Fish,
        "exercise"                    => Action::Exercise,
        "bathe"                       => Action::Bathe,
        "explore"                     => Action::Explore,
        "play"                        => Action::Play,
        "wander"                      => Action::Wander,
        "chat" => {
            let t = target.unwrap_or("").to_string();
            Action::Chat { target_name: t }
        }
        "move" => {
            let d = target.unwrap_or("Village Square").to_string();
            Action::Move { destination: d }
        }
        "cast intent" | "cast_intent" => {
            let i = intent.unwrap_or("").to_string();
            if i.is_empty() {
                Action::CastIntent { intent: "I seek something I cannot quite name".to_string() }
            } else {
                Action::CastIntent { intent: i }
            }
        }
        "pray" => {
            let p = intent.unwrap_or("I offer this moment in stillness").to_string();
            Action::Pray { prayer: p }
        }
        "praise" => {
            let p = intent.unwrap_or("I offer gratitude for this world").to_string();
            Action::Praise { praise_text: p }
        }
        "compose" => {
            let h = intent.unwrap_or("silence / between two thoughts / the world breathes").to_string();
            Action::Compose { haiku: h }
        }
        "read oracle" | "read_oracle" => Action::ReadOracle,
        "gossip" => {
            let about = target.unwrap_or("").to_string();
            let rumor = intent.unwrap_or("I noticed something about them").to_string();
            if about.is_empty() {
                tracing::warn!("Gossip action with no target, defaulting to Wander");
                Action::Wander
            } else {
                Action::Gossip { about, rumor }
            }
        }
        "meditate" => Action::Meditate,
        "teach" => {
            let about  = target.unwrap_or("").to_string();
            let lesson = intent.unwrap_or("I shared what I know").to_string();
            if about.is_empty() {
                tracing::warn!("Teach action with no target, defaulting to Wander");
                Action::Wander
            } else {
                Action::Teach { about, lesson }
            }
        }
        "admire" => {
            let name = target.unwrap_or("").to_string();
            if name.is_empty() {
                tracing::warn!("Admire action with no target, defaulting to Wander");
                Action::Wander
            } else {
                Action::Admire { admired_name: name }
            }
        }
        other => {
            tracing::warn!("Unknown action '{}', defaulting to Wander", other);
            Action::Wander
        }
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn strip_thinking_tags_removes_blocks() {
        let s = "<think>some reasoning</think>actual content";
        assert_eq!(strip_thinking_tags(s), "actual content");
    }

    #[test]
    fn strip_thinking_tags_multiple_blocks() {
        let s = "<think>a</think> middle <think>b</think> end";
        let result = strip_thinking_tags(s);
        assert!(!result.contains("<think>"), "think tags should be stripped: {}", result);
        assert!(result.contains("middle"), "content should be preserved: {}", result);
    }

    #[test]
    fn parse_response_with_think_tags() {
        let raw = r#"<think>Let me choose an action carefully.</think>{"action":"eat","target":null,"intent":null,"reason":"hungry","description":"I sit down and eat."}"#;
        let (action, reason, _desc) = parse_response(raw);
        assert!(matches!(action, Action::Eat), "expected Eat, got {:?}", action);
        assert_eq!(reason.as_deref(), Some("hungry"));
    }

    // --- parse_response cascade ---

    #[test]
    fn parse_response_valid_direct_json() {
        let raw = r#"{"action":"fish","target":null,"intent":null,"reason":"hungry","description":"I fish at the river"}"#;
        let (action, reason, desc) = parse_response(raw);
        assert!(matches!(action, Action::Fish), "expected Fish, got {:?}", action);
        assert_eq!(reason.as_deref(), Some("hungry"));
        assert!(desc.is_some());
    }

    #[test]
    fn parse_response_code_fenced_json() {
        let raw = "```json\n{\"action\":\"eat\",\"reason\":\"hungry\",\"description\":\"eating\"}\n```";
        let (action, _, _) = parse_response(raw);
        assert!(matches!(action, Action::Eat), "expected Eat, got {:?}", action);
    }

    #[test]
    fn parse_response_regex_fallback() {
        // No valid JSON but has "action": "fish" in prose
        let raw = r#"I think I should rest. "action": "fish" is what I choose."#;
        let (action, _, _) = parse_response(raw);
        assert!(matches!(action, Action::Fish), "expected Fish, got {:?}", action);
    }

    #[test]
    fn parse_response_empty_string_becomes_wander() {
        let (action, _, _) = parse_response("");
        assert!(matches!(action, Action::Wander), "expected Wander, got {:?}", action);
    }

    #[test]
    fn parse_response_garbage_becomes_wander() {
        let (action, _, _) = parse_response("xyz !! not json at all !!! 123");
        assert!(matches!(action, Action::Wander), "expected Wander, got {:?}", action);
    }

    #[test]
    fn parse_response_null_action_field_becomes_wander() {
        // {"action":null} — action field is null, not a string → Option<String> is None
        // try_parse_json returns None (action? short-circuits), no string in extract_action_field
        let raw = r#"{"action":null,"reason":"confused"}"#;
        let (action, _, _) = parse_response(raw);
        assert!(matches!(action, Action::Wander), "expected Wander for null action, got {:?}", action);
    }

    #[test]
    fn parse_response_reason_empty_string_filtered() {
        let raw = r#"{"action":"eat","reason":"","description":"eating"}"#;
        let (_, reason, _) = parse_response(raw);
        assert!(reason.is_none(), "empty reason should be filtered to None");
    }

    // --- action_from_name edge cases ---

    #[test]
    fn action_from_name_case_insensitive() {
        let a = action_from_name("EAT", None, None);
        assert!(matches!(a, Action::Eat), "EAT should map to Eat");
        let b = action_from_name("CAST_INTENT", None, Some("test intent"));
        assert!(matches!(b, Action::CastIntent { .. }), "CAST_INTENT should map to CastIntent");
    }

    #[test]
    fn action_from_name_chat_empty_target_allowed() {
        let a = action_from_name("chat", None, None);
        match a {
            Action::Chat { target_name } => assert!(target_name.is_empty(), "no target → empty string"),
            _ => panic!("expected Chat, got {:?}", a),
        }
    }

    #[test]
    fn action_from_name_move_no_target_defaults_village_square() {
        let a = action_from_name("move", None, None);
        match a {
            Action::Move { destination } => assert_eq!(destination, "Village Square"),
            _ => panic!("expected Move, got {:?}", a),
        }
    }

    #[test]
    fn action_from_name_gossip_empty_target_becomes_wander() {
        let a = action_from_name("gossip", None, Some("some rumor"));
        assert!(matches!(a, Action::Wander), "gossip with no target should Wander");
    }

    #[test]
    fn action_from_name_teach_empty_target_becomes_wander() {
        let a = action_from_name("teach", None, Some("some lesson"));
        assert!(matches!(a, Action::Wander), "teach with no target should Wander");
    }

    #[test]
    fn action_from_name_admire_empty_target_becomes_wander() {
        let a = action_from_name("admire", None, None);
        assert!(matches!(a, Action::Wander), "admire with no target should Wander");
    }

    #[test]
    fn action_from_name_cast_intent_empty_intent_uses_default() {
        let a = action_from_name("cast_intent", None, Some(""));
        match a {
            Action::CastIntent { intent } => {
                assert!(!intent.is_empty(), "empty intent should use hardcoded default");
                assert_eq!(intent, "I seek something I cannot quite name");
            }
            _ => panic!("expected CastIntent, got {:?}", a),
        }
    }

    #[test]
    fn action_from_name_unknown_becomes_wander() {
        let a = action_from_name("fly_through_the_sky", None, None);
        assert!(matches!(a, Action::Wander), "unknown action should Wander");
    }

    // --- d20 math ---

    #[test]
    fn resolve_auto_success_dc_zero() {
        use rand::SeedableRng;
        use rand::rngs::StdRng;
        use crate::agent::{Attributes, Needs};
        let config = crate::config::load("config/world.toml").expect("config should load");
        let attrs = Attributes { vigor: 6, wit: 6, grace: 6, heart: 6, numen: 6 };
        let needs = Needs { hunger: 70.0, energy: 70.0, fun: 70.0, social: 70.0, hygiene: 70.0 };
        let mut rng = StdRng::seed_from_u64(0);
        let res = resolve(&Action::Rest, &attrs, &needs, &config, false, 0, &mut rng, 0);
        assert_eq!(res.tier, OutcomeTier::Success, "Rest should auto-succeed");
        assert_eq!(res.roll, 0, "auto-success has roll=0");
        assert_eq!(res.dc, 0, "auto-success has dc=0");
    }

    #[test]
    fn resolve_night_dc_bonus_applies() {
        use rand::SeedableRng;
        use rand::rngs::StdRng;
        use crate::agent::{Attributes, Needs};
        let config = crate::config::load("config/world.toml").expect("config should load");
        let attrs = Attributes { vigor: 6, wit: 6, grace: 6, heart: 6, numen: 6 };
        let needs = Needs { hunger: 70.0, energy: 70.0, fun: 70.0, social: 70.0, hygiene: 70.0 };
        let mut rng_day   = StdRng::seed_from_u64(99);
        let mut rng_night = StdRng::seed_from_u64(99);
        let res_day   = resolve(&Action::Forage, &attrs, &needs, &config, false, 0, &mut rng_day,   0);
        let res_night = resolve(&Action::Forage, &attrs, &needs, &config, true,  0, &mut rng_night, 0);
        assert!(res_night.dc > res_day.dc,
            "night DC ({}) should exceed day DC ({})", res_night.dc, res_day.dc);
    }

    #[test]
    fn need_changes_scale_multiplier_zero_gives_zero() {
        use crate::agent::NeedChanges;
        let nc = NeedChanges { hunger: Some(20.0), energy: Some(-5.0), fun: None, social: None, hygiene: None };
        let scaled = nc.scale(0.0);
        assert_eq!(scaled.hunger, Some(0.0), "scaled hunger should be 0");
        assert_eq!(scaled.energy, Some(0.0), "scaled energy should be 0");
        assert!(scaled.fun.is_none(), "None fields remain None");
    }

    #[test]
    fn need_changes_scale_multiplier_1_5() {
        use crate::agent::NeedChanges;
        let nc = NeedChanges { hunger: Some(20.0), energy: None, fun: None, social: None, hygiene: None };
        let scaled = nc.scale(1.5);
        let h = scaled.hunger.expect("hunger should be Some after scaling");
        assert!((h - 30.0).abs() < 0.001, "20.0 * 1.5 should be 30.0, got {}", h);
    }

    // --- Attributes::modifier ---

    #[test]
    fn modifier_score_5_gives_zero() {
        use crate::agent::Attributes;
        let attrs = Attributes { vigor: 5, wit: 6, grace: 6, heart: 6, numen: 6 };
        assert_eq!(attrs.modifier("vigor"), 0, "score 5 → modifier 0");
    }

    #[test]
    fn modifier_score_10_gives_plus_five() {
        use crate::agent::Attributes;
        let attrs = Attributes { vigor: 10, wit: 6, grace: 6, heart: 6, numen: 6 };
        assert_eq!(attrs.modifier("vigor"), 5, "score 10 → modifier +5");
    }

    #[test]
    fn modifier_unknown_attr_defaults_to_5() {
        use crate::agent::Attributes;
        let attrs = Attributes { vigor: 10, wit: 10, grace: 10, heart: 10, numen: 10 };
        // Unknown attr defaults to score 5 → modifier = 5 - 5 = 0
        assert_eq!(attrs.modifier("arcane"), 0, "unknown attr defaults to score 5 → modifier 0");
    }
}
