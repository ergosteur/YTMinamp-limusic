use std::collections::HashMap;
use std::io::{Cursor, Read};

use crate::error::Error;

/// The most one file in a skin is read to: a 2048×2048 32-bit BMP (`bmp::MAX_SIDE`) is 16 MiB,
/// classic sprites are a few KiB. Bounds a zip bomb, and a declared size that lies.
const MAX_ENTRY: u64 = 17 << 20;

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
            // Raw: only the name is needed, and an entry this crate can't decompress (encrypted,
            // or an unusual method) is just one file the skin can't use, not a broken skin.
            let file = archive.by_index_raw(i)?;
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
        let file = self.archive.by_index(idx).ok()?;
        if file.size() > MAX_ENTRY {
            return None;
        }
        let mut buf = Vec::with_capacity(file.size() as usize);
        file.take(MAX_ENTRY + 1).read_to_end(&mut buf).ok()?;
        (buf.len() as u64 <= MAX_ENTRY).then_some(buf)
    }

    /// Every basename present (lowercase), so callers can discover e.g. all `*.bmp` files
    /// without hardcoding a fixed list of sprite sheet names.
    pub fn basenames(&self) -> impl Iterator<Item = &str> {
        self.index_by_basename.keys().map(String::as_str)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    /// A zip of `(name, bytes)` entries, deflated.
    fn zip(entries: &[(&str, &[u8])]) -> Vec<u8> {
        let mut w = zip::ZipWriter::new(Cursor::new(Vec::new()));
        let opts = zip::write::SimpleFileOptions::default();
        for (name, bytes) in entries {
            w.start_file(*name, opts).unwrap();
            w.write_all(bytes).unwrap();
        }
        w.finish().unwrap().into_inner()
    }

    #[test]
    fn an_entry_past_the_limit_is_not_read() {
        // 18 MiB of zeros deflates to a few KiB: a small bomb.
        let bomb = vec![0u8; 18 << 20];
        let bytes = zip(&[("Skin/main.bmp", b"BM"), ("Skin/eqmain.bmp", &bomb)]);
        assert!(bytes.len() < 1 << 20);
        let mut archive = SkinArchive::open(&bytes).unwrap();
        assert_eq!(archive.read("MAIN.BMP").as_deref(), Some(&b"BM"[..]));
        assert_eq!(archive.read("eqmain.bmp"), None);
    }
}
