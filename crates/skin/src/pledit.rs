//! `pledit.txt`: playlist editor colors + font, one `[Text]` section of flat `key=value` pairs
//! (hex color strings like `#FFFFFF`, plus a plain font name). Small and irregular enough
//! across real skins (optional keys, stray comment lines before the section, tabs vs. `;`
//! comments) that a hand parser is simpler and more forgiving than pulling in a general INI
//! crate for a 7-key format.

#[derive(Debug, Clone, Default, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Pledit {
    pub normal: Option<String>,
    pub current: Option<String>,
    pub normal_bg: Option<String>,
    pub selected_bg: Option<String>,
    pub mb_bg: Option<String>,
    pub mb_fg: Option<String>,
    pub font: Option<String>,
    /// YTMinamp's extension, `YTMinampTransparent=#rrggbb`: a colour drawn see-through in the EQ's
    /// slider backgrounds. Real Winamp ignores the key and shows the colour as it is.
    pub ytminamp_transparent: Option<String>,
}

pub fn parse(text: &str) -> Pledit {
    let mut result = Pledit::default();
    let mut in_text_section = false;

    for raw_line in text.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with(';') || line.starts_with('#') {
            continue;
        }
        if line.starts_with('[') && line.ends_with(']') {
            in_text_section = line[1..line.len() - 1].trim().eq_ignore_ascii_case("text");
            continue;
        }
        if !in_text_section {
            continue;
        }
        let Some((key, value)) = line.split_once('=') else { continue };
        let value = value.trim();
        if value.is_empty() {
            continue;
        }
        match key.trim().to_lowercase().as_str() {
            "normal" => result.normal = color(value),
            "current" => result.current = color(value),
            "normalbg" => result.normal_bg = color(value),
            "selectedbg" => result.selected_bg = color(value),
            "mbbg" => result.mb_bg = color(value),
            "mbfg" => result.mb_fg = color(value),
            "font" => result.font = font(value),
            "ytminamptransparent" => result.ytminamp_transparent = color(value),
            _ => {}
        }
    }

    result
}

/// A colour as `#rrggbb`, from `#RRGGBB`, `RRGGBB` or `#RGB` (anything after it ignored, as stray
/// comments are); `None` for anything else. These values go into the UI's CSS, so nothing but a
/// colour may come through: a skin from the web could otherwise add rules (a remote `url()`, say).
fn color(value: &str) -> Option<String> {
    let token = value.split(|c: char| c.is_whitespace() || c == ';').next()?;
    let hex = token.strip_prefix('#').unwrap_or(token);
    if !hex.chars().all(|c| c.is_ascii_hexdigit()) {
        return None;
    }
    match hex.len() {
        6 => Some(format!("#{}", hex.to_ascii_lowercase())),
        3 => {
            let doubled: String = hex.chars().flat_map(|c| [c, c]).collect();
            Some(format!("#{}", doubled.to_ascii_lowercase()))
        }
        _ => None,
    }
}

/// A font name with nothing that could end a CSS string or declaration (quotes, `;`, braces,
/// brackets, backslashes, control characters), at most 64 characters; `None` if nothing's left.
fn font(value: &str) -> Option<String> {
    let name: String = value
        .chars()
        .filter(|c| !c.is_control() && !"\"';\\{}()<>[]".contains(*c))
        .take(64)
        .collect();
    let name = name.trim();
    (!name.is_empty()).then(|| name.to_owned())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn colours_and_font_are_kept_to_what_css_can_take() {
        let p = parse(
            "[Text]\nNormal=#00FF00\nCurrent=FFFFFF ; white\n\
             NormalBG=#000; background:url(https://x)\nSelectedBG=red\nmbBG=#12345\n\
             Font=Arial\"; color: red; x:url(y)\n",
        );
        assert_eq!(p.normal.as_deref(), Some("#00ff00"));
        assert_eq!(p.current.as_deref(), Some("#ffffff"));
        assert_eq!(p.normal_bg.as_deref(), Some("#000000"));
        assert_eq!(p.selected_bg, None);
        assert_eq!(p.mb_bg, None);
        assert_eq!(p.font.as_deref(), Some("Arial color: red x:urly"));
    }

    #[test]
    fn the_transparent_colour_is_optional_and_a_colour_only() {
        assert_eq!(parse("[Text]\nYTMinampTransparent=#1A2B3C\n").ytminamp_transparent.as_deref(), Some("#1a2b3c"));
        assert_eq!(parse("[Text]\nytminamptransparent=nope\n").ytminamp_transparent, None);
        assert_eq!(parse("[Text]\nNormal=#00FF00\n").ytminamp_transparent, None);
    }
}
