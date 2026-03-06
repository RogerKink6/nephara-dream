use colored::Color;
use ratatui::style::Color as RatColor;

use crate::world::TileType;

// ---------------------------------------------------------------------------
// Agent colors (indexed by agent sort order: Elara=0, Rowan=1, Thane=2)
// ---------------------------------------------------------------------------

pub const AGENT_COLORS: &[Color] = &[
    Color::BrightCyan,    // 0
    Color::BrightGreen,   // 1
    Color::BrightYellow,  // 2
    Color::BrightRed,     // 3
    Color::BrightBlue,    // 4
    Color::BrightMagenta, // 5
    Color::Cyan,          // 6
    Color::Green,         // 7
];

pub fn agent_color(id: usize) -> Color {
    AGENT_COLORS.get(id).copied().unwrap_or(Color::White)
}

// ---------------------------------------------------------------------------
// Tile colors
// ---------------------------------------------------------------------------

pub fn tile_color(tile: TileType) -> Color {
    match tile {
        TileType::Open    => Color::BrightBlack,
        TileType::Forest  => Color::Green,
        TileType::River   => Color::Blue,
        TileType::Square  => Color::Yellow,
        TileType::Tavern  => Color::BrightYellow,
        TileType::Well    => Color::Cyan,
        TileType::Meadow  => Color::BrightGreen,
        TileType::Home(_) => Color::Magenta,
        TileType::Temple  => Color::BrightMagenta,
    }
}

// ---------------------------------------------------------------------------
// Outcome tier colors
// ---------------------------------------------------------------------------

pub fn tier_color(tier_label: &str) -> Color {
    match tier_label {
        "Critical Success" => Color::BrightGreen,
        "Success"          => Color::Green,
        "Fail"             => Color::Red,
        "Critical Fail"    => Color::BrightRed,
        _                  => Color::White,
    }
}

// ---------------------------------------------------------------------------
// Need value colors
// ---------------------------------------------------------------------------

pub fn needs_color(value: f32) -> Color {
    if value > 60.0       { Color::Green }
    else if value >= 20.0 { Color::Yellow }
    else                  { Color::Red }
}

// ---------------------------------------------------------------------------
// Location name colors (matched on string contents)
// ---------------------------------------------------------------------------

pub fn to_ratatui_color(c: Color) -> RatColor {
    match c {
        Color::Black        => RatColor::Black,
        Color::Red          => RatColor::Red,
        Color::Green        => RatColor::Green,
        Color::Yellow       => RatColor::Yellow,
        Color::Blue         => RatColor::Blue,
        Color::Magenta      => RatColor::Magenta,
        Color::Cyan         => RatColor::Cyan,
        Color::White        => RatColor::White,
        Color::BrightBlack  => RatColor::DarkGray,
        Color::BrightRed    => RatColor::LightRed,
        Color::BrightGreen  => RatColor::LightGreen,
        Color::BrightYellow => RatColor::LightYellow,
        Color::BrightBlue   => RatColor::LightBlue,
        Color::BrightMagenta=> RatColor::LightMagenta,
        Color::BrightCyan   => RatColor::LightCyan,
        Color::BrightWhite  => RatColor::White,
        _                   => RatColor::Reset,
    }
}

pub fn location_color(loc: &str) -> Color {
    if loc.contains("Forest")       { Color::Green }
    else if loc.contains("River")   { Color::Blue }
    else if loc.contains("Square")  { Color::Yellow }
    else if loc.contains("Tavern")  { Color::BrightYellow }
    else if loc.contains("Well")    { Color::Cyan }
    else if loc.contains("Meadow")  { Color::BrightGreen }
    else if loc.contains("Home")    { Color::Magenta }
    else if loc.contains("Temple")  { Color::BrightMagenta }
    else                            { Color::BrightBlack }
}
