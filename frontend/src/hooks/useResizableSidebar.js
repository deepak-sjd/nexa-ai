import { useEffect, useState } from "react";

const STORAGE_KEY = "nexa-sidebar-width";

export const SIDEBAR_DEFAULT_WIDTH = 280;
export const SIDEBAR_MIN_WIDTH = 220;
export const SIDEBAR_MAX_WIDTH = 480;

function clamp(value) {
  return Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, value));
}

function readStoredWidth() {
  try {
    const stored = Number(window.localStorage.getItem(STORAGE_KEY));

    return Number.isFinite(stored) && stored > 0
      ? clamp(stored)
      : SIDEBAR_DEFAULT_WIDTH;
  } catch {
    return SIDEBAR_DEFAULT_WIDTH;
  }
}

/**
 * Drag-to-resize sidebar. Uses pointer capture on the handle, so the
 * drag keeps working even when the cursor leaves it (no window listeners).
 *
 * Returns { width, dragging, handleProps } — spread handleProps on the
 * resize handle element.
 */
export function useResizableSidebar() {
  const [width, setWidth] = useState(readStoredWidth);
  const [drag, setDrag] = useState(null); // { startX, startWidth } | null

  const dragging = drag !== null;

  // Persist once the drag is finished (not on every pixel).
  useEffect(() => {
    if (dragging) {
      return;
    }

    try {
      window.localStorage.setItem(STORAGE_KEY, String(width));
    } catch {
      // Storage disabled — width just won't persist.
    }
  }, [width, dragging]);

  // Keep the cursor + text selection sane while dragging.
  useEffect(() => {
    if (!dragging) {
      return;
    }

    document.body.classList.add("is-resizing-sidebar");

    return () => {
      document.body.classList.remove("is-resizing-sidebar");
    };
  }, [dragging]);

  const handleProps = {
    role: "separator",
    "aria-orientation": "vertical",
    "aria-label": "Resize sidebar",
    "aria-valuemin": SIDEBAR_MIN_WIDTH,
    "aria-valuemax": SIDEBAR_MAX_WIDTH,
    "aria-valuenow": width,
    tabIndex: 0,

    onPointerDown: (event) => {
      if (event.button !== 0) {
        return;
      }

      event.currentTarget.setPointerCapture(event.pointerId);

      setDrag({ startX: event.clientX, startWidth: width });
    },

    onPointerMove: (event) => {
      if (!drag) {
        return;
      }

      setWidth(clamp(drag.startWidth + event.clientX - drag.startX));
    },

    onPointerUp: () => setDrag(null),
    onPointerCancel: () => setDrag(null),
    onLostPointerCapture: () => setDrag(null),

    onDoubleClick: () => setWidth(SIDEBAR_DEFAULT_WIDTH),

    onKeyDown: (event) => {
      const step = event.shiftKey ? 48 : 16;

      if (event.key === "ArrowLeft") {
        event.preventDefault();
        setWidth((current) => clamp(current - step));
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        setWidth((current) => clamp(current + step));
      } else if (event.key === "Home") {
        event.preventDefault();
        setWidth(SIDEBAR_MIN_WIDTH);
      } else if (event.key === "End") {
        event.preventDefault();
        setWidth(SIDEBAR_MAX_WIDTH);
      }
    },
  };

  return { width, dragging, handleProps };
}