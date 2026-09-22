import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

import { DownloadIcon, XIcon } from "./ImageIcons";

/**
 * Fullscreen image viewer.
 *
 * - Rendered in a portal so no ancestor (transform / backdrop-filter)
 *   can break `position: fixed`.
 * - Esc or a click on the backdrop closes it.
 * - Focus moves into the dialog, is kept inside while it's open, and
 *   returns to whatever opened it on close.
 * - Page scroll is locked while open.
 */
export default function ImageLightbox({
  src,
  alt,
  onClose,
  onDownload,
  downloading = false,
}) {
  const dialogRef = useRef(null);
  const closeButtonRef = useRef(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const previouslyFocused = document.activeElement;
    const previousOverflow = document.body.style.overflow;

    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onCloseRef.current();
        return;
      }

      if (event.key !== "Tab") {
        return;
      }

      const focusable = dialogRef.current?.querySelectorAll(
        "button:not([disabled])"
      );

      if (!focusable || focusable.length === 0) {
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;

      if (previouslyFocused instanceof HTMLElement) {
        previouslyFocused.focus();
      }
    };
  }, []);

  return createPortal(
    <div
      className="image-lightbox"
      role="dialog"
      aria-modal="true"
      aria-label="Image viewer"
      ref={dialogRef}
      onClick={onClose}
    >
      <div className="image-lightbox-toolbar">
        <button
          type="button"
          className="image-lightbox-button"
          onClick={(event) => {
            event.stopPropagation();
            onDownload();
          }}
          disabled={downloading}
        >
          <DownloadIcon />
          {downloading ? "Saving..." : "Download"}
        </button>

        <button
          type="button"
          className="image-lightbox-button icon-only"
          onClick={(event) => {
            event.stopPropagation();
            onClose();
          }}
          aria-label="Close image viewer"
          ref={closeButtonRef}
        >
          <XIcon />
        </button>
      </div>

      <img
        className="image-lightbox-image"
        src={src}
        alt={alt}
        onClick={(event) => event.stopPropagation()}
      />
    </div>,
    document.body
  );
}
