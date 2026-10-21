//! `viscolor.txt`: a palette for the spectrum analyzer / oscilloscope visualization, nominally
//! 24 slots (background x2, 15 spectrum bars, 5 oscilloscope lines, 1 peak-dot color) but **not
//! reliably exactly 24 in the wild** — one sampled real skin has 26 lines and no comments at
//! all, so this is kept as a plain `Vec`, not a fixed-size array; callers index defensively
//! (clamp/modulo) rather than assuming a slot exists.
//!
//! Format: `R,G,B` per line, optionally followed by a `//` comment (format/spacing of the
//! comment varies between skins — some use multiple spaces, some a tab); ints may have leading
//! zeros (`"0,034,099"`). Not strict CSV: whitespace and comment style are not validated.

pub fn parse(text: &str) -> Vec<(u8, u8, u8)> {
    text.lines()
        .filter_map(|line| {
            let color_part = line.split("//").next().unwrap_or("").trim();
            if color_part.is_empty() {
                return None;
            }
            let mut parts = color_part.split(',').map(str::trim);
            let r = parts.next()?.parse().ok()?;
            let g = parts.next()?.parse().ok()?;
            let b = parts.next()?.parse().ok()?;
            Some((r, g, b))
        })
        .collect()
}
