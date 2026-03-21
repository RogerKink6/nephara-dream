use std::collections::{HashMap, VecDeque};
use serde::{Deserialize, Serialize};

use crate::config::{Config, NeedsValues};
use crate::soul::SoulSeed;

pub type AgentId = usize;

// ---------------------------------------------------------------------------
// Beliefs (Theory of Mind — FEAT-23)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct AgentBeliefs {
    /// Rumors / impressions accumulated about this agent.
    pub rumors: Vec<String>,
}

// ---------------------------------------------------------------------------
// Identity
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentIdentity {
    pub name:             String,
    pub personality:      String,
    pub backstory:        String,
    pub magical_affinity: String,
    pub self_declaration: String,
    pub specialty:        Option<String>,
}

// ---------------------------------------------------------------------------
// Attributes
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Attributes {
    pub vigor: u32,
    pub wit:   u32,
    pub grace: u32,
    pub heart: u32,
    pub numen: u32,
}

impl Attributes {
    /// Returns the d20 modifier for a named attribute.
    pub fn modifier(&self, attr: &str) -> i32 {
        let score = match attr {
            "vigor" => self.vigor,
            "wit"   => self.wit,
            "grace" => self.grace,
            "heart" => self.heart,
            "numen" => self.numen,
            _       => 5,
        } as i32;
        score - 5
    }
}

// ---------------------------------------------------------------------------
// Needs
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Needs {
    pub hunger:  f32,
    pub energy:  f32,
    pub fun:     f32,
    pub social:  f32,
    pub hygiene: f32,
}

impl Needs {
    pub fn from_initial(v: &NeedsValues) -> Self {
        Needs { hunger: v.hunger, energy: v.energy, fun: v.fun, social: v.social, hygiene: v.hygiene }
    }

    pub fn clamp(&mut self) {
        self.hunger  = self.hunger .clamp(0.0, 100.0);
        self.energy  = self.energy .clamp(0.0, 100.0);
        self.fun     = self.fun    .clamp(0.0, 100.0);
        self.social  = self.social .clamp(0.0, 100.0);
        self.hygiene = self.hygiene.clamp(0.0, 100.0);
    }

    pub fn apply_decay(&mut self, decay: &NeedsValues) {
        self.hunger  -= decay.hunger;
        self.energy  -= decay.energy;
        self.fun     -= decay.fun;
        self.social  -= decay.social;
        self.hygiene -= decay.hygiene;
        self.clamp();
    }

    pub fn apply(&mut self, changes: &NeedChanges) {
        if let Some(v) = changes.hunger  { self.hunger  += v; }
        if let Some(v) = changes.energy  { self.energy  += v; }
        if let Some(v) = changes.fun     { self.fun     += v; }
        if let Some(v) = changes.social  { self.social  += v; }
        if let Some(v) = changes.hygiene { self.hygiene += v; }
        self.clamp();
    }

    /// Sum of d20 penalties from need states, for the given attribute.
    pub fn penalty(&self, config: &Config, attribute: &str) -> i32 {
        let t = &config.needs.thresholds;
        let mut p = 0i32;

        // Hunger penalises all checks
        if self.hunger < t.penalty_severe {
            p -= 4;
        } else if self.hunger < t.penalty_mild {
            p -= 2;
        }

        // Energy penalises physical checks
        let physical = matches!(attribute, "vigor" | "grace");
        if physical {
            if self.energy < t.penalty_severe {
                p -= 4;
            } else if self.energy < t.penalty_mild {
                p -= 2;
            }
        }

        // Fun: -2 all at <10
        if self.fun < t.penalty_severe {
            p -= 2;
        }

        // Social + Hygiene: -2 Heart at <10
        if attribute == "heart" {
            if self.social  < t.penalty_severe { p -= 2; }
            if self.hygiene < t.penalty_severe { p -= 2; }
        }

        p
    }

    pub fn compact(&self) -> String {
        format!(
            "H:{:.0} E:{:.0} F:{:.0} S:{:.0} Y:{:.0}",
            self.hunger, self.energy, self.fun, self.social, self.hygiene
        )
    }

    pub fn describe(&self) -> String {
        format!(
            "Satiety: {:.0}/100, Energy: {:.0}/100, Fun: {:.0}/100, Social: {:.0}/100, Hygiene: {:.0}/100",
            self.hunger, self.energy, self.fun, self.social, self.hygiene
        )
    }
}

