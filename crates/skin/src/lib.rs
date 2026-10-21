//! Classic Winamp 2.x `.wsz` skin parser.
//!
//! Pure Rust, no Tauri/UI dependency — mirrors how `innertube`/`player` (the limusic crates
//! this project reuses) stay decoupled from any particular runtime, so this crate is
//! unit-testable on its own and a future second skin format (modern Winamp, WMP) can sit
//! alongside it without the two being forced into a shared trait today. There is exactly one
//! format implemented here; no `trait Skin`/`trait SkinRenderer` abstraction has been added,
//! since a trait with a single implementation is speculative generality — add one once a
//! second format's actual shape is known.

mod archive;
mod bmp;
mod error;
mod pledit;
mod region;
mod viscolor;

use std::collections::HashMap;

pub use bmp::Image as Sprite;
pub use error::Error;
pub use pledit::Pledit;
pub use region::Region;

use archive::SkinArchive;

/// A fully parsed classic skin: every `*.bmp` found in the archive, decoded, keyed by its
/// lowercase filename without extension (`"main"`, `"cbuttons"`, `"eqmain"`, ...); the window
/// shape from `region.txt` (`None` if the skin doesn't have one — callers fall back to a plain
/// rectangle); the visualization palette; and the playlist editor's colors/font.
#[derive(Debug, Clone)]
pub struct Skin {
    pub sprites: HashMap<String, Sprite>,
    pub region: Option<Region>,
    pub viscolor: Vec<(u8, u8, u8)>,
    pub pledit: Pledit,
}

impl Skin {
    pub fn sprite(&self, name: &str) -> Option<&Sprite> {
        self.sprites.get(name)
    }
}

/// Parse a `.wsz` file's raw bytes into a [`Skin`]. Takes bytes, not a path — the seam that
/// lets a future skin source (a different archive format, a directory instead of a zip) hand
/// this crate input differently without touching anything else.
pub fn load(bytes: &[u8]) -> Result<Skin, Error> {
    let mut archive = SkinArchive::open(bytes)?;

    let bmp_names: Vec<String> =
        archive.basenames().filter(|name| name.ends_with(".bmp")).map(str::to_owned).collect();

    let mut sprites = HashMap::new();
    for name in bmp_names {
        let Some(data) = archive.read(&name) else { continue };
        match bmp::decode(&name, &data) {
            Ok(image) => {
                let key = name.trim_end_matches(".bmp").to_owned();
                sprites.insert(key, image);
            }
            // `main.bmp` is the one sprite every classic skin needs (it sizes the window) —
            // propagate a decode failure on it. Every other sprite is optional per the original
            // Winamp spec ("WinAmp supplies the behavior for anything you don't include"), so a
            // corrupt extra bitmap (e.g. a skin-specific bonus graphic this app never reads)
            // doesn't take down the whole skin.
            Err(e) if name == "main.bmp" => return Err(e),
            Err(_) => continue,
        }
    }

    if !sprites.contains_key("main") {
        return Err(Error::MissingMainBmp);
    }

    let region = archive
        .read("region.txt")
        .map(|bytes| region::parse(&String::from_utf8_lossy(&bytes)));
    let viscolor = archive
        .read("viscolor.txt")
        .map(|bytes| viscolor::parse(&String::from_utf8_lossy(&bytes)))
        .unwrap_or_default();
    let pledit = archive
        .read("pledit.txt")
        .map(|bytes| pledit::parse(&String::from_utf8_lossy(&bytes)))
        .unwrap_or_default();

    Ok(Skin { sprites, region, viscolor, pledit })
}
