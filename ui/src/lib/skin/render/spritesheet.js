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