// ---------------------------------------------------------------------------
// NeedChanges — delta applied after action resolution
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct NeedChanges {
    pub hunger:  Option<f32>,
    pub energy:  Option<f32>,
    pub fun:     Option<f32>,
    pub social:  Option<f32>,
    pub hygiene: Option<f32>,
}

impl NeedChanges {
    pub fn scale(&self, factor: f32) -> Self {
        NeedChanges {
            hunger:  self.hunger .map(|v| v * factor),
            energy:  self.energy .map(|v| v * factor),
            fun:     self.fun    .map(|v| v * factor),
            social:  self.social .map(|v| v * factor),
            hygiene: self.hygiene.map(|v| v * factor),
        }
    }

    pub fn describe(&self) -> String {
        let mut parts = Vec::new();
        let fmt = |label: &str, val: f32| {
            if val > 0.0 { format!("{} +{:.0}", label, val) }
            else         { format!("{} {:.0}", label, val) }
        };
        if let Some(v) = self.hunger  { if v != 0.0 { parts.push(fmt("Hunger",  v)); } }
        if let Some(v) = self.energy  { if v != 0.0 { parts.push(fmt("Energy",  v)); } }
        if let Some(v) = self.fun     { if v != 0.0 { parts.push(fmt("Fun",     v)); } }
        if let Some(v) = self.social  { if v != 0.0 { parts.push(fmt("Social",  v)); } }
        if let Some(v) = self.hygiene { if v != 0.0 { parts.push(fmt("Hygiene", v)); } }
        parts.join(", ")
    }
}

// ---------------------------------------------------------------------------
// Inventory (Feature D)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ItemKind {
    Berry,
    Fish,
    Herb,
    CookedMeal,
}

impl ItemKind {
    pub fn label(self) -> &'static str {
        match self {
            ItemKind::Berry      => "Berry",
            ItemKind::Fish       => "Fish",
            ItemKind::Herb       => "Herb",
            ItemKind::CookedMeal => "Cooked Meal",
        }
    }
}

pub type Inventory = HashMap<ItemKind, u8>;

// ---------------------------------------------------------------------------
// Agent
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Agent {
    pub id:                AgentId,
    pub identity:          AgentIdentity,
    pub attributes:        Attributes,
    pub needs:             Needs,
    /// Current grid position (x, y) — x=column, y=row.
    pub pos:               (u8, u8),
    /// Home tile position — where the agent sleeps.
    pub home_pos:          (u8, u8),
    pub memory:            VecDeque<String>,
    pub busy_ticks:        u32,
    /// Energy restored per tick while sleeping (None when not sleeping).
    pub sleep_energy_tick: Option<f32>,
    pub daily_intentions:  Option<String>,
    pub life_story:        String,
    pub desires:           Option<String>,
    pub oracle_pending:    bool,
    /// Whether the agent has prayed or praised today (resets each day).
    pub daily_praised:     bool,
    /// Devotion score (0–100); rises with quality prayer/praise, decays when skipped.
    pub devotion:          f32,
    /// Summary (or raw excerpt) of past journal entries, injected into prompts.
    pub journal_summary:   String,
    /// XP toward leveling up each attribute (key: lowercase attr name).
    pub attribute_xp:           HashMap<String, u32>,
    /// Tick of the most recent successful use per attribute (for neglect debuff).
    pub attribute_last_success: HashMap<String, u32>,
    /// Affinity toward other agents keyed by name, range -100..=100.
    pub affinity:               HashMap<String, f32>,
    /// Theory-of-Mind belief map: other_name → accumulated rumors/impressions.
    pub beliefs:                HashMap<String, AgentBeliefs>,
    /// Recent action names (newest first) for repeat-penalty and prompt context.
    pub last_actions:           VecDeque<String>,
    /// Human-readable label of the action currently being executed (shown during busy ticks).
    pub current_action_display: String,
    /// Ticks remaining until this agent must praise again (0 = must praise now).
    pub praise_ticks_remaining: u32,
    /// Last N praise texts for repetition detection.
    pub recent_praises:         VecDeque<String>,
    /// Item inventory: item kind → count.
    pub inventory:              Inventory,
}

