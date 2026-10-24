import { MARQUEE_STEP_MS } from './sprites.js';

/** After any input (or focus, resize), every frame is drawn for this long: presses, drags and
 * hovers answer at once. */
const ACTIVE_MS = 500;
const INPUT_EVENTS = ['mousedown', 'mouseup', 'mousemove', 'wheel', 'keydown', 'keyup', 'focus', 'blur', 'resize'];
/** Shared by this window's loops: input anywhere in it wakes them all. */
let activeUntil = 0;

/** Draw every frame for a moment: for changes that come from outside the page, like a pick in
 * the GTK menu (menu.js), which no page event announces. */
export function wake() {
  activeUntil = performance.now() + ACTIVE_MS;
}

/**
 * Draws on animation frames, but only when it can matter: every frame while `busy()` says
 * something is moving (the analyzer) or just after input; otherwise once per marquee step, which
 * is the fastest anything else on a Winamp window changes (the title scrolls, clocks tick, the
 * backend's state lands). A window at rest costs a few draws a second instead of sixty.
 * @param {(nowMs: number) => void} draw
 * @param {(nowMs: number) => boolean} [busy]
 * @returns {() => void} stop
 */
export function startRenderLoop(draw, busy = () => false) {
  let lastStep = -1;
  for (const type of INPUT_EVENTS) window.addEventListener(type, wake, { capture: true, passive: true });

  let handle = requestAnimationFrame(frame);
  function frame(nowMs) {
    handle = requestAnimationFrame(frame);
    const step = Math.floor(nowMs / MARQUEE_STEP_MS);
    if (step === lastStep && nowMs > activeUntil && !busy(nowMs)) return;
    lastStep = step;
    draw(nowMs);
  }
  return () => {
    cancelAnimationFrame(handle);
    for (const type of INPUT_EVENTS) window.removeEventListener(type, wake, { capture: true });
  };
}
