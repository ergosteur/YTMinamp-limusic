// The playing track's lyrics for the Winamp lyrics panel: fetched once per track, the same
// request Limusic's own lyrics view makes (LyricsView.svelte), and where in them the song is.
import * as api from '$lib/api';
import { playback } from '$lib/player.svelte';
import { uiState } from './uiState.js';

/** @typedef {{ status: 'none' | 'loading' | 'missing' | 'instrumental' | 'ready', lyrics: api.Lyrics | null }} LyricsState */

// Limusic's own romanization and translation switches (LyricsView.svelte): the same localStorage
// keys and defaults, so a switch flipped in either place applies in both, and the `storage` event
// carries it between windows.
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

/** What the lyrics panel shows under each line. */
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
}

let requested = '';
/** @type {LyricsState} */
let current = { status: 'none', lyrics: null };

/** "3:45" → 225. @param {string | undefined} d */
function seconds(d) {
	if (!d) return undefined;
	const parts = d.split(':').map(Number);
	return parts.some(Number.isNaN) ? undefined : parts.reduce((a, b) => a * 60 + b, 0);
}

/** The lyrics for what's playing, starting the fetch when the track changes. */
export function lyricsNow() {
	const now = playback.now;
	if (!now) {
		requested = '';
		current = { status: 'none', lyrics: null };
		return current;
	}
	if (now.videoId !== requested) {
		const id = (requested = now.videoId);
		current = { status: 'loading', lyrics: null };
		uiState.lyrics.nudge = 0;
		api
			.getLyrics({
				videoId: id,
				title: now.title,
				artists: now.artists,
				album: now.album ?? undefined,
				// The track's own length: playback.duration can still be the last track's.
				duration: seconds(now.duration)
			})
			.then((l) => {
				if (requested !== id) return;
				current = !l
					? { status: 'missing', lyrics: null }
					: { status: l.instrumental ? 'instrumental' : 'ready', lyrics: l };
			})
			.catch(() => {
				if (requested === id) current = { status: 'missing', lyrics: null };
			});
	}
	return current;
}

/** Where the song is now, in ms, between the position ticks (they land at about 4 Hz). */
function positionMs() {
	const drift = playback.paused ? 0 : (performance.now() - playback.positionAt) / 1000;
	return (playback.position + drift) * 1000;
}

/** The last timed line whose cue has passed, or -1 (untimed lyrics, or before the first). */
export function sungLine(/** @type {api.Lyrics} */ lyrics) {
	if (!lyrics.synced) return -1;
	const ms = positionMs() - (lyrics.offset_ms ?? 0);
	let line = -1;
	for (let i = 0; i < lyrics.lines.length; i++) {
		const t = lyrics.lines[i].time_ms;
		if (t === undefined) continue;
		if (t > ms) break;
		line = i;
	}
	return line;
}