impl Agent {
    pub fn from_soul(id: AgentId, soul: &SoulSeed, config: &Config, home_pos: (u8, u8)) -> Self {
        Agent {
            id,
            identity: AgentIdentity {
                name:             soul.name.clone(),
                personality:      soul.personality.clone(),
                backstory:        soul.backstory.clone(),
                magical_affinity: soul.magical_affinity.clone(),
                self_declaration: soul.self_declaration.clone(),
                specialty:        soul.specialty.clone(),
            },
            attributes: Attributes {
                vigor: soul.vigor,
                wit:   soul.wit,
                grace: soul.grace,
                heart: soul.heart,
                numen: soul.numen,
            },
            needs:             Needs::from_initial(&config.needs.initial),
            pos:               home_pos,
            home_pos,
            memory:            VecDeque::new(),
            busy_ticks:        0,
            sleep_energy_tick: None,
            daily_intentions:  None,
            life_story:        String::new(),
            desires:           None,
            oracle_pending:    false,
            daily_praised:     false,
            devotion:          20.0,
            journal_summary:   String::new(),
            attribute_xp:           HashMap::new(),
            attribute_last_success: HashMap::new(),
            affinity:               HashMap::new(),
            beliefs:                HashMap::new(),
            last_actions:           VecDeque::new(),
            current_action_display: String::new(),
            praise_ticks_remaining: 0,
            recent_praises:         VecDeque::new(),
            inventory:              HashMap::new(),
        }
    }

    pub fn name(&self) -> &str { &self.identity.name }
    pub fn is_busy(&self) -> bool { self.busy_ticks > 0 }

    /// Total number of items held.
    pub fn inventory_count(&self) -> u8 {
        self.inventory.values().copied().fold(0u8, |acc, v| acc.saturating_add(v))
    }

    /// Add `count` items of `kind`, clamped to `max_slots` total.
    pub fn add_item(&mut self, kind: ItemKind, count: u8, max_slots: u8) {
        let current_total = self.inventory_count();
        let space = max_slots.saturating_sub(current_total);
        let to_add = count.min(space);
        if to_add > 0 {
            *self.inventory.entry(kind).or_insert(0) += to_add;
        }
    }

    /// Consume `count` items of `kind`. Returns true if successful.
    pub fn consume_item(&mut self, kind: ItemKind, count: u8) -> bool {
        let held = self.inventory.get(&kind).copied().unwrap_or(0);
        if held >= count {
            let new_val = held - count;
            if new_val == 0 {
                self.inventory.remove(&kind);
            } else {
                *self.inventory.get_mut(&kind).unwrap() = new_val;
            }
            true
        } else {
            false
        }
    }

    /// Compact display string for inventory (e.g. "Berry×2 Fish×1").
    pub fn inventory_display(&self) -> String {
        if self.inventory.is_empty() {
            return String::new();
        }
        let mut parts: Vec<String> = self.inventory.iter()
            .map(|(k, &v)| format!("{}×{}", k.label(), v))
            .collect();
        parts.sort();
        parts.join(" ")
    }

    /// Returns memory entries that belong to the given day.
    pub fn today_memories(&self, day: u32) -> Vec<&str> {
        let tag = format!("| Day {} |", day);
        self.memory.iter()
            .filter(|m| m.contains(&tag))
            .map(|m| m.as_str())
            .collect()
    }

    // -----------------------------------------------------------------------
    // Attribute growth (FEAT-21)
    // -----------------------------------------------------------------------

    /// Returns extra DC to add for this attribute when it has been neglected
    /// (no successful use in the last 48 ticks). Returns 0 if no debuff.
    pub fn neglect_extra_dc(&self, attr: &str, current_tick: u32) -> u32 {
        if attr.is_empty() || current_tick < 48 { return 0; }
        let last = self.attribute_last_success.get(attr).copied().unwrap_or(0);
        if current_tick.saturating_sub(last) > 48 { 1 } else { 0 }
    }

    /// Grant 1 XP for `attr`. Returns `Some(new_score)` if the attribute leveled up.
    pub fn grant_xp(&mut self, attr: &str) -> Option<u32> {
        if attr.is_empty() { return None; }
        let xp = self.attribute_xp.entry(attr.to_string()).or_insert(0);
        *xp += 1;
        if *xp >= 5 {
            *xp = 0;
            let score = match attr {
                "vigor" => &mut self.attributes.vigor,
                "wit"   => &mut self.attributes.wit,
                "grace" => &mut self.attributes.grace,
                "heart" => &mut self.attributes.heart,
                "numen" => &mut self.attributes.numen,
                _       => return None,
            };
            if *score < 10 {
                *score += 1;
                return Some(*score);
            }
        }
        None
    }

    /// Record a successful attribute use at `tick` (clears neglect debuff).
    pub fn record_success(&mut self, attr: &str, tick: u32) {
        if !attr.is_empty() {
            self.attribute_last_success.insert(attr.to_string(), tick);
        }
    }

