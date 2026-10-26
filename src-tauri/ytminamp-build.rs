//! YTMinamp's part of the build script: the skins compiled into the app, which it copies into the
//! skins folder the way Winamp's installer drops its bundled skins into `Skins\`
//! (`winamp::bundled`). The public skins always (every `skins/*/YTMinamp-*.wsz`, from the
//! generators beside them); `YTMINAMP_SKINS` adds more: paths
//! relative to the repo (or absolute), separated like `PATH` (`:`, `;` on Windows), each a
//! `.wsz`/`.zip` or a folder searched for them (its subfolders too). Two skins of the same file
//! name are an error.

use std::path::{Path, PathBuf};

pub fn bundle_skins() {
    println!("cargo:rerun-if-env-changed=YTMINAMP_SKINS");
    let repo = Path::new(env!("CARGO_MANIFEST_DIR")).parent().expect("src-tauri is in the repo");
    let mut files = Vec::new();
    let mut named = public_skins(&repo.join("skins"));
    if let Some(extra) = std::env::var_os("YTMINAMP_SKINS") {
        let paths = std::env::split_paths(&extra).filter(|p| !p.as_os_str().is_empty());
        named.extend(paths.map(|p| repo.join(p)));
    }
    for path in named {
        println!("cargo:rerun-if-changed={}", path.display());
        if !path.exists() {
            panic!("YTMINAMP_SKINS: {} not found", path.display());
        } else if path.is_dir() {
            let before = files.len();
            collect(&path, &mut files);
            assert!(files.len() > before, "YTMINAMP_SKINS: no skins in {}", path.display());
        } else if is_skin(&path) {
            files.push(path);
        } else {
            panic!("YTMINAMP_SKINS: {} isn't a .wsz/.zip or a folder", path.display());
        }
    }
    let mut seen = std::collections::BTreeMap::new();
    for f in &files {
        let name = f.file_name().unwrap().to_string_lossy().into_owned();
        if let Some(other) = seen.insert(name.clone(), f) {
            if other != f {
                let (a, b) = (other.display(), f.display());
                panic!("YTMINAMP_SKINS: two skins named {name}: {a} and {b}");
            }
        }
    }
    let mut code = String::from("pub const BUNDLED: &[(&str, &[u8])] = &[\n");
    for (name, path) in &seen {
        code += &format!("    ({name:?}, include_bytes!({:?})),\n", path.to_string_lossy());
    }
    code += "];\n";
    let out = PathBuf::from(std::env::var_os("OUT_DIR").unwrap()).join("bundled_skins.rs");
    std::fs::write(out, code).unwrap();
}

/// `skins/*/YTMinamp-*.wsz`: the skins every build ships, in name order.
fn public_skins(skins: &Path) -> Vec<PathBuf> {
    println!("cargo:rerun-if-changed={}", skins.display());
    let mut found = Vec::new();
    for dir in std::fs::read_dir(skins).unwrap().filter_map(|e| e.ok().map(|e| e.path())) {
        if !dir.is_dir() {
            continue;
        }
        for file in std::fs::read_dir(&dir).unwrap().filter_map(|e| e.ok().map(|e| e.path())) {
            let name = file.file_name().unwrap().to_string_lossy();
            if name.starts_with("YTMinamp-") && is_skin(&file) {
                found.push(file);
            }
        }
    }
    found.sort();
    assert!(!found.is_empty(), "no skins/*/YTMinamp-*.wsz to ship");
    found
}

fn is_skin(p: &Path) -> bool {
    let ext = p.extension().and_then(|x| x.to_str());
    ext.is_some_and(|x| x.eq_ignore_ascii_case("wsz") || x.eq_ignore_ascii_case("zip"))
}

/// Skins in `dir` and its subfolders, in name order; hidden folders and generators' `out/` skipped.
fn collect(dir: &Path, files: &mut Vec<PathBuf>) {
    let mut entries: Vec<PathBuf> =
        std::fs::read_dir(dir).unwrap().filter_map(|e| e.ok().map(|e| e.path())).collect();
    entries.sort();
    for p in entries {
        let name = p.file_name().unwrap().to_string_lossy();
        if p.is_dir() {
            if !name.starts_with('.') && name != "out" {
                collect(&p, files);
            }
        } else if is_skin(&p) {
            files.push(p);
        }
    }
}
