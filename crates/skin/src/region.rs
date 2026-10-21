//! `region.txt`: defines the skin's non-rectangular window shape as pixel polygons, for the
//! `[Normal]` and `[Equalizer]` windows. Each has a `NumPoints=` list (point count per polygon —
//! multiple polygons per window are the rounded-corner antialiasing steps) paired positionally
//! with a `PointList=` of that many `x,y` pairs per polygon. The file itself is optional — most
//! real skins omit it, in which case the caller falls back to a plain rectangle.

use std::collections::HashMap;

#[derive(Debug, Clone, Default)]
pub struct Region {
    pub normal: Vec<Vec<(i32, i32)>>,
    pub equalizer: Vec<Vec<(i32, i32)>>,
}

pub fn parse(text: &str) -> Region {
    let mut sections: HashMap<String, (Vec<usize>, Vec<(i32, i32)>)> = HashMap::new();
    let mut current: Option<String> = None;

    for raw_line in text.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with(';') || line.starts_with('#') {
            continue;
        }
        if line.starts_with('[') && line.ends_with(']') {
            current = Some(line[1..line.len() - 1].trim().to_lowercase());
            continue;
        }
        let Some(section) = current.clone() else { continue };
        let entry = sections.entry(section).or_default();
        if let Some(rest) = line.strip_prefix("NumPoints=") {
            entry.0 = rest.split(',').filter_map(|s| s.trim().parse().ok()).collect();
        } else if let Some(rest) = line.strip_prefix("PointList=") {
            entry.1 = rest
                .split_whitespace()
                .filter_map(|pair| {
                    let (x, y) = pair.split_once(',')?;
                    Some((x.trim().parse().ok()?, y.trim().parse().ok()?))
                })
                .collect();
        }
    }

    let group = |nums: &[usize], pts: &[(i32, i32)]| -> Vec<Vec<(i32, i32)>> {
        let mut polygons = Vec::new();
        let mut idx = 0;
        for &n in nums {
            match pts.get(idx..idx + n) {
                Some(slice) => polygons.push(slice.to_vec()),
                // A malformed file (counts that overrun the point list) stops grouping rather
                // than panicking — whatever polygons parsed cleanly are kept.
                None => break,
            }
            idx += n;
        }
        polygons
    };

    let normal = sections.get("normal").map(|(n, p)| group(n, p)).unwrap_or_default();
    let equalizer = sections.get("equalizer").map(|(n, p)| group(n, p)).unwrap_or_default();
    Region { normal, equalizer }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Two overlapping rectangles for a rounded main window, one for the EQ, a comment and a
    /// blank line, the way real skins write it.
    const TEXT: &str = "; rounded corners\r\n[Normal]\r\nNumPoints=4,4\r\n\
        PointList=2,0 273,0 273,116 2,116 0,2 275,2 275,114 0,114\r\n\r\n\
        [Equalizer]\r\nNumPoints=4\r\nPointList=0,0 275,0 275,116 0,116\r\n";

    #[test]
    fn polygons_are_grouped_by_their_point_counts() {
        let region = parse(TEXT);
        assert_eq!(region.normal.len(), 2);
        assert_eq!(region.normal[0], vec![(2, 0), (273, 0), (273, 116), (2, 116)]);
        assert_eq!(region.normal[1][3], (0, 114));
        assert_eq!(region.equalizer, vec![vec![(0, 0), (275, 0), (275, 116), (0, 116)]]);
    }

    #[test]
    fn counts_that_overrun_the_points_keep_what_parsed() {
        let region = parse("[Normal]\nNumPoints=4,4\nPointList=0,0 1,0 1,1 0,1 5,5\n");
        assert_eq!(region.normal, vec![vec![(0, 0), (1, 0), (1, 1), (0, 1)]]);
    }

    #[test]
    fn a_commented_out_file_has_no_polygons() {
        let region = parse("; [Normal]\n; NumPoints=4\n; PointList=0,0 1,0 1,1 0,1\n");
        assert!(region.normal.is_empty() && region.equalizer.is_empty());
    }
}
