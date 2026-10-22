// The analyzer's stand-in where there's no real spectrum: audio is only captured on Linux so far
// (src-tauri/src/viz.rs), so elsewhere, or when capture fails, the analyzer plays test patterns
// while music plays rather than sitting empty. A new one every few seconds: sweeps at different
// speeds, a travelling wave, random bars, a rising staircase, a beat-ish pulse.
import { playback } from '$lib/player.svelte';
import { uiState } from './uiState.js';

const COLUMNS = 75;
/** Values in the analyzer's units, the same as viz.rs's (15 fills the box). */
const TOP = 16;
const PATTERN_MS = 6000;
/** Real columns older than this mean there's no live feed. */
const STALE_MS = 500;

const out = new Float32Array(COLUMNS);
const noise = new Float32Array(COLUMNS);
let noiseAt = 0;

/** A bump `width` columns wide centred on `at`. @param {number} at @param {number} width */
function bump(at, width) {
	for (let x = 0; x < COLUMNS; x++) out[x] = Math.max(out[x], TOP * Math.exp(-(((x - at) / width) ** 2)));
}

/** Each pattern fills `out` for time `t` (seconds into it). @type {((t: number) => void)[]} */
const PATTERNS = [
	// Slow sweep, left to right.
	(t) => bump(((t / 2) % 1) * (COLUMNS + 20) - 10, 6),
	// Fast ping-pong.
	(t) => {
		const p = (t / 0.7) % 2;
		bump((p < 1 ? p : 2 - p) * COLUMNS, 4);
	},
	// Travelling wave.
	(t) => {
		for (let x = 0; x < COLUMNS; x++) out[x] = TOP * (0.5 + 0.45 * Math.sin(x * 0.18 - t * 5));
	},
	// Random bars, a new set ten times a second, louder at the low end like music.
	(t) => {
		if (t * 1000 - noiseAt > 100 || t * 1000 < noiseAt) {
			noiseAt = t * 1000;
			for (let x = 0; x < COLUMNS; x++) noise[x] = Math.random() * TOP * (1 - (x / COLUMNS) * 0.6);
		}
		out.set(noise);
	},
	// Staircase filling up from the left, then emptying.
	(t) => {
		const p = (t / 1.5) % 2;
		const level = (p < 1 ? p : 2 - p) * COLUMNS;
		for (let x = 0; x < COLUMNS; x++) out[x] = x < level ? TOP * (0.3 + (0.7 * x) / COLUMNS) : 0;
	},
	// Two sweeps crossing at different speeds.
	(t) => {
		bump(((t / 1.2) % 1) * COLUMNS, 3);
		bump((1 - ((t / 3) % 1)) * COLUMNS, 5);
	},
	// A pulse on every half-second "beat", dying away.
	(t) => {
		const beat = Math.exp(-((t % 0.5) * 8));
		for (let x = 0; x < COLUMNS; x++) out[x] = TOP * beat * (1 - (x / COLUMNS) * 0.7) * (0.75 + 0.25 * Math.sin(x * 1.3));
	}
];

/**
 * The columns the analyzer should draw now: the live feed's, a test pattern while music plays
 * without one, or null (silence).
 * @param {number} nowMs a `performance.now()` time
 * @returns {ArrayLike<number> | null}
 */
export function analyzerColumns(nowMs) {
	if (uiState.vizColumns && nowMs - uiState.vizAt < STALE_MS) return uiState.vizColumns;
	if (!playback.now || playback.paused) return null;
	const n = Math.floor(nowMs / PATTERN_MS);
	out.fill(0);
	PATTERNS[n % PATTERNS.length]((nowMs % PATTERN_MS) / 1000);
	return out;
}
