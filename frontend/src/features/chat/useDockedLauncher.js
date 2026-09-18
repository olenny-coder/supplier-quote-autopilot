import { useCallback, useRef, useState } from "react";

// Movement (in px) below which a press is treated as a click rather than a drag.
const CLICK_THRESHOLD = 4;

// Gap kept between the launcher and the viewport edges (matches the panel's
// bottom-6 / x-6 anchor so the two line up).
const MARGIN = 24;

/**
 * Docking launcher for the chat button.
 *
 * The button can be dragged anywhere, but on release it snaps to the nearest
 * vertical edge — so it only ever lives on the LEFT or RIGHT side — while
 * keeping its vertical position. A press that doesn't move past CLICK_THRESHOLD
 * is reported through `onClick` instead of dragging.
 *
 * Returns the docked `side` ('left' | 'right') so the panel can slide in from
 * the matching edge. Position is in-memory only and resets on refresh.
 */
export function useDockedLauncher({ onClick } = {}) {
  const [side, setSide] = useState("right");
  const [y, setY] = useState(null); // docked top px; null => default bottom anchor
  const [drag, setDrag] = useState(null); // live coords while dragging
  const [dragging, setDragging] = useState(false);

  const start = useRef(null);
  const live = useRef(null);
  const moved = useRef(false);

  const onPointerDown = useCallback((e) => {
    if (e.button !== undefined && e.button !== 0) return; // primary / touch only

    const rect = e.currentTarget.getBoundingClientRect();
    start.current = {
      px: e.clientX,
      py: e.clientY,
      ex: rect.left,
      ey: rect.top,
      w: rect.width,
      h: rect.height,
    };
    live.current = { x: rect.left, y: rect.top };
    moved.current = false;
    setDragging(true);
    setDrag(live.current);
    e.currentTarget.setPointerCapture?.(e.pointerId);
  }, []);

  const onPointerMove = useCallback((e) => {
    const s = start.current;
    if (!s) return;

    const dx = e.clientX - s.px;
    const dy = e.clientY - s.py;
    if (Math.hypot(dx, dy) > CLICK_THRESHOLD) moved.current = true;

    const maxX = window.innerWidth - s.w - MARGIN;
    const maxY = window.innerHeight - s.h - MARGIN;
    const x = Math.min(Math.max(MARGIN, s.ex + dx), maxX);
    const yy = Math.min(Math.max(MARGIN, s.ey + dy), maxY);

    live.current = { x, y: yy };
    setDrag(live.current);
  }, []);

  const onPointerUp = useCallback(
    (e) => {
      const s = start.current;
      if (!s) return;

      const d = live.current;
      const wasClick = !moved.current;

      start.current = null;
      live.current = null;
      setDragging(false);
      setDrag(null);
      e.currentTarget.releasePointerCapture?.(e.pointerId);

      if (wasClick) {
        onClick?.();
        return;
      }

      // Snap to whichever side the launcher's center ended up closest to,
      // keeping the vertical position it was dropped at.
      if (d) {
        const center = d.x + s.w / 2;
        setSide(center < window.innerWidth / 2 ? "left" : "right");
        setY(d.y);
      }
    },
    [onClick]
  );

  let style;
  if (drag) {
    // Free-floating while dragging.
    style = { left: drag.x, top: drag.y, right: "auto", bottom: "auto" };
  } else {
    const horizontal =
      side === "right"
        ? { right: MARGIN, left: "auto" }
        : { left: MARGIN, right: "auto" };
    const vertical =
      y == null ? { bottom: MARGIN, top: "auto" } : { top: y, bottom: "auto" };
    style = { ...horizontal, ...vertical };
  }

  return {
    side,
    dragging,
    style,
    handlers: { onPointerDown, onPointerMove, onPointerUp },
  };
}