    // -----------------------------------------------------------------------
    // Affinity / relationships (FEAT-18)
    // -----------------------------------------------------------------------

    /// Add `delta` to affinity toward `other`, clamping to -100..=100.
    pub fn update_affinity(&mut self, other: &str, delta: f32) {
        let v = self.affinity.entry(other.to_string()).or_insert(0.0);
        *v = (*v + delta).clamp(-100.0, 100.0);
    }

    /// Chat social restore bonus from affinity (range ≈ -10..=+10).
    pub fn affinity_social_bonus(&self, other_name: &str) -> f32 {
        let v = self.affinity.get(other_name).copied().unwrap_or(0.0);
        (v * 0.1).clamp(-10.0, 10.0)
    }

    // -----------------------------------------------------------------------
    // Theory-of-Mind beliefs (FEAT-23)
    // -----------------------------------------------------------------------

    /// Append a rumor about `about` to this agent's belief map.
    /// Drops the oldest rumor if over `max_per_agent`.
    pub fn update_belief(&mut self, about: &str, rumor: String, max_per_agent: usize) {
        let entry = self.beliefs.entry(about.to_string()).or_insert_with(AgentBeliefs::default);
        entry.rumors.push(rumor);
        while entry.rumors.len() > max_per_agent {
            entry.rumors.remove(0);
        }
    }

    pub fn push_memory(&mut self, entry: String, max_size: usize) {
        self.memory.push_front(entry);
        while self.memory.len() > max_size {
            self.memory.pop_back();
        }
    }

