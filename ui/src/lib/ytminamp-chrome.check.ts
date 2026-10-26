// ytminamp: self-check that Limusic's titlebar, sidebar and account button are still laid out the
// way the Media Library's CSS expects (LibraryPages.svelte). That CSS hides some of their pieces by
// position (the wordmark, the theme switch, Settings, theater, the mini player, Winamp mode), so an
// upstream reshuffle would quietly hide the wrong thing. This reads the components' source, checks
// the order, and fails with what moved. Run with the others (`pnpm test`), after every upstream
// merge:
//
//     node --experimental-strip-types ui/src/lib/ytminamp-chrome.check.ts
//
// Prints "ok" and exits 0, or throws on the first thing out of place. A failure means: look at
// the component, fix the selectors in LibraryPages.svelte, then the expectations here.
// @ts-expect-error: ui/ has no Node types (svelte-check); Node runs this file.
import { readFileSync } from 'node:fs';

const source = (name: string): string[] =>
	(readFileSync(new URL(`./components/${name}`, import.meta.url), 'utf8') as string).split('\n');

function ok(cond: boolean, what: string): void {
	if (!cond) throw new Error(`FAIL: ${what}`);
}

const tabs = (line: string) => line.match(/^\t*/)![0].length;

/** The element lines (`<tag`) and blocks (`{#if`) directly inside the element opened at `open`. */
function children(lines: string[], open: number): { at: number; line: string }[] {
	const depth = tabs(lines[open]) + 1;
	const out: { at: number; line: string }[] = [];
	// An opening tag spread over several lines ends at a `>` line of its own indent.
	let start = open;
	if (!/>\s*$/.test(lines[open])) {
		while (start < lines.length - 1 && !(tabs(lines[start + 1]) === depth - 1 && /^\t*\/?>/.test(lines[start + 1]))) start++;
		start++;
	}
	for (let i = start + 1; i < lines.length; i++) {
		const line = lines[i];
		if (line.trim() === '') continue;
		if (tabs(line) < depth) break;
		if (tabs(line) === depth && /^\t*(<[A-Za-z]|\{[#:])/.test(line)) out.push({ at: i, line: line.trim() });
	}
	return out;
}

/** The label an opening tag carries (its aria-label, else its title): a t() key or plain text. */
function label(lines: string[], at: number): string {
	for (let i = at; i < lines.length && i < at + 12; i++) {
		const m = lines[i].match(/(?:aria-label|title)=(?:\{t\('([^']+)'\)\}|\{(\w+)\}|"([^"]+)")/);
		if (m) return m[1] ?? m[2] ?? m[3];
		if (i > at && /^\t*\/?>/.test(lines[i])) break;
	}
	return '?';
}

const find = (lines: string[], pattern: RegExp, what: string) => {
	const i = lines.findIndex((l) => pattern.test(l));
	ok(i >= 0, `${what} not found`);
	return i;
};

// Titlebar.svelte: `header > span:first-child` is the app's name, `header > div:first-of-type >
// img` the icon, and the right group (`header > div:last-child`) is these buttons, in this order.
// The last three (`button:nth-last-of-type(-n + 3)`) are hidden.
{
	const lines = source('Titlebar.svelte');
	const header = find(lines, /^<header\b/, 'Titlebar <header>');
	const top = children(lines, header);
	ok(top[0]?.line.startsWith('<span'), `the titlebar's first child is ${top[0]?.line}, not the name <span>`);
	ok(
		lines.slice(top[0].at, top[0].at + 5).some((l) => l.includes('{APP_NAME}')),
		"the titlebar's first <span> no longer holds {APP_NAME}"
	);
	const firstDiv = top.find((c) => c.line.startsWith('<div'));
	ok(!!firstDiv, 'the titlebar has no <div>');
	ok(
		children(lines, firstDiv!.at).some((c) => c.line.startsWith('<img')),
		"the titlebar's first <div> no longer holds the icon <img>"
	);

	const right = top.filter((c) => c.line.startsWith('<div')).at(-1)!;
	const inRight = children(lines, right.at);
	// A button inside an {#if} block is a sibling too, and would move the count.
	for (const block of inRight.filter((c) => c.line.startsWith('{'))) {
		ok(
			!children(lines, block.at).some((c) => /^<(button|AccountMenu)\b/.test(c.line)),
			`a button in a block (${block.line}) in the titlebar's right group`
		);
	}
	const buttons = inRight
		.filter((c) => /^<(button|AccountMenu)\b/.test(c.line))
		.map((c) => (c.line.startsWith('<AccountMenu') ? 'AccountMenu' : label(lines, c.at)));
	const expected = [
		'AccountMenu',
		'dialogs.link.title',
		'nav.listen_together',
		'settings.general.discord_rpc',
		'scrobblerTitle',
		'player.theater_mode',
		'a11y.toggle_mini',
		'Winamp skin mode'
	];
	ok(
		JSON.stringify(buttons) === JSON.stringify(expected),
		`the titlebar's right group is now [${buttons.join(', ')}], expected [${expected.join(', ')}]`
	);
}

// AccountMenu.svelte: its button (the right group's first) holds the name as a <span> and ends with
// the arrow icon (`button:first-of-type > span`, `> svg:last-child`).
{
	const lines = source('AccountMenu.svelte');
	const button = find(lines, /^<button\b/, "AccountMenu's top-level <button>");
	const inside = children(lines, button);
	ok(inside.some((c) => c.line.startsWith('<span')), "the account button has no name <span>");
	ok(
		/^<HugeiconsIcon\b/.test(inside.at(-1)?.line ?? '') &&
			lines.slice(inside.at(-1)!.at, inside.at(-1)!.at + 3).some((l) => l.includes('ArrowDown01Icon')),
		"the account button no longer ends with its arrow icon"
	);
}

// Sidebar.svelte: `aside > div:first-child` starts with the wordmark <span> and has a <div> whose
// last button is the theme switch; `aside > nav > button` is Settings alone (the pages are <a>).
{
	const lines = source('Sidebar.svelte');
	const aside = find(lines, /^<aside\b/, 'Sidebar <aside>');
	const top = children(lines, aside);
	ok(top[0]?.line.startsWith('<div'), `the sidebar's first child is ${top[0]?.line}, not a <div>`);
	const row = children(lines, top[0].at);
	ok(/^<span\b.*>Limusic</.test(row[0]?.line ?? ''), `the sidebar's first row starts with ${row[0]?.line}, not the wordmark`);
	const switches = row.find((c) => c.line.startsWith('<div'));
	ok(!!switches, "the sidebar's first row has no <div> of buttons");
	const last = children(lines, switches!.at).at(-1)!;
	ok(
		/^<Button\b/.test(last.line) && label(lines, last.at) === 'a11y.toggle_theme',
		"the theme switch is no longer the last button in the sidebar's first row"
	);
	const nav = top.find((c) => c.line.startsWith('<nav'));
	ok(!!nav, 'the sidebar has no <nav>');
	const navButtons = children(lines, nav!.at).filter((c) => /^<(button|Button)\b/.test(c.line));
	ok(
		navButtons.length === 1 && label(lines, navButtons[0].at) === 'nav.settings',
		`the sidebar's <nav> buttons are [${navButtons.map((c) => label(lines, c.at)).join(', ')}], expected Settings alone`
	);
}

console.log('ok');
