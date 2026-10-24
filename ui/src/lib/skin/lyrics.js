// The lyrics panel's romanization and translation switches, for its right-click menu: Limusic's
// own (LyricsView.svelte), the same localStorage keys and defaults, so a switch flipped in either
// place applies in both, and the `storage` event carries it between windows.

const SHOW_KEYS = { romanized: 'lyrics_romanized', translated: 'lyrics_translated' };
const SHOW_DEFAULTS = { romanized: false, translated: true };

/** @param {'romanized' | 'translated'} what */
function loadShow(what) {
	try {
		const v = localStorage.getItem(SHOW_KEYS[what]);
		return v === null ? SHOW_DEFAULTS[what] : v === '1';
	} catch {
		return SHOW_DEFAULTS[what];
	}
}

/** What the lyrics show under each line. */
export const lyricsShow = { romanized: loadShow('romanized'), translated: loadShow('translated') };
window.addEventListener('storage', (e) => {
	if (e.key === SHOW_KEYS.romanized) lyricsShow.romanized = loadShow('romanized');
	if (e.key === SHOW_KEYS.translated) lyricsShow.translated = loadShow('translated');
});

/** @param {'romanized' | 'translated'} what */
export function toggleLyricsShow(what) {
	lyricsShow[what] = !lyricsShow[what];
	try {
		localStorage.setItem(SHOW_KEYS[what], lyricsShow[what] ? '1' : '0');
	} catch {
		// Private storage: it still applies for this session.
	}
	// `storage` only reaches the other windows: this one's LyricsView hears it from here.
	window.dispatchEvent(new StorageEvent('storage', { key: SHOW_KEYS[what] }));
}
