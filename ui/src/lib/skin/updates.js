// ytminamp's update check, in place of Limusic's (see `latest_release` in brand.rs): finds a newer
// `v<Limusic version>-ytminamp.N` release on GitHub. Nothing is signed for the updater, so the
// banner only ever offers the download page.
import { getVersion } from '@tauri-apps/api/app';
import { invoke } from '@tauri-apps/api/core';
import { fullVersion } from './brand.js';

export const RELEASES_URL = 'https://github.com/ergosteur/YTMinamp-limusic/releases/latest';

/** `v1.3.0-ytminamp.6` or `1.3.0-ytminamp.6` → [1, 3, 0, 6]; anything else → null. */
export function releaseKey(/** @type {string} */ tag) {
	const m = /^v?(\d+)\.(\d+)\.(\d+)-ytminamp\.(\d+)$/.exec(tag);
	return m ? m.slice(1).map(Number) : null;
}

/** Whether release key `a` comes after `b`. */
function after(/** @type {number[]} */ a, /** @type {number[]} */ b) {
	const i = a.findIndex((v, i) => v !== b[i]);
	return i >= 0 && a[i] > b[i];
}

/**
 * Updater's `look()` for ytminamp: sets `state.available` to a newer release, if one is out.
 * @param {{ available: { version: string; rollback: boolean } | null; canInstall: boolean }} state
 * @param {boolean} [fresh] ask GitHub now rather than reuse a recent answer (Check for updates)
 * @returns {Promise<boolean>} whether one is available
 */
export async function lookForRelease(state, fresh = false) {
	const current = fullVersion(await getVersion());
	const tag = /** @type {string | null} */ (await invoke('latest_release', { fresh }));
	const latest = tag && releaseKey(tag);
	const ours = releaseKey(current);
	if (!tag || !latest || !ours || !after(latest, ours)) return false;
	state.canInstall = false;
	state.available = { version: tag.replace(/^v/, ''), rollback: false };
	return true;
}
