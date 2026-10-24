<script>
	// The lyrics panel's lyrics: Limusic's own view (LyricsView.svelte: the sweep word by word, a
	// click on a line seeks there, a scrollbar, the source picker, romanization and translation and
	// size in its bar), laid over the frame render/lyrics.js draws, in the skin's playlist colours
	// and font: its theme tokens set here, for this view alone. The Winamp window (docked) and a
	// floating lyrics window both use it.
	import LyricsView from './LyricsView.svelte';
	import { zoomLyrics } from '../skin/skinApi.js';
	import { readable } from '../skin/contrast.js';

	/**
	 * @type {{
	 *   rect: { x: number, y: number, w: number, h: number },
	 *   pledit: import('$lib/api').SkinPayload['pledit'],
	 *   zoom: number,
	 *   onmenu: (at: { x: number, y: number }) => void
	 * }}
	 */
	let { rect, pledit, zoom, onmenu } = $props();

	/** At the panel's text size 1, Limusic's view (sized for its side panel) comes out at about the
	 * playlist editor's 11 px. */
	const BASE = 0.6;
	const scale = $derived(BASE * zoom);

	const bg = $derived(pledit.normalBg ?? '#000000');
	// The playlist's colours, nudged until they read at lyrics' size where a skin's don't (contrast.js).
	const normal = $derived(readable(pledit.normal ?? '#00ff00', [bg], 3));
	const current = $derived(readable(pledit.current ?? '#ffffff', [bg], 3));
	const font = $derived(`${pledit.font ? `"${pledit.font}", ` : ''}Arial, sans-serif`);
	/** Limusic's tokens: the sung line in the current-track colour, the rest in the normal one. */
	const tokens = $derived(
		[
			['--background', bg],
			['--foreground', current],
			['--muted-foreground', normal],
			['--muted', `color-mix(in srgb, ${normal} 15%, ${bg})`],
			['--border', `color-mix(in srgb, ${normal} 40%, ${bg})`],
			['--primary', current],
			['--font-heading', font],
			['--font-sans', font]
		]
			.map(([k, v]) => `${k}: ${v}`)
			.join('; ')
	);

	/** Ctrl+wheel over the lyrics sizes them, as it did on the canvas. @param {WheelEvent} e */
	function onwheel(e) {
		if (!e.ctrlKey && !e.metaKey) return;
		e.preventDefault();
		zoomLyrics(e.deltaY < 0 ? 1 : -1);
	}

	/** @param {MouseEvent} e */
	function oncontextmenu(e) {
		e.preventDefault();
		e.stopPropagation();
		onmenu({ x: e.clientX, y: e.clientY });
	}
</script>

<div
	class="absolute overflow-hidden"
	style:left="{rect.x}px"
	style:top="{rect.y}px"
	style:width="{rect.w}px"
	style:height="{rect.h}px"
	{onwheel}
	{oncontextmenu}
	role="region"
	aria-label="Lyrics"
>
	<!-- Zoomed as a whole, so the bar and its icons scale with the text; sized back up to fill. -->
	<div
		class="flex flex-col bg-background text-foreground"
		style="{tokens}; zoom: {scale}; width: {rect.w / scale}px; height: {rect.h / scale}px; font-family: {font}"
	>
		<LyricsView />
	</div>
</div>
