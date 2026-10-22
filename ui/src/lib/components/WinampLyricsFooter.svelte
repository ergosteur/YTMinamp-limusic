<script>
	// The lyrics panel's footer, laid over the strip render/lyrics.js keeps for it: Limusic's own
	// lyrics source picker (LyricsSourcePicker.svelte, its "Lyrics from ..." button and popover:
	// every provider's answer side by side, pin one, nudge the timing, search a corrected title),
	// in the skin's playlist colours. What it picks shows in the panel at once (lyrics.js
	// `pickedLyrics`). Used by the Winamp window (docked lyrics) and a floating lyrics window.
	import { onMount } from 'svelte';
	import LyricsSourcePicker from './LyricsSourcePicker.svelte';
	import { lyricsNow, lyricsTrack, pickedLyrics } from '../skin/lyrics.js';

	/** @type {{ rect: { x: number, y: number, w: number, h: number }, pledit: import('$lib/api').SkinPayload['pledit'] }} */
	let { rect, pledit } = $props();

	let lyrics = $state(/** @type {import('$lib/api').Lyrics | null} */ (null));
	let track = $state(/** @type {import('$lib/api').LyricsTrack | null} */ (null));
	let open = $state(false);

	// lyrics.js is plain module state the canvas reads per frame; this follows it at a gentler pace.
	onMount(() => {
		const sync = () => {
			const next = lyricsTrack();
			if (next?.videoId !== track?.videoId) track = next;
			const l = lyricsNow().lyrics;
			if (l !== lyrics) lyrics = l;
		};
		sync();
		const timer = setInterval(sync, 300);
		return () => clearInterval(timer);
	});
</script>

{#if track}
	<div
		class="winamp-lyrics-footer absolute flex items-center overflow-visible px-1 text-[11px]"
		style:left="{rect.x}px"
		style:top="{rect.y}px"
		style:width="{rect.w}px"
		style:height="{rect.h}px"
		style:color={pledit.normal ?? '#00ff00'}
		style:font-family={pledit.font ? `"${pledit.font}", Arial, sans-serif` : 'Arial, sans-serif'}
	>
		<LyricsSourcePicker {lyrics} {track} bind:open onchange={(l, videoId) => pickedLyrics(l, videoId)} />
	</div>
{/if}

<style>
	/* The picker's trigger is styled for Limusic's theme; here it takes the skin's colours. */
	.winamp-lyrics-footer :global(button) {
		color: inherit;
		font: inherit;
		height: auto;
		padding: 0 2px;
	}
</style>
