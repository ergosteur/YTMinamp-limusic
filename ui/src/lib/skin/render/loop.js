/** @param {(nowMs: number) => void} draw @returns {() => void} stop */
export function startRenderLoop(draw) {
  let handle = requestAnimationFrame(frame);
  function frame(nowMs) {
    draw(nowMs);
    handle = requestAnimationFrame(frame);
  }
  return () => cancelAnimationFrame(handle);
}
