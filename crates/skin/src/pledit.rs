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
            "normal" => result.normal = Some(value.to_owned()),
            "current" => result.current = Some(value.to_owned()),
            "normalbg" => result.normal_bg = Some(value.to_owned()),
            "selectedbg" => result.selected_bg = Some(value.to_owned()),
            "mbbg" => result.mb_bg = Some(value.to_owned()),
            "mbfg" => result.mb_fg = Some(value.to_owned()),
            "font" => result.font = Some(value.to_owned()),
            _ => {}
        }
    }

    result
}
