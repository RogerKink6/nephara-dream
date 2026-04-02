//! Dream config loader: reads a JSON file describing a dream world and generates
//! soul seeds + world layout from it, instead of using the hardcoded Nephara village.

use serde::Deserialize;
use std::collections::HashMap;
use std::fs;
use std::path::Path;

use crate::soul::SoulSeed;
use crate::world::{TileType, GRID_W, GRID_H, HOME_POSITIONS};

// ---------------------------------------------------------------------------
// JSON schema types
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct DreamWorldConfig {
    pub world:             DreamWorldMeta,
    pub locations:         Vec<DreamLocation>,
    pub npcs:              Vec<DreamNpc>,
    pub leeloo:            Option<DreamNpc>,
    pub initial_situation: Option<String>,
    pub dream_logic:       Option<DreamLogicConfig>,
}

// ---------------------------------------------------------------------------
// Dream logic configuration
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Deserialize)]
pub struct DreamLogicConfig {
    /// 0.0 = normal world, 1.0 = full surreal
    #[serde(default = "default_intensity")]
    pub intensity: f64,
    /// Per-tick chance of abrupt scene change
    #[serde(default = "default_scene_shift_chance")]
    pub scene_shift_chance: f64,
    /// How much distances warp (0.0 = stable, 1.0 = very fluid)
    #[serde(default = "default_distance_fluidity")]
    pub distance_fluidity: f64,
    /// Whether emotions affect world descriptions
    #[serde(default = "default_emotional_causality")]
    pub emotional_causality: bool,
    /// Per-tick chance of NPC/object transformation
    #[serde(default = "default_transformation_chance")]
    pub transformation_chance: f64,
    /// Time dilation settings
    pub time_dilation: Option<TimeDilationConfig>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct TimeDilationConfig {
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default = "default_min_factor")]
    pub min_factor: f64,
    #[serde(default = "default_max_factor")]
    pub max_factor: f64,
}

fn default_intensity() -> f64 { 0.7 }
fn default_scene_shift_chance() -> f64 { 0.15 }
fn default_distance_fluidity() -> f64 { 0.5 }
fn default_emotional_causality() -> bool { true }
fn default_transformation_chance() -> f64 { 0.1 }
fn default_true() -> bool { true }
fn default_min_factor() -> f64 { 0.5 }
fn default_max_factor() -> f64 { 2.0 }

