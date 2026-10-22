// Winamp mode's remembered UI state (winamp.json's `ui` object, winamp.rs): panel placement, the
// EQ, double size, always on top, the time display. Every Winamp window loads it on open and saves
// the keys it changes; Rust merges per key, so windows don't undo each other's saves.
import * as api from '$lib/api';

/** @type {Record<string, any>} */
let cache = {};
/** @type {Record<string, any>} */
let pending = {};
let timer = /** @type {ReturnType<typeof setTimeout> | undefined} */ (undefined);

/** Load the remembered state (empty on a first run or an unreadable file). */
export async function loadPrefs() {
	cache = await api.winampPrefs().catch(() => ({}));
	return cache;
}

/**
 * @template T
 * @param {string} key @param {T} fallback
 * @returns {T}
 */
export function pref(key, fallback) {
	return key in cache ? cache[key] : fallback;
}

/**
 * Remember `value` under `key`. Batched: a slider drag is many changes and one write.
 * @param {string} key @param {any} value
 */
export function savePref(key, value) {
	cache[key] = value;
	pending[key] = value;
	clearTimeout(timer);
	timer = setTimeout(() => flushPrefs().catch((e) => console.error('saving winamp prefs failed', e)), 400);
}

/** Write what's waiting now, for a window about to close. */
export function flushPrefs() {
	clearTimeout(timer);
	const patch = pending;
	pending = {};
	return Object.keys(patch).length ? api.setWinampPrefs(patch) : Promise.resolve();
}
