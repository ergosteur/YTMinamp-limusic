//! Minimal BMP decoder for exactly what classic Winamp skins ship: 24-bit BGR or 32-bit BGRX
//! (uncompressed), and 1/4/8-bit paletted, uncompressed or run-length encoded (`BI_RLE8`,
//! `BI_RLE4`). Real skins use all of these — `numbers.bmp` in one fixture is 8bpp paletted,
//! `monoster.bmp` in another is 32bpp, most sprites are 24bpp, and older skins saved by
//! Windows-era paint programs ship RLE8. A general-purpose BMP/image crate would pull in far
//! more format support than this narrow, fixed input ever needs.

use crate::error::Error;

/// A decoded sprite sheet: straight RGBA8, top-down row order, no per-pixel alpha (classic BMP
/// has none — a skin's non-rectangular shape comes from `region.txt`, not from image alpha).
#[derive(Debug, Clone)]
pub struct Image {
    pub width: u32,
    pub height: u32,
    /// `width * height * 4` bytes, row-major, top-down, RGBA8, alpha always 255.
    pub rgba: Vec<u8>,
}

pub fn decode(name: &str, bytes: &[u8]) -> Result<Image, Error> {
    let name = name.to_owned();
    let truncated = || Error::TruncatedBmp { name: name.clone() };

    if bytes.len() < 54 || &bytes[0..2] != b"BM" {
        return Err(Error::NotABmp { name });
    }
    let read_u32 = |off: usize| -> Result<u32, Error> {
        bytes.get(off..off + 4).map(|s| u32::from_le_bytes(s.try_into().unwrap())).ok_or_else(truncated)
    };
    let read_i32 = |off: usize| -> Result<i32, Error> {
        bytes.get(off..off + 4).map(|s| i32::from_le_bytes(s.try_into().unwrap())).ok_or_else(truncated)
    };
    let read_u16 = |off: usize| -> Result<u16, Error> {
        bytes.get(off..off + 2).map(|s| u16::from_le_bytes(s.try_into().unwrap())).ok_or_else(truncated)
    };

    let pixel_offset = read_u32(10)? as usize;
    let header_size = read_u32(14)? as usize;
    let width = read_i32(18)?.unsigned_abs();
    let height_raw = read_i32(22)?;
    let top_down = height_raw < 0;
    let height = height_raw.unsigned_abs();
    let bpp = read_u16(28)?;
    let compression = read_u32(30)?;

    // 0 = BI_RGB (uncompressed), 1 = BI_RLE8, 2 = BI_RLE4. Anything else (bitfields, embedded
    // JPEG/PNG) no skin seen so far uses.
    let supported = matches!(
        (bpp, compression),
        (24 | 32, 0) | (1 | 4 | 8, 0) | (8, 1) | (4, 2)
    );
    if !supported {
        return Err(Error::UnsupportedBmp { name, bpp, compression });
    }

    let row_size = ((bpp as usize * width as usize + 31) / 32) * 4;
    let pixel_data = bytes.get(pixel_offset..).ok_or_else(truncated)?;

    let mut rgba = vec![0u8; width as usize * height as usize * 4];
    let put_pixel = |rgba: &mut [u8], x: u32, y: u32, r: u8, g: u8, b: u8| {
        // BMP rows are bottom-up by default (positive height); flip into top-down output so
        // callers never have to think about BMP's row order.
        let out_y = if top_down { y } else { height - 1 - y };
        let i = (out_y as usize * width as usize + x as usize) * 4;
        rgba[i] = r;
        rgba[i + 1] = g;
        rgba[i + 2] = b;
        rgba[i + 3] = 255;
    };

    match bpp {
        24 | 32 => {
            let stride = (bpp / 8) as usize;
            for y in 0..height {
                let row_start = y as usize * row_size;
                let row = pixel_data.get(row_start..row_start + row_size).ok_or_else(truncated)?;
                for x in 0..width {
                    let p = x as usize * stride;
                    let (b, g, r) = (row[p], row[p + 1], row[p + 2]);
                    // 32bpp's 4th byte is nominally alpha, but classic Winamp skins don't rely
                    // on real per-pixel alpha (shape comes from region.txt) — ignored here, same
                    // as 24bpp, rather than risk treating stray/garbage bytes as transparency.
                    put_pixel(&mut rgba, x, y, r, g, b);
                }
            }
        }
        1 | 4 | 8 => {
            // Palette: RGBQUAD[] (4 bytes each, BGRX) immediately after the info header.
            let palette_start = 14 + header_size;
            let palette_bytes = bytes.get(palette_start..pixel_offset).ok_or_else(truncated)?;
            let palette_len = palette_bytes.len() / 4;
            let indices = if compression == 0 {
                unpack_rows(pixel_data, width, height, bpp, row_size).ok_or_else(truncated)?
            } else {
                unpack_rle(pixel_data, width, height, compression == 2).ok_or_else(truncated)?
            };
            for y in 0..height {
                for x in 0..width {
                    let idx = indices[y as usize * width as usize + x as usize] as usize;
                    if idx >= palette_len {
                        return Err(truncated());
                    }
                    let entry = &palette_bytes[idx * 4..idx * 4 + 4];
                    let (b, g, r) = (entry[0], entry[1], entry[2]);
                    put_pixel(&mut rgba, x, y, r, g, b);
                }
            }
        }
        other => return Err(Error::UnsupportedBmp { name, bpp: other, compression }),
    }

    Ok(Image { width, height, rgba })
}