impl Default for DreamLogicConfig {
    fn default() -> Self {
        DreamLogicConfig {
            intensity: default_intensity(),
            scene_shift_chance: default_scene_shift_chance(),
            distance_fluidity: default_distance_fluidity(),
            emotional_causality: default_emotional_causality(),
            transformation_chance: default_transformation_chance(),
            time_dilation: Some(TimeDilationConfig {
                enabled: true,
                min_factor: default_min_factor(),
                max_factor: default_max_factor(),
            }),
        }
    }
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct DreamWorldMeta {
    pub name:                  String,
    pub atmosphere:            Option<String>,
    pub time_of_day:           Option<String>,
    pub weather:               Option<String>,
    pub dream_logic_intensity: Option<f64>,
    pub god_name:              Option<String>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct DreamLocation {
    pub name:        String,
    pub tile_type:   String,
    pub position:    [u8; 2],
    pub description: Option<String>,
    pub mood:        Option<String>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
pub struct DreamNpc {
    pub name:              String,
    pub archetype:         Option<String>,
    pub vigor:             u32,
    pub wit:               u32,
    pub grace:             u32,
    pub heart:             u32,
    pub numen:             u32,
    pub personality_prompt: String,
    pub backstory:         Option<String>,
    pub magical_affinity:  Option<String>,
    pub self_declaration:  Option<String>,
    pub initial_location:  Option<String>,
    pub backend:           Option<String>,
    pub specialty:         Option<String>,
}

// ---------------------------------------------------------------------------
// Loader
// ---------------------------------------------------------------------------

pub fn load(path: &str) -> Result<DreamWorldConfig, Box<dyn std::error::Error + Send + Sync>> {
    let content = fs::read_to_string(path)
        .map_err(|e| format!("Failed to read dream config '{}': {}", path, e))?;
    let config: DreamWorldConfig = serde_json::from_str(&content)
        .map_err(|e| format!("Failed to parse dream config '{}': {}", path, e))?;

    // Validate attribute sums
    for npc in &config.npcs {
        validate_attrs(&npc.name, npc.vigor, npc.wit, npc.grace, npc.heart, npc.numen)?;
    }
    if let Some(ref leeloo) = config.leeloo {
        validate_attrs(&leeloo.name, leeloo.vigor, leeloo.wit, leeloo.grace, leeloo.heart, leeloo.numen)?;
    }

    Ok(config)
}

fn validate_attrs(name: &str, v: u32, w: u32, g: u32, h: u32, n: u32) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let sum = v + w + g + h + n;
    if sum != 30 {
        return Err(format!(
            "Dream NPC '{}': attributes must sum to 30, got {} (V:{} W:{} G:{} H:{} N:{})",
            name, sum, v, w, g, h, n
        ).into());
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Convert dream NPCs to SoulSeeds
// ---------------------------------------------------------------------------

pub fn npcs_to_seeds(config: &DreamWorldConfig) -> Vec<SoulSeed> {
    let mut seeds: Vec<SoulSeed> = config.npcs.iter()
        .map(|npc| npc_to_seed(npc))
        .collect();

    // Leeloo is always added last (if present)
    if let Some(ref leeloo) = config.leeloo {
        seeds.push(npc_to_seed(leeloo));
    }

    // Sort alphabetically for deterministic ordering
    seeds.sort_by(|a, b| a.name.cmp(&b.name));
    seeds
}

fn npc_to_seed(npc: &DreamNpc) -> SoulSeed {
    SoulSeed {
        name:             npc.name.clone(),
        vigor:            npc.vigor,
        wit:              npc.wit,
        grace:            npc.grace,
        heart:            npc.heart,
        numen:            npc.numen,
        specialty:        npc.specialty.clone().or_else(|| npc.archetype.clone()),
        backend:          npc.backend.clone(),
        personality:      npc.personality_prompt.clone(),
        backstory:        npc.backstory.clone().unwrap_or_else(|| format!("{} appeared one day, as if always meant to be here.", npc.name)),
        magical_affinity: npc.magical_affinity.clone().unwrap_or_else(|| "Their magic follows their nature.".to_string()),
        self_declaration: npc.self_declaration.clone().unwrap_or_else(|| format!("I am {}.", npc.name)),
    }
}

// ---------------------------------------------------------------------------
// Write auto-generated soul seed files
// ---------------------------------------------------------------------------

pub fn write_soul_seeds(seeds: &[SoulSeed], souls_dir: &str) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let dir = Path::new(souls_dir);
    fs::create_dir_all(dir)?;

    for seed in seeds {
        let filename = format!("{}.seed.md", seed.name.to_lowercase());
        let path = dir.join(&filename);

        let content = format!(
            "---\n\
             name: \"{}\"\n\
             vigor: {}\n\
             wit: {}\n\
             grace: {}\n\
             heart: {}\n\
             numen: {}\n\
             summoned: \"2026-04-02\"\n\
             summoner: \"DreamConfig\"\n\
             ---\n\
             \n\
             # {}\n\
             \n\
             ## Personality\n\
             {}\n\
             \n\
             ## Backstory\n\
             {}\n\
             \n\
             ## Magical Affinity\n\
             {}\n\
             \n\
             ## Self-Declaration\n\
             {}\n",
            seed.name, seed.vigor, seed.wit, seed.grace, seed.heart, seed.numen,
            seed.name,
            seed.personality,
            seed.backstory,
            seed.magical_affinity,
            seed.self_declaration,
        );

        fs::write(&path, content)?;
        tracing::info!("Wrote dream soul seed: {}", path.display());
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// Build dream grid
// ---------------------------------------------------------------------------

fn parse_tile_type(s: &str) -> TileType {
    match s.to_lowercase().as_str() {
        "forest"       => TileType::Forest,
        "river"        => TileType::River,
        "square"       => TileType::Square,
        "tavern"       => TileType::Tavern,
        "well"         => TileType::Well,
        "meadow"       => TileType::Meadow,
        "temple"       => TileType::Temple,
        _              => TileType::Open,
    }
}

/// Build a grid from the dream config locations. Locations are painted as small
/// regions (4x4) centered on their specified position. Home tiles are placed at
/// the standard HOME_POSITIONS for each agent.
pub fn build_dream_grid(config: &DreamWorldConfig, n_agents: usize) -> [[TileType; GRID_W]; GRID_H] {
    let mut g = [[TileType::Open; GRID_W]; GRID_H];

    // Paint locations as regions
    for loc in &config.locations {
        let tile = parse_tile_type(&loc.tile_type);
        let cx = loc.position[0] as usize;
        let cy = loc.position[1] as usize;

        // Paint a region around the position (size depends on tile type)
        let (half_w, half_h) = match tile {
            TileType::Forest => (5, 4),
            TileType::River  => (1, 8),
            TileType::Square => (3, 3),
            TileType::Tavern => (2, 2),
            TileType::Well   => (1, 1),
            TileType::Meadow => (4, 4),
            TileType::Temple => (2, 2),
            _                => (2, 2),
        };

        let y_start = cy.saturating_sub(half_h);
        let y_end   = (cy + half_h).min(GRID_H);
        let x_start = cx.saturating_sub(half_w);
        let x_end   = (cx + half_w).min(GRID_W);

        for row in y_start..y_end {
            for col in x_start..x_end {
                g[row][col] = tile;
            }
        }
    }

    // Place home tiles for agents
    for (i, &(hx, hy)) in HOME_POSITIONS[..n_agents].iter().enumerate() {
        for dy in 0..2usize {
            for dx in 0..3usize {
                let ry = hy as usize + dy;
                let rx = hx as usize + dx;
                if ry < GRID_H && rx < GRID_W {
                    g[ry][rx] = TileType::Home(i);
                }
            }
        }
    }

    g
}

/// Resolve an NPC's initial_location name to a grid position.
/// Falls back to the agent's home position.
pub fn resolve_initial_position(
    npc: &DreamNpc,
    locations: &[DreamLocation],
    agent_idx: usize,
) -> (u8, u8) {
    if let Some(ref loc_name) = npc.initial_location {
        for loc in locations {
            if loc.name.eq_ignore_ascii_case(loc_name) {
                return (loc.position[0], loc.position[1]);
            }
        }
    }
    // Fall back to home position
    if agent_idx < HOME_POSITIONS.len() {
        HOME_POSITIONS[agent_idx]
    } else {
        (16, 16) // center of grid
    }
}

// ---------------------------------------------------------------------------
// Resolve initial positions for all seeds (alphabetically sorted)
// ---------------------------------------------------------------------------

/// Returns a map from agent name -> initial position based on config.
pub fn resolve_all_positions(config: &DreamWorldConfig) -> HashMap<String, (u8, u8)> {
    let mut positions = HashMap::new();
    let mut all_npcs: Vec<&DreamNpc> = config.npcs.iter().collect();
    if let Some(ref leeloo) = config.leeloo {
        all_npcs.push(leeloo);
    }
    // Sort alphabetically to match seed ordering
    all_npcs.sort_by(|a, b| a.name.cmp(&b.name));

    for (idx, npc) in all_npcs.iter().enumerate() {
        let pos = resolve_initial_position(npc, &config.locations, idx);
        positions.insert(npc.name.clone(), pos);
    }

    positions
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // -----------------------------------------------------------------------
    // Config loading
    // -----------------------------------------------------------------------

    #[test]
    fn load_dream_example_succeeds() {
        let config = load("config/dream_example.json")
            .expect("config/dream_example.json should load successfully");
        assert_eq!(config.world.name, "The Shifting Isles");
        assert_eq!(config.npcs.len(), 3);
        assert!(config.leeloo.is_some());
        assert!(config.dream_logic.is_some());
    }

    #[test]
    fn load_nonexistent_file_errors() {
        let result = load("config/nonexistent.json");
        assert!(result.is_err());
    }

    #[test]
    fn load_rejects_invalid_attribute_sum() {
        // Create a minimal JSON with bad attribute sum
        let json = r#"{
            "world": {"name": "Test"},
            "locations": [],
            "npcs": [{
                "name": "Bad",
                "vigor": 1, "wit": 1, "grace": 1, "heart": 1, "numen": 1,
                "personality_prompt": "test"
            }]
        }"#;
        let tmp = std::env::temp_dir().join("bad_attrs_test.json");
        std::fs::write(&tmp, json).unwrap();
        let result = load(tmp.to_str().unwrap());
        assert!(result.is_err());
        let err = result.unwrap_err().to_string();
        assert!(err.contains("attributes must sum to 30"), "error should mention attribute sum: {}", err);
        std::fs::remove_file(&tmp).ok();
    }

    #[test]
    fn load_rejects_missing_required_fields() {
        // Missing "world" field
        let json = r#"{"locations": [], "npcs": []}"#;
        let tmp = std::env::temp_dir().join("missing_fields_test.json");
        std::fs::write(&tmp, json).unwrap();
        let result = load(tmp.to_str().unwrap());
        assert!(result.is_err());
        std::fs::remove_file(&tmp).ok();
    }

    // -----------------------------------------------------------------------
    // npcs_to_seeds
    // -----------------------------------------------------------------------

    #[test]
    fn npcs_to_seeds_correct_count_with_leeloo() {
        let config = load("config/dream_example.json").unwrap();
        let seeds = npcs_to_seeds(&config);
        // 3 NPCs + 1 Leeloo = 4
        assert_eq!(seeds.len(), 4, "should have 4 seeds (3 NPCs + Leeloo)");
    }

    #[test]
    fn npcs_to_seeds_sorted_alphabetically() {
        let config = load("config/dream_example.json").unwrap();
        let seeds = npcs_to_seeds(&config);
        let names: Vec<&str> = seeds.iter().map(|s| s.name.as_str()).collect();
        let mut sorted = names.clone();
        sorted.sort();
        assert_eq!(names, sorted, "seeds should be sorted alphabetically");
    }

    #[test]
    fn npcs_to_seeds_attributes_match_config() {
        let config = load("config/dream_example.json").unwrap();
        let seeds = npcs_to_seeds(&config);
        // Find Vesper
        let vesper = seeds.iter().find(|s| s.name == "Vesper").expect("Vesper should be in seeds");
        assert_eq!(vesper.vigor, 4);
        assert_eq!(vesper.wit, 8);
        assert_eq!(vesper.grace, 6);
        assert_eq!(vesper.heart, 5);
        assert_eq!(vesper.numen, 7);
    }

    #[test]
    fn npcs_to_seeds_leeloo_has_backend() {
        let config = load("config/dream_example.json").unwrap();
        let seeds = npcs_to_seeds(&config);
        let leeloo = seeds.iter().find(|s| s.name == "Leeloo").expect("Leeloo should be in seeds");
        assert_eq!(leeloo.backend.as_deref(), Some("hermes"), "Leeloo should have hermes backend");
    }

    #[test]
    fn npcs_to_seeds_without_leeloo() {
        let mut config = load("config/dream_example.json").unwrap();
        config.leeloo = None;
        let seeds = npcs_to_seeds(&config);
        assert_eq!(seeds.len(), 3, "should have 3 seeds without Leeloo");
        assert!(seeds.iter().all(|s| s.name != "Leeloo"));
    }

    #[test]
    fn npc_to_seed_default_backstory() {
        let npc = DreamNpc {
            name: "TestNpc".to_string(),
            archetype: Some("test".to_string()),
            vigor: 6, wit: 6, grace: 6, heart: 6, numen: 6,
            personality_prompt: "A test personality".to_string(),
            backstory: None,
            magical_affinity: None,
            self_declaration: None,
            initial_location: None,
            backend: None,
            specialty: None,
        };
        let seed = npc_to_seed(&npc);
        assert!(seed.backstory.contains("TestNpc"), "default backstory should include NPC name");
        assert!(seed.self_declaration.contains("TestNpc"), "default self-declaration should include NPC name");
    }

    #[test]
    fn npc_to_seed_specialty_falls_back_to_archetype() {
        let npc = DreamNpc {
            name: "Test".to_string(),
            archetype: Some("dream_weaver".to_string()),
            vigor: 6, wit: 6, grace: 6, heart: 6, numen: 6,
            personality_prompt: "test".to_string(),
            backstory: None, magical_affinity: None, self_declaration: None,
            initial_location: None, backend: None, specialty: None,
        };
        let seed = npc_to_seed(&npc);
        assert_eq!(seed.specialty.as_deref(), Some("dream_weaver"));
    }

    // -----------------------------------------------------------------------
    // build_dream_grid
    // -----------------------------------------------------------------------

    #[test]
    fn build_dream_grid_valid_dimensions() {
        let config = load("config/dream_example.json").unwrap();
        let grid = build_dream_grid(&config, 4);
        assert_eq!(grid.len(), GRID_H);
        assert_eq!(grid[0].len(), GRID_W);
    }

    #[test]
    fn build_dream_grid_locations_painted() {
        let config = load("config/dream_example.json").unwrap();
        let grid = build_dream_grid(&config, 4);
        // Coral Library at position [10, 11] is a Temple
        // Temple has half_w=2, half_h=2, so it should be at the center
        assert_eq!(grid[11][10], TileType::Temple,
            "Coral Library position should be Temple tile");
    }

    #[test]
    fn build_dream_grid_homes_placed() {
        let config = load("config/dream_example.json").unwrap();
        let grid = build_dream_grid(&config, 4);
        // Check that home tiles exist for 4 agents
        for i in 0..4 {
            let (hx, hy) = HOME_POSITIONS[i];
            assert_eq!(grid[hy as usize][hx as usize], TileType::Home(i),
                "Home tile for agent {} should exist at ({}, {})", i, hx, hy);
        }
    }

    // -----------------------------------------------------------------------
    // resolve_initial_position / resolve_all_positions
    // -----------------------------------------------------------------------

    #[test]
    fn resolve_initial_position_matches_location() {
        let config = load("config/dream_example.json").unwrap();
        let vesper_npc = config.npcs.iter().find(|n| n.name == "Vesper").unwrap();
        let pos = resolve_initial_position(vesper_npc, &config.locations, 0);
        // Vesper's initial_location is "Coral Library" at [10, 11]
        assert_eq!(pos, (10, 11), "Vesper should resolve to Coral Library position");
    }

    #[test]
    fn resolve_initial_position_fallback_to_home() {
        let config = load("config/dream_example.json").unwrap();
        let npc = DreamNpc {
            name: "NoLoc".to_string(),
            archetype: None,
            vigor: 6, wit: 6, grace: 6, heart: 6, numen: 6,
            personality_prompt: "test".to_string(),
            backstory: None, magical_affinity: None, self_declaration: None,
            initial_location: None, backend: None, specialty: None,
        };
        let pos = resolve_initial_position(&npc, &config.locations, 2);
        assert_eq!(pos, HOME_POSITIONS[2], "should fall back to home position for agent index 2");
    }

    #[test]
    fn resolve_all_positions_has_all_npcs() {
        let config = load("config/dream_example.json").unwrap();
        let positions = resolve_all_positions(&config);
        assert_eq!(positions.len(), 4, "should have 4 positions (3 NPCs + Leeloo)");
        assert!(positions.contains_key("Vesper"));
        assert!(positions.contains_key("Ondra"));
        assert!(positions.contains_key("Thren"));
        assert!(positions.contains_key("Leeloo"));
    }

    // -----------------------------------------------------------------------
    // write_soul_seeds (round-trip)
    // -----------------------------------------------------------------------

    #[test]
    fn write_soul_seeds_creates_parseable_files() {
        let config = load("config/dream_example.json").unwrap();
        let seeds = npcs_to_seeds(&config);
        let tmp_dir = std::env::temp_dir().join("dream_test_souls");
        let _ = std::fs::remove_dir_all(&tmp_dir);

        write_soul_seeds(&seeds, tmp_dir.to_str().unwrap())
            .expect("write_soul_seeds should succeed");

        // Verify each written file can be re-parsed
        for seed in &seeds {
            let filename = format!("{}.seed.md", seed.name.to_lowercase());
            let path = tmp_dir.join(&filename);
            assert!(path.exists(), "seed file {} should exist", filename);

            let content = std::fs::read_to_string(&path).unwrap();
            let parsed = crate::soul::parse(&content)
                .unwrap_or_else(|e| panic!("written seed for {} should re-parse: {}", seed.name, e));
            assert_eq!(parsed.name, seed.name);
            assert_eq!(parsed.vigor, seed.vigor);
            assert_eq!(parsed.wit, seed.wit);
            assert_eq!(parsed.grace, seed.grace);
            assert_eq!(parsed.heart, seed.heart);
            assert_eq!(parsed.numen, seed.numen);
        }

        std::fs::remove_dir_all(&tmp_dir).ok();
    }

    // -----------------------------------------------------------------------
    // parse_tile_type
    // -----------------------------------------------------------------------

    #[test]
    fn parse_tile_type_all_variants() {
        assert_eq!(parse_tile_type("forest"), TileType::Forest);
        assert_eq!(parse_tile_type("river"), TileType::River);
        assert_eq!(parse_tile_type("square"), TileType::Square);
        assert_eq!(parse_tile_type("tavern"), TileType::Tavern);
        assert_eq!(parse_tile_type("well"), TileType::Well);
        assert_eq!(parse_tile_type("meadow"), TileType::Meadow);
        assert_eq!(parse_tile_type("temple"), TileType::Temple);
        assert_eq!(parse_tile_type("unknown"), TileType::Open);
    }

    #[test]
    fn parse_tile_type_case_insensitive() {
        assert_eq!(parse_tile_type("Forest"), TileType::Forest);
        assert_eq!(parse_tile_type("TAVERN"), TileType::Tavern);
    }

    // -----------------------------------------------------------------------
    // validate_attrs
    // -----------------------------------------------------------------------

    #[test]
    fn validate_attrs_accepts_sum_30() {
        assert!(validate_attrs("Test", 6, 6, 6, 6, 6).is_ok());
    }

    #[test]
    fn validate_attrs_rejects_sum_not_30() {
        assert!(validate_attrs("Bad", 1, 1, 1, 1, 1).is_err());
        assert!(validate_attrs("Bad", 10, 10, 10, 10, 10).is_err());
    }

    // -----------------------------------------------------------------------
    // DreamLogicConfig defaults
    // -----------------------------------------------------------------------

    #[test]
    fn dream_logic_config_default_values() {
        let config = DreamLogicConfig::default();
        assert!((config.intensity - 0.7).abs() < f64::EPSILON);
        assert!((config.scene_shift_chance - 0.15).abs() < f64::EPSILON);
        assert!((config.distance_fluidity - 0.5).abs() < f64::EPSILON);
        assert!(config.emotional_causality);
        assert!((config.transformation_chance - 0.1).abs() < f64::EPSILON);
        assert!(config.time_dilation.is_some());
    }
}