    /// Formatted need warnings for the perception prompt.
    pub fn need_warnings(&self, config: &Config) -> Vec<String> {
        let t  = &config.needs.thresholds;
        let mut w = Vec::new();

        if self.needs.hunger < t.forced_action {
            w.push("You are STARVING. You need food immediately.".into());
        } else if self.needs.hunger < t.penalty_severe {
            w.push("You are very hungry. Your body aches for food.".into());
        } else if self.needs.hunger < t.penalty_mild {
            w.push("You are hungry.".into());
        }

        if self.needs.energy < t.forced_action {
            w.push("You are utterly exhausted. You cannot stay awake.".into());
        } else if self.needs.energy < t.penalty_severe {
            w.push("You are exhausted. You can barely keep your eyes open.".into());
        } else if self.needs.energy < t.penalty_mild {
            w.push("You feel tired.".into());
        }

        if self.needs.fun < t.forced_action {
            w.push("A deep, grey boredom has settled over you.".into());
        } else if self.needs.fun < t.penalty_severe {
            w.push("Life feels dull and joyless.".into());
        }

        if self.needs.social < t.forced_action {
            w.push("You feel achingly lonely, desperate for connection.".into());
        } else if self.needs.social < t.penalty_severe {
            w.push("You crave the company of others.".into());
        }

        if self.needs.hygiene < t.penalty_mild {
            w.push("You are becoming quite grimy.".into());
        }

        w
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // -----------------------------------------------------------------------
    // Test helpers
    // -----------------------------------------------------------------------

    fn minimal_config() -> crate::config::Config {
        crate::config::load("config/world.toml").expect("config/world.toml should load")
    }

    fn minimal_soul_seed(name: &str) -> crate::soul::SoulSeed {
        crate::soul::SoulSeed {
            name:             name.to_string(),
            vigor:            6,
            wit:              6,
            grace:            6,
            heart:            6,
            numen:            6,
            specialty:        None,
            personality:      "quiet and thoughtful".to_string(),
            backstory:        "came from the hills".to_string(),
            magical_affinity: "earth".to_string(),
            self_declaration: "I seek understanding".to_string(),
        }
    }

    fn minimal_agent(name: &str) -> Agent {
        Agent::from_soul(0, &minimal_soul_seed(name), &minimal_config(), (5, 17))
    }

    // -----------------------------------------------------------------------
    // Needs::apply clamping
    // -----------------------------------------------------------------------

    #[test]
    fn needs_apply_clamps_above_100() {
        let mut needs = Needs { hunger: 95.0, energy: 50.0, fun: 50.0, social: 50.0, hygiene: 50.0 };
        let changes = NeedChanges { hunger: Some(20.0), energy: None, fun: None, social: None, hygiene: None };
        needs.apply(&changes);
        assert_eq!(needs.hunger, 100.0, "hunger should be clamped to 100.0, was {}", needs.hunger);
    }

    #[test]
    fn needs_apply_clamps_below_zero() {
        let mut needs = Needs { hunger: 50.0, energy: 3.0, fun: 50.0, social: 50.0, hygiene: 50.0 };
        let changes = NeedChanges { hunger: None, energy: Some(-10.0), fun: None, social: None, hygiene: None };
        needs.apply(&changes);
        assert_eq!(needs.energy, 0.0, "energy should be clamped to 0.0, was {}", needs.energy);
    }

    #[test]
    fn needs_apply_only_modifies_some_fields() {
        let mut needs = Needs { hunger: 50.0, energy: 50.0, fun: 42.0, social: 33.0, hygiene: 77.0 };
        let changes = NeedChanges { hunger: Some(10.0), energy: None, fun: None, social: None, hygiene: None };
        needs.apply(&changes);
        assert_eq!(needs.hunger,  60.0,  "hunger should increase");
        assert_eq!(needs.energy,  50.0,  "energy unchanged");
        assert_eq!(needs.fun,     42.0,  "fun unchanged");
        assert_eq!(needs.social,  33.0,  "social unchanged");
        assert_eq!(needs.hygiene, 77.0,  "hygiene unchanged");
    }

    // -----------------------------------------------------------------------
    // Needs::penalty stacking
    // -----------------------------------------------------------------------

    #[test]
    fn needs_penalty_hunger_severe() {
        let config = minimal_config();
        // Severe threshold from config is 10.0; set hunger to 5.0 (below severe)
        let needs = Needs { hunger: 5.0, energy: 80.0, fun: 80.0, social: 80.0, hygiene: 80.0 };
        // Hunger penalises all checks
        let p = needs.penalty(&config, "vigor");
        assert_eq!(p, -4, "severe hunger should give -4 penalty to vigor, got {}", p);
    }

    #[test]
    fn needs_penalty_energy_physical_only() {
        let config = minimal_config();
        let needs = Needs { hunger: 80.0, energy: 5.0, fun: 80.0, social: 80.0, hygiene: 80.0 };
        // Energy penalises physical checks (vigor, grace) only
        let p_vigor = needs.penalty(&config, "vigor");
        let p_wit   = needs.penalty(&config, "wit");
        assert_eq!(p_vigor, -4, "severe energy should give -4 to vigor");
        assert_eq!(p_wit, 0, "severe energy should NOT penalise wit");
    }

    #[test]
    fn needs_penalty_fun_affects_all() {
        let config = minimal_config();
        // Fun severe (<10) adds -2 to ALL checks
        let needs = Needs { hunger: 80.0, energy: 80.0, fun: 5.0, social: 80.0, hygiene: 80.0 };
        let p_wit   = needs.penalty(&config, "wit");
        let p_vigor = needs.penalty(&config, "vigor");
        assert_eq!(p_wit,   -2, "severe fun should give -2 to wit");
        assert_eq!(p_vigor, -2, "severe fun should give -2 to vigor");
    }

    #[test]
    fn needs_penalty_social_hygiene_heart_only() {
        let config = minimal_config();
        // Social and hygiene <10 each give -2 to heart only
        let needs = Needs { hunger: 80.0, energy: 80.0, fun: 80.0, social: 5.0, hygiene: 5.0 };
        let p_heart = needs.penalty(&config, "heart");
        let p_wit   = needs.penalty(&config, "wit");
        assert_eq!(p_heart, -4, "severe social+hygiene should give -4 to heart");
        assert_eq!(p_wit,    0, "social/hygiene should not penalise wit");
    }

    #[test]
    fn needs_penalty_multiple_stacks() {
        let config = minimal_config();
        // hunger severe(-4) + energy severe(-4) + fun severe(-2) all at 5.0
        // vigor is physical: hunger(-4) + energy(-4) + fun(-2) = -10
        let needs = Needs { hunger: 5.0, energy: 5.0, fun: 5.0, social: 80.0, hygiene: 80.0 };
        let p = needs.penalty(&config, "vigor");
        assert_eq!(p, -10, "stacked penalties should sum to -10 for vigor, got {}", p);
    }

    // -----------------------------------------------------------------------
    // update_belief cap
    // -----------------------------------------------------------------------

    #[test]
    fn update_belief_adds_rumor() {
        let mut agent = minimal_agent("Elara");
        agent.update_belief("Rowan", "likes fish".to_string(), 5);
        let beliefs = agent.beliefs.get("Rowan").expect("Rowan entry should exist");
        assert_eq!(beliefs.rumors.len(), 1);
        assert_eq!(beliefs.rumors[0], "likes fish");
    }

    #[test]
    fn update_belief_drops_oldest_over_cap() {
        let mut agent = minimal_agent("Elara");
        for i in 0..6 {
            agent.update_belief("Rowan", format!("rumor {}", i), 5);
        }
        let beliefs = agent.beliefs.get("Rowan").expect("should exist");
        assert_eq!(beliefs.rumors.len(), 5, "should cap at 5");
        // First rumor "rumor 0" should have been dropped
        assert!(!beliefs.rumors.contains(&"rumor 0".to_string()), "oldest rumor should be gone");
        assert!(beliefs.rumors.contains(&"rumor 5".to_string()), "newest rumor should be present");
    }

    #[test]
    fn update_belief_drops_index_zero_not_last() {
        let mut agent = minimal_agent("Elara");
        agent.update_belief("Rowan", "A".to_string(), 2);
        agent.update_belief("Rowan", "B".to_string(), 2);
        agent.update_belief("Rowan", "C".to_string(), 2);
        let beliefs = agent.beliefs.get("Rowan").expect("should exist");
        assert_eq!(beliefs.rumors.len(), 2, "should cap at 2");
        // A was added first → dropped; should have B and C
        assert!(!beliefs.rumors.contains(&"A".to_string()), "A should be dropped (oldest)");
        assert!(beliefs.rumors.contains(&"B".to_string()), "B should remain");
        assert!(beliefs.rumors.contains(&"C".to_string()), "C should remain");
    }

    // -----------------------------------------------------------------------
    // grant_xp leveling
    // -----------------------------------------------------------------------

    #[test]
    fn grant_xp_levels_up_at_5_xp() {
        let mut agent = minimal_agent("Elara");
        // vigor starts at 6; 5 XP should level it up to 7
        let mut leveled = None;
        for _ in 0..5 {
            leveled = agent.grant_xp("vigor");
        }
        assert!(leveled.is_some(), "5th XP should trigger level-up");
        assert_eq!(leveled.unwrap(), 7, "vigor should go from 6 to 7");
    }

    #[test]
    fn grant_xp_resets_counter_after_levelup() {
        let mut agent = minimal_agent("Elara");
        for _ in 0..5 { agent.grant_xp("vigor"); }
        // After level-up, XP counter should be 0
        let xp = agent.attribute_xp.get("vigor").copied().unwrap_or(0);
        assert_eq!(xp, 0, "XP counter should reset to 0 after level-up");
    }

    #[test]
    fn grant_xp_capped_at_10() {
        let mut agent = minimal_agent("Elara");
        agent.attributes.vigor = 10; // already at cap
        // Grant 5 XP — should NOT level up since already at 10
        let mut leveled = None;
        for _ in 0..5 {
            leveled = agent.grant_xp("vigor");
        }
        assert!(leveled.is_none(), "vigor at 10 should not level up");
        assert_eq!(agent.attributes.vigor, 10, "vigor should remain 10");
    }

    #[test]
    fn grant_xp_returns_none_for_empty_attr() {
        let mut agent = minimal_agent("Elara");
        let result = agent.grant_xp("");
        assert!(result.is_none(), "empty attr should return None");
    }

    // -----------------------------------------------------------------------
    // Inventory
    // -----------------------------------------------------------------------

    #[test]
    fn add_item_respects_max_slots() {
        let mut agent = minimal_agent("Elara");
        agent.add_item(ItemKind::Berry, 3, 2); // max 2 slots
        let total = agent.inventory_count();
        assert_eq!(total, 2, "should only add up to max_slots (2), got {}", total);
    }

    #[test]
    fn consume_item_returns_false_when_not_enough() {
        let mut agent = minimal_agent("Elara");
        agent.add_item(ItemKind::Fish, 1, 10);
        let result = agent.consume_item(ItemKind::Fish, 5); // only have 1, need 5
        assert!(!result, "should return false when not enough items");
        assert_eq!(agent.inventory_count(), 1, "inventory should be unchanged");
    }

    #[test]
    fn consume_item_removes_entry_at_zero() {
        let mut agent = minimal_agent("Elara");
        agent.add_item(ItemKind::Herb, 2, 10);
        let result = agent.consume_item(ItemKind::Herb, 2); // consume all
        assert!(result, "should return true when enough items");
        assert!(!agent.inventory.contains_key(&ItemKind::Herb), "entry should be removed when count reaches 0");
    }
}