/// Uncompressed 1/4/8-bit rows → one palette index per pixel, in the file's row order. Within a
/// byte, the leftmost pixel is in the high bits. `None` if the data runs short.
fn unpack_rows(data: &[u8], width: u32, height: u32, bpp: u16, row_size: usize) -> Option<Vec<u8>> {
    let (w, bits) = (width as usize, bpp as usize);
    let per_byte = 8 / bits;
    let mask = ((1u16 << bits) - 1) as u8;
    let mut out = vec![0u8; w * height as usize];
    for y in 0..height as usize {
        let row = data.get(y * row_size..y * row_size + row_size)?;
        for x in 0..w {
            let byte = row[x / per_byte];
            let shift = 8 - bits * (x % per_byte + 1);
            out[y * w + x] = (byte >> shift) & mask;
        }
    }
    Some(out)
}

/// `BI_RLE8` / `BI_RLE4` → one palette index per pixel, in the file's row order (bottom-up: RLE
/// bitmaps can't be top-down). Pixels the stream skips (end-of-line early, deltas) stay index 0,
/// which is what Windows shows there. `None` if the stream runs short.
fn unpack_rle(data: &[u8], width: u32, height: u32, nibbles: bool) -> Option<Vec<u8>> {
    let (w, h) = (width as usize, height as usize);
    let mut out = vec![0u8; w * h];
    let mut set = |x: usize, y: usize, v: u8| {
        if x < w && y < h {
            out[y * w + x] = v;
        }
    };
    // Pixel `k` of a run or literal: RLE8 takes whole bytes; RLE4 alternates high/low nibbles.
    let nibble = |byte: u8, k: usize| if k % 2 == 0 { byte >> 4 } else { byte & 0x0f };
    let (mut x, mut y, mut i) = (0usize, 0usize, 0usize);
    while y < h {
        let (count, value) = (*data.get(i)? as usize, *data.get(i + 1)?);
        i += 2;
        if count > 0 {
            // Encoded run: `count` pixels of `value`.
            for k in 0..count {
                set(x, y, if nibbles { nibble(value, k) } else { value });
                x += 1;
            }
            continue;
        }
        match value {
            0 => {
                x = 0;
                y += 1;
            }
            1 => break,
            2 => {
                x += *data.get(i)? as usize;
                y += *data.get(i + 1)? as usize;
                i += 2;
            }
            n => {
                // Absolute mode: `n` literal pixels, padded to a 16-bit boundary.
                let n = n as usize;
                let len = if nibbles { n.div_ceil(2) } else { n };
                let literal = data.get(i..i + len)?;
                for k in 0..n {
                    set(x, y, if nibbles { nibble(literal[k / 2], k) } else { literal[k] });
                    x += 1;
                }
                i += len + len % 2;
            }
        }
    }
    Some(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A BMP file around `pixels` with a 2-color palette (index 0 black, 1 red).
    fn bmp(width: i32, height: i32, bpp: u16, compression: u32, pixels: &[u8]) -> Vec<u8> {
        let palette: [u8; 8] = [0, 0, 0, 0, 0, 0, 255, 0];
        let offset = 14 + 40 + palette.len() as u32;
        let mut f = Vec::new();
        f.extend_from_slice(b"BM");
        f.extend_from_slice(&(offset + pixels.len() as u32).to_le_bytes());
        f.extend_from_slice(&[0; 4]);
        f.extend_from_slice(&offset.to_le_bytes());
        f.extend_from_slice(&40u32.to_le_bytes());
        f.extend_from_slice(&width.to_le_bytes());
        f.extend_from_slice(&height.to_le_bytes());
        f.extend_from_slice(&1u16.to_le_bytes());
        f.extend_from_slice(&bpp.to_le_bytes());
        f.extend_from_slice(&compression.to_le_bytes());
        f.extend_from_slice(&[0; 20]);
        f.extend_from_slice(&palette);
        f.extend_from_slice(pixels);
        f
    }

    /// Top-down rows of 'R' (red) / '.' (black) for an RGBA image.
    fn render(img: &Image) -> Vec<String> {
        img.rgba
            .chunks(img.width as usize * 4)
            .map(|row| row.chunks(4).map(|p| if p[0] == 255 { 'R' } else { '.' }).collect())
            .collect()
    }

    #[test]
    fn rle8_runs_literals_and_deltas() {
        // 4x3, bottom-up. Bottom row: run of 2 red, run of 2 black. Middle: literal R . R .
        // Top: delta right by 3 (x=3), then one red.
        let data = [
            2, 1, 2, 0, 0, 0, //
            0, 4, 1, 0, 1, 0, 0, 0, //
            0, 2, 3, 0, 1, 1, 0, 1,
        ];
        let img = decode("t.bmp", &bmp(4, 3, 8, 1, &data)).unwrap();
        assert_eq!(render(&img), ["...R", "R.R.", "RR.."]);
    }

    #[test]
    fn rle4_nibbles_and_odd_literal_padding() {
        // 3x2, bottom-up. Bottom: run of 3 alternating 1,0,1 (byte 0x10). Top: literal 0,1,1
        // (3 nibbles = 2 bytes, already 16-bit aligned).
        let data = [3, 0x10, 0, 0, 0, 3, 0x01, 0x10, 0, 1];
        let img = decode("t.bmp", &bmp(3, 2, 4, 2, &data)).unwrap();
        assert_eq!(render(&img), [".RR", "R.R"]);
    }

    #[test]
    fn uncompressed_32bpp_ignores_the_fourth_byte() {
        // 2x1 BGRX: red then black, with junk in the X byte (some skins have it).
        let pixels = [0, 0, 255, 0x7f, 0, 0, 0, 0xff];
        let img = decode("t.bmp", &bmp(2, 1, 32, 0, &pixels)).unwrap();
        assert_eq!(render(&img), ["R."]);
        assert!(img.rgba.chunks(4).all(|p| p[3] == 255), "alpha is always opaque");
    }

    #[test]
    fn uncompressed_1bpp() {
        // 3x1: bits 101 in the high bits, row padded to 4 bytes.
        let img = decode("t.bmp", &bmp(3, 1, 1, 0, &[0b1010_0000, 0, 0, 0])).unwrap();
        assert_eq!(render(&img), ["R.R"]);
    }
}
