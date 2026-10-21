//! Parse every `.wsz`/`.zip` in a folder and report which ones fail, and why:
//! `cargo run -p skin --example check_skins -- <dir>`
fn main() {
    let dir = std::env::args().nth(1).expect("usage: check_skins <dir>");
    let mut paths: Vec<_> = std::fs::read_dir(&dir)
        .expect("can't read dir")
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().is_some_and(|x| x.eq_ignore_ascii_case("wsz") || x.eq_ignore_ascii_case("zip")))
        .collect();
    paths.sort();
    let mut failed = 0;
    for path in &paths {
        let name = path.file_name().unwrap().to_string_lossy();
        match std::fs::read(path).map_err(|e| e.to_string()).and_then(|b| skin::load(&b).map_err(|e| e.to_string())) {
            Ok(skin) => {
                let mut missing: Vec<_> = ["gen", "eqmain", "pledit", "text"]
                    .into_iter()
                    .filter(|s| !skin.sprites.contains_key(*s))
                    .collect();
                missing.sort();
                println!("ok    {name}{}", if missing.is_empty() { String::new() } else { format!("  (no {})", missing.join(", ")) });
            }
            Err(e) => {
                failed += 1;
                println!("FAIL  {name}: {e}");
            }
        }
    }
    println!("{} skins, {failed} failed", paths.len());
}
