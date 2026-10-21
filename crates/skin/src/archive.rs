use std::collections::HashMap;
use std::io::{Cursor, Read};

use crate::error::Error;

/// A `.wsz` is just a zip file. Real-world skins disagree on layout: some put every file at
/// the zip root, others nest everything under a folder named after the skin (e.g. `Excel and
/// Menchi/main.bmp`). Lookup is therefore always by basename, case-insensitive, regardless of
/// nesting depth — never by a path assumed to start at the root.
pub struct SkinArchive {
    archive: zip::ZipArchive<Cursor<Vec<u8>>>,
    /// lowercase basename -> index into `archive`. First match wins if a name somehow repeats
    /// under multiple directories (not expected for a single skin).
    index_by_basename: HashMap<String, usize>,
}

impl SkinArchive {
    pub fn open(bytes: &[u8]) -> Result<Self, Error> {
        let mut archive = zip::ZipArchive::new(Cursor::new(bytes.to_vec()))?;
        let mut index_by_basename = HashMap::new();
        for i in 0..archive.len() {
            let file = archive.by_index(i)?;
            if file.is_dir() {
                continue;
            }
            let name = file.name().to_owned();
            drop(file);
            if let Some(base) = name.rsplit(['/', '\\']).next() {
                index_by_basename.entry(base.to_lowercase()).or_insert(i);
            }
        }
        Ok(SkinArchive { archive, index_by_basename })
    }

    /// Read a file's bytes by basename (e.g. `"main.bmp"`, `"region.txt"`), case-insensitive.
    /// `None` if the skin doesn't include that file — most of these files are optional in the
    /// original Winamp spec, so a missing one is not an error, just a gap the caller decides
    /// how to fill.
    pub fn read(&mut self, filename: &str) -> Option<Vec<u8>> {
        let idx = *self.index_by_basename.get(&filename.to_lowercase())?;
        let mut file = self.archive.by_index(idx).ok()?;
        let mut buf = Vec::with_capacity(file.size() as usize);
        file.read_to_end(&mut buf).ok()?;
        Some(buf)
    }

    /// Every basename present (lowercase), so callers can discover e.g. all `*.bmp` files
    /// without hardcoding a fixed list of sprite sheet names.
    pub fn basenames(&self) -> impl Iterator<Item = &str> {
        self.index_by_basename.keys().map(String::as_str)
    }
}
