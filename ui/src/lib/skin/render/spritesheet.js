/** @typedef {import("../skinApi.js").SpritePayload} SpritePayload */

/**
 * Decodes a sprite's `data:image/png;base64,...` URL (built once, in Rust — see
 * `src-tauri/src/winamp.rs`) into an `ImageBitmap`, once per sprite.
 * @param {SpritePayload} sprite
 * @returns {Promise<ImageBitmap>}
 */
export async function decodeSprite(sprite) {
  const res = await fetch(sprite.pngDataUrl);
  const blob = await res.blob();
  return createImageBitmap(blob);
}

/**
 * Decodes every sprite in a skin payload's `sprites` map, keyed the same way.
 * @param {Record<string, SpritePayload>} sprites
 * @returns {Promise<Map<string, ImageBitmap>>}
 */
export async function decodeAllSprites(sprites) {
  const entries = await Promise.all(
    Object.entries(sprites).map(async ([name, sprite]) => [name, await decodeSprite(sprite)]),
  );
  return new Map(entries);
}

/** The EQ's sliders in eqmain.bmp (render/equalizer.js): the thumbs at (0, 164) and (0, 176), 11x11,
 * and the background frames, 28 of 14x63 from (13, 164), 15 apart and two rows 65 apart. */
const EQ_SLIDER_FRAMES = { x: 0, y: 164, w: 13 + 14 * 15, h: 65 + 63 };

/**
 * YTMinamp's one skin extension: pledit.txt's `YTMinampTransparent=#rrggbb` is see-through in the
 * EQ's sliders (backgrounds and thumbs), which Winamp draws opaque at all eleven from the same
 * frames, so a picture behind them shows between the slider marks. Only there: the same colour elsewhere in a
 * skin stays put. Real Winamp ignores the key and draws the colour as it is.
 * @param {Map<string, ImageBitmap>} sprites @param {string | undefined} colour `#rrggbb`
 * @returns {Promise<Map<string, ImageBitmap>>}
 */
export async function keyOutEqSliders(sprites, colour) {
  const sheet = sprites.get("eqmain");
  const f = EQ_SLIDER_FRAMES;
  if (!sheet || !colour || sheet.width <= f.x || sheet.height <= f.y) return sprites;
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(colour.slice(i, i + 2), 16));
  const canvas = new OffscreenCanvas(sheet.width, sheet.height);
  const ctx = canvas.getContext("2d");
  if (!ctx) return sprites;
  ctx.drawImage(sheet, 0, 0);
  const w = Math.min(f.w, sheet.width - f.x);
  const h = Math.min(f.h, sheet.height - f.y);
  const image = ctx.getImageData(f.x, f.y, w, h);
  const px = image.data;
  for (let i = 0; i < px.length; i += 4) {
    if (px[i] === r && px[i + 1] === g && px[i + 2] === b) px[i + 3] = 0;
  }
  ctx.putImageData(image, f.x, f.y);
  return new Map(sprites).set("eqmain", await createImageBitmap(canvas));
}
