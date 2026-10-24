//! `genex.bmp`'s colours: the Media Library's palette (Winamp 2.9 and later). Besides its
//! button and scrollbar graphics, the sheet carries one colour per pixel along its top row,
//! every other pixel from x = 48: list items, the window around them, list headers, scrollbars.
//! Read by Winamp mode's Media Library window to colour Limusic's pages.

use crate::bmp::Image;

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Genex {
    pub item_bg: String,
    pub item_fg: String,
    pub window_bg: String,
    pub button_text: String,
    pub window_text: String,
    /// Dividers and sunken borders.
    pub divider: String,
    /// The selection bar in lists.
    pub selection: String,
    pub header_bg: String,
    pub header_text: String,
    pub header_frame_light: String,
    pub header_frame_dark: String,
    pub header_frame_pressed: String,
    pub header_dead_area: String,
    pub scrollbar: String,
    pub scrollbar_2: String,
    pub scrollbar_pressed: String,
    pub scrollbar_pressed_2: String,
    pub scrollbar_dead_area: String,
}

/// Where the colours start along the top row, and how many there are, one every other pixel.
const FIRST_X: u32 = 48;
const COUNT: u32 = 18;

/// The palette in `image` (a skin's `genex.bmp`), or `None` if it's too narrow to hold one.
pub fn colors(image: &Image) -> Option<Genex> {
    if image.height == 0 || image.width < FIRST_X + 2 * (COUNT - 1) + 1 {
        return None;
    }
    let at = |i: u32| {
        let p = ((FIRST_X + 2 * i) * 4) as usize;
        let [r, g, b] = [image.rgba[p], image.rgba[p + 1], image.rgba[p + 2]];
        format!("#{r:02x}{g:02x}{b:02x}")
    };
    Some(Genex {
        item_bg: at(0),
        item_fg: at(1),
        window_bg: at(2),
        button_text: at(3),
        window_text: at(4),
        divider: at(5),
        selection: at(6),
        header_bg: at(7),
        header_text: at(8),
        header_frame_light: at(9),
        header_frame_dark: at(10),
        header_frame_pressed: at(11),
        header_dead_area: at(12),
        scrollbar: at(13),
        scrollbar_2: at(14),
        scrollbar_pressed: at(15),
        scrollbar_pressed_2: at(16),
        scrollbar_dead_area: at(17),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn image(width: u32, row: &[(u32, [u8; 3])]) -> Image {
        let mut rgba = vec![0; (width * 2 * 4) as usize];
        for (x, [r, g, b]) in row {
            let p = (x * 4) as usize;
            rgba[p..p + 3].copy_from_slice(&[*r, *g, *b]);
        }
        Image { width, height: 2, rgba }
    }

    #[test]
    fn reads_every_other_pixel_from_x_48() {
        let genex = colors(&image(130, &[(48, [1, 2, 3]), (49, [9, 9, 9]), (50, [0, 255, 0]), (82, [36, 36, 60])])).unwrap();
        assert_eq!(genex.item_bg, "#010203");
        assert_eq!(genex.item_fg, "#00ff00");
        assert_eq!(genex.scrollbar_dead_area, "#24243c");
    }

    #[test]
    fn too_narrow_is_none() {
        assert_eq!(colors(&image(82, &[])), None);
    }
}
