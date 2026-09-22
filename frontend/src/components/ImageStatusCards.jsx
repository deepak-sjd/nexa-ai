import { useEffect, useState } from "react";

import { AlertIcon, RefreshIcon, SparklesIcon } from "./ImageIcons";

function secondsSince(startedAt) {
  return Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
}

/**
 * Shown while an image request is in flight. Image generation takes
 * a while, so it shows elapsed time and offers Cancel.
 */
export function ImageGeneratingCard({ startedAt, onCancel }) {
  const [seconds, setSeconds] = useState(() => secondsSince(startedAt));

  useEffect(() => {
    const timerId = setInterval(() => {
      setSeconds(secondsSince(startedAt));
    }, 1000);

    return () => clearInterval(timerId);
  }, [startedAt]);

  return (
    <div className="image-pending">
      <div className="image-pending-art" aria-hidden="true">
        <span className="image-pending-shimmer" />
        <span className="image-pending-icon">
          <SparklesIcon />
        </span>
      </div>

      <div className="image-pending-footer">
        <div className="image-pending-text">
          {/* Only this line is announced to screen readers — the
              ticking timer below is aria-hidden to avoid noise. */}
          <span className="image-pending-title" role="status">
            Creating your image...
          </span>

          <span className="image-pending-meta" aria-hidden="true">
            {seconds}s
            {seconds >= 20 ? " · still working, complex images take longer" : ""}
          </span>
        </div>

        <button
          type="button"
          className="image-action-button"
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

/**
 * Shown when generation failed or was cancelled.
 */
export function ImageErrorCard({
  message,
  cancelled = false,
  onRetry,
  retryDisabled = false,
}) {
  return (
    <div
      className={`image-error ${cancelled ? "is-cancelled" : ""}`}
      role={cancelled ? "status" : "alert"}
    >
      <span className="image-error-icon">
        <AlertIcon />
      </span>

      <div className="image-error-body">
        <span className="image-error-title">
          {cancelled ? "Cancelled" : "Couldn't create the image"}
        </span>

        <span className="image-error-message">{message}</span>
      </div>

      {onRetry && (
        <button
          type="button"
          className="image-action-button"
          onClick={onRetry}
          disabled={retryDisabled}
        >
          <RefreshIcon />
          Try again
        </button>
      )}
    </div>
  );
}
