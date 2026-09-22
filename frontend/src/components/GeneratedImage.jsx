import { useState } from "react";

import ImageLightbox from "./ImageLightbox";
import { DownloadIcon, ExpandIcon, RefreshIcon } from "./ImageIcons";
import { downloadImage, imageAltText } from "../utils/imageMessage";

/**
 * A finished, generated image with its actions.
 *
 * Props
 *   src           image URL or data URI
 *   prompt        the prompt that produced it (alt text, filename, regenerate)
 *   caption       optional text the model returned with the image
 *   onRegenerate  optional; called with the prompt
 *   regenerateDisabled  disable Regenerate (e.g. another request is running)
 *   onLoad        called once the image has loaded (used to re-scroll chat)
 */
export default function GeneratedImage({
  src,
  prompt,
  caption,
  onRegenerate,
  regenerateDisabled = false,
  onLoad,
}) {
  // "loading" | "loaded" | "error"
  const [status, setStatus] = useState("loading");
  // Bumping this remounts <img> so "Try again" re-requests the file.
  const [attempt, setAttempt] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  // "idle" | "saving" | "failed"
  const [downloadState, setDownloadState] = useState("idle");

  async function handleDownload() {
    if (downloadState === "saving") {
      return;
    }

    setDownloadState("saving");

    try {
      await downloadImage(src, prompt);
      setDownloadState("idle");
    } catch (error) {
      console.error("Image download failed:", error);
      setDownloadState("failed");
    }
  }

  const alt = imageAltText(prompt);
  const canInteract = status === "loaded";

  return (
    <figure className="generated-image">
      <button
        type="button"
        className={`generated-image-frame ${
          status === "loaded" ? "is-loaded" : ""
        } ${status === "error" ? "is-error" : ""}`}
        onClick={() => setLightboxOpen(true)}
        disabled={!canInteract}
        aria-label={canInteract ? "View image full size" : undefined}
      >
        {status === "loading" && (
          <span className="generated-image-skeleton" aria-hidden="true" />
        )}

        {status === "error" ? (
          <span className="generated-image-broken" role="alert">
            Couldn't load this image.
          </span>
        ) : (
          <img
            key={attempt}
            src={src}
            alt={alt}
            loading="lazy"
            decoding="async"
            draggable={false}
            onLoad={() => {
              setStatus("loaded");
              onLoad?.();
            }}
            onError={() => setStatus("error")}
          />
        )}
      </button>

      {caption ? (
        <figcaption className="generated-image-caption">{caption}</figcaption>
      ) : null}

      <div className="generated-image-actions">
        {status === "error" ? (
          <button
            type="button"
            className="image-action-button"
            onClick={() => {
              setStatus("loading");
              setAttempt((value) => value + 1);
            }}
          >
            <RefreshIcon />
            Try again
          </button>
        ) : (
          <>
            <button
              type="button"
              className="image-action-button"
              onClick={handleDownload}
              disabled={!canInteract || downloadState === "saving"}
            >
              <DownloadIcon />
              {downloadState === "saving"
                ? "Saving..."
                : downloadState === "failed"
                ? "Failed — retry"
                : "Download"}
            </button>

            <button
              type="button"
              className="image-action-button"
              onClick={() => setLightboxOpen(true)}
              disabled={!canInteract}
            >
              <ExpandIcon />
              View
            </button>

            {onRegenerate && prompt ? (
              <button
                type="button"
                className="image-action-button"
                onClick={() => onRegenerate(prompt)}
                disabled={regenerateDisabled}
                title="Generate another image from the same prompt"
              >
                <RefreshIcon />
                Regenerate
              </button>
            ) : null}
          </>
        )}
      </div>

      {lightboxOpen && (
        <ImageLightbox
          src={src}
          alt={alt}
          onClose={() => setLightboxOpen(false)}
          onDownload={handleDownload}
          downloading={downloadState === "saving"}
        />
      )}
    </figure>
  );
}
