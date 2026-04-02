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
