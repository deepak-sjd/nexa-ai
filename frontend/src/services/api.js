// ============================================================
// API CLIENT
// ------------------------------------------------------------
// Single place for the backend base URL and for the calls the
// image feature makes. Other calls in App.jsx can migrate here
// gradually — nothing else needs to change for that.
//
// Configure per environment with a Vite env var:
//   VITE_API_BASE_URL=https://api.example.com/api/v1
// Falls back to the local dev backend.
// ============================================================

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/api/v1";

export const API_BASE_URL = (
  import.meta.env?.VITE_API_BASE_URL || DEFAULT_API_BASE_URL
).replace(/\/+$/, "");

// Image generation is slow (typically 5–30s). Give up after this
// long instead of leaving the user staring at a spinner forever.
export const IMAGE_TIMEOUT_MS = 90_000;

export class ApiError extends Error {
  /**
   * @param {string} message  Safe, user-facing message.
   * @param {{status?: number, kind?: "http"|"network"|"timeout"}} [meta]
   */
  constructor(message, { status = 0, kind = "http" } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.kind = kind;
  }
}

/**
 * Turn a path returned by the backend into something an <img>
 * can load. Absolute URLs and data/blob URLs pass through;
 * root-relative paths ("/api/v1/images/files/x.png") are resolved
 * against the API's origin, not the page's (they differ in dev:
 * :5173 vs :8000).
 */
export function resolveApiUrl(path) {
  if (!path) {
    return "";
  }

  if (/^(https?:|data:|blob:)/i.test(path)) {
    return path;
  }

  const apiOrigin = new URL(API_BASE_URL, window.location.href).origin;

  return new URL(path, `${apiOrigin}/`).toString();
}

async function readErrorMessage(response) {
  let detail = null;

  try {
    const body = await response.json();
    detail = body?.detail ?? null;
  } catch {
    // Body wasn't JSON — fall through to the generic messages.
  }

  // FastAPI HTTPException: detail is a string (already user-facing
  // for the image endpoint).
  if (typeof detail === "string" && detail.trim()) {
    return detail.trim();
  }

  // FastAPI validation error: detail is a list of objects.
  if (Array.isArray(detail)) {
    // Pydantic v2 error type for a prompt over the server's max length.
    if (detail.some((item) => item?.type === "string_too_long")) {
      return "That prompt is too long. Please shorten it and try again.";
    }

    return "That request wasn't valid. Please check your prompt and try again.";
  }

  if (response.status === 429) {
    return "Too many requests right now. Please wait a minute and try again.";
  }

  if (response.status >= 500) {
    return "Image generation is temporarily unavailable. Please try again.";
  }

  return "Could not generate that image. Please try again.";
}

/**
 * Generate an image from a text prompt.
 *
 * Resolves to:
 *   { src, text, messageId, conversation }
 * where `src` is directly usable as an <img src>.
 *
 * Works with both backend response shapes:
 *   - new:    { image_url, ... }            (image stored server-side)
 *   - legacy: { image_base64, mime_type }   (image inline)
 *
 * Rejects with:
 *   - a DOMException named "AbortError" if the caller aborted
 *   - an ApiError for everything else (timeout, network, HTTP)
 */
export async function generateImage({
  prompt,
  conversationId,
  signal,
  timeoutMs = IMAGE_TIMEOUT_MS,
}) {
  const controller = new AbortController();

  let timedOut = false;

  const forwardAbort = () => controller.abort();

  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener("abort", forwardAbort, { once: true });
    }
  }

  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    const response = await fetch(`${API_BASE_URL}/images/generate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        prompt,
        conversation_id: conversationId ?? null,
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new ApiError(await readErrorMessage(response), {
        status: response.status,
      });
    }

    const data = await response.json();

    let src = "";

    if (data.image_url) {
      src = resolveApiUrl(data.image_url);
    } else if (data.image_base64) {
      src = `data:${data.mime_type || "image/png"};base64,${data.image_base64}`;
    }

    if (!src) {
      throw new ApiError("The server didn't return an image. Please try again.");
    }

    return {
      src,
      text: data.text || "",
      messageId: data.message_id ?? null,
      conversation: data.conversation ?? null,
    };
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (error?.name === "AbortError") {
      if (timedOut) {
        throw new ApiError(
          "Image generation took too long. Please try again.",
          { kind: "timeout" }
        );
      }

      // The user cancelled — let the caller handle it.
      throw error;
    }

    throw new ApiError(
      "Can't reach the server. Check your connection and try again.",
      { kind: "network" }
    );
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", forwardAbort);
  }
}
