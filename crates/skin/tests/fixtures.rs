//! Tests against real `.wsz` skins — never synthetic test skins — all three freely licensed (see
//! `fixtures/skins/README.md`):
//!
//! | Skin | Layout | `region.txt` | Digits | BMPs |
//! |---|---|---|---|---|
//! | Winamp 2.91 base (`src-tauri/skins`, the built-in one) | zip root | all commented out | `numbers.bmp` | 8bpp paletted, some RLE8 |
//! | Debian 1.0 | nested under `Debian/` | no | `nums_ex.bmp` | 24bpp |
//! | Antares 1a | zip root | no | `numbers.bmp` | 24bpp |
//!
//! Antares also sets `pledit.txt`'s optional `mbBG`/`mbFG`, the others don't.

fn fixture(name: &str) -> Vec<u8> {
    let path = format!("{}/../../fixtures/skins/{name}", env!("CARGO_MANIFEST_DIR"));
    std::fs::read(&path).unwrap_or_else(|e| panic!("reading fixture {path}: {e}"))
}

fn base() -> skin::Skin {
    let path = format!("{}/../../src-tauri/skins/base-2.91.wsz", env!("CARGO_MANIFEST_DIR"));
    let bytes = std::fs::read(&path).unwrap_or_else(|e| panic!("reading {path}: {e}"));
    skin::load(&bytes).expect("base skin failed to parse")
}

fn debian() -> skin::Skin {
    skin::load(&fixture(DEBIAN)).expect("Debian failed to parse")
}

fn antares() -> skin::Skin {
    skin::load(&fixture(ANTARES)).expect("Antares failed to parse")
}

const DEBIAN: &str = "Debian_1.0.wsz";
const ANTARES: &str = "Antares_1a.wsz";

fn all() -> [(&'static str, skin::Skin); 3] {
    [("base-2.91", base()), ("Debian", debian()), ("Antares", antares())]
}

#[test]
fn main_window_is_275x116_for_every_skin() {
    for (name, skin) in all() {
        let main = skin.sprite("main").unwrap_or_else(|| panic!("{name}: no main sprite"));
        assert_eq!((main.width, main.height), (275, 116), "{name}: unexpected main.bmp size");
    }
}

/// Found even when a skin nests everything under a folder, as Debian does — common among real
/// skins, not an edge case.
#[test]
fn core_sprites_found_regardless_of_zip_nesting() {
    const CORE_SPRITES: &[&str] = &[
        "main", "titlebar", "cbuttons", "shufrep", "monoster", "posbar", "playpaus", "volume",
        "balance", "text", "pledit", "eqmain",
    ];
    for (name, skin) in all() {
        for sprite in CORE_SPRITES {
            assert!(skin.sprite(sprite).is_some(), "{name}: missing {sprite}.bmp");
        }
    }
}

/// The base skin is Winamp mode's built-in one, so it has to have everything that's drawn,
/// including the generic window frame.
#[test]
fn base_skin_has_everything_winamp_mode_draws() {
    let skin = base();
    for sprite in ["numbers", "gen", "genex"] {
        assert!(skin.sprite(sprite).is_some(), "base: missing {sprite}.bmp");
    }
}

#[test]
fn numbers_and_nums_ex_are_alternatives() {
    let debian = debian();
    assert!(debian.sprite("nums_ex").is_some() && debian.sprite("numbers").is_none());
    for (name, skin) in [("base-2.91", base()), ("Antares", antares())] {
        assert!(skin.sprite("numbers").is_some(), "{name}: no numbers.bmp");
    }
}

/// The base skin's bitmaps are 8bpp paletted, several of them RLE8-compressed.
#[test]
fn eight_bit_paletted_and_rle8_bmps_decode() {
    let skin = base();
    for sprite in ["cbuttons", "shufrep", "pledit", "main"] {
        let s = skin.sprite(sprite).unwrap_or_else(|| panic!("base: no {sprite}.bmp"));
        assert_eq!(s.rgba.len(), (s.width * s.height * 4) as usize, "base: {sprite}.bmp");
        // Not a blank decode: a real sprite sheet has more than one colour.
        let first = &s.rgba[..4];
        assert!(s.rgba.chunks(4).any(|p| p != first), "base: {sprite}.bmp decoded to one colour");
    }
}

/// Winamp 2.91 ships `REGION.TXT` as a documented template, every line commented out: parsed,
/// and no polygons, so the window stays a plain rectangle. (Real polygons: region.rs's tests.)
#[test]
fn base_skins_commented_out_region_txt_has_no_polygons() {
    let region = base().region.expect("base: REGION.TXT not read");
    assert!(region.normal.is_empty() && region.equalizer.is_empty());
}

#[test]
fn region_falls_back_to_none_when_absent() {
    for (name, skin) in [("Debian", debian()), ("Antares", antares())] {
        assert!(skin.region.is_none(), "{name} has no region.txt, so no region");
    }
}

#[test]
fn viscolor_parses_for_every_skin() {
    for (name, skin) in all() {
        assert_eq!(skin.viscolor.len(), 24, "{name}: viscolor.txt should give 24 colours");
    }
}

#[test]
fn pledit_optional_keys_are_actually_optional() {
    let antares = antares();
    assert!(antares.pledit.mb_bg.is_some() && antares.pledit.mb_fg.is_some(), "Antares sets mbBG/mbFG");
    for (name, skin) in [("base-2.91", base()), ("Debian", debian())] {
        assert!(skin.pledit.normal.is_some(), "{name}: Normal missing");
        assert!(skin.pledit.mb_bg.is_none(), "{name} has no mbBG");
    }
}

/// The Media Library window's colours come from here when a skin has no genex.bmp of its own.
#[test]
fn base_skins_genex_colours() {
    let genex = skin::genex_colors(base().sprite("genex").unwrap()).unwrap();
    assert_eq!(genex.item_bg, "#000000");
    assert_eq!(genex.item_fg, "#00ff00");
    assert_eq!(genex.window_bg, "#383757");
    assert_eq!(genex.selection, "#0000c6");
    assert_eq!(genex.header_bg, "#484878");
}
