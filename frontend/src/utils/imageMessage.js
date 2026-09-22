// ============================================================
// IMAGE MESSAGE HELPERS
// ============================================================

import { resolveApiUrl } from "../services/api";

// ------------------------------------------------------------
// Slash command: "/image a red fox" or "/imagine a red fox"
// Returns null if the text isn't the command, otherwise
// { prompt } (prompt may be "" for a bare "/image").
// ------------------------------------------------------------

const IMAGE_COMMAND = /^\/(?:image|imagine)(?:\s+([\s\S]*))?$/i;

export function parseImageCommand(text) {
  const match = IMAGE_COMMAND.exec(text.trim());

  if (!match) {
    return null;
  }

  return { prompt: (match[1] || "").trim() };
}

// ------------------------------------------------------------
// Legacy format: the first backend version stored images as
//   "<caption>\n\n![Generated image](data:image/png;base64,....)"
// directly in message.content. react-markdown strips data: URLs,
// so these must be pulled out and rendered by <GeneratedImage>.
// Uses indexOf rather than a regex — the payload is megabytes.
// ------------------------------------------------------------

export function extractLegacyImage(content) {
  if (typeof content !== "string") {
    return null;
  }

  const marker = "](data:image/";
  const markerIndex = content.indexOf(marker);

  if (markerIndex === -1) {
    return null;
  }

  const altStart = content.lastIndexOf("![", markerIndex);

  if (altStart === -1) {
    return null;
  }

  const srcStart = markerIndex + 2;
  const srcEnd = content.indexOf(")", srcStart);

  if (srcEnd === -1) {
    return null;
  }

  const src = content.slice(srcStart, srcEnd).replace(/\s+/g, "");

  if (!/^data:image\/[a-z0-9.+-]+;base64,/i.test(src.slice(0, 80))) {
    return null;
  }

  const caption = (
    content.slice(0, altStart) + content.slice(srcEnd + 1)
  ).trim();

  return { src, caption };
}

// ------------------------------------------------------------
// API message -> UI message
//   { id, role, content, sources, image?: { src, prompt } }
// ------------------------------------------------------------

export function normalizeApiMessage(message) {
  const base = {
    id: message.id,
    role: message.role,
    content: message.content || "",
    sources: message.sources || null,
  };

  if (message.role !== "assistant") {
    return base;
  }

  if (message.image_url) {
    return {
      ...base,
      image: { src: resolveApiUrl(message.image_url) },
    };
  }

  const legacy = extractLegacyImage(base.content);

  if (legacy) {
    return {
      ...base,
      content: legacy.caption,
      image: { src: legacy.src },
    };
  }

  return base;
}

/**
 * Normalize a whole history and attach each image's prompt
 * (the user message right before it) — used for alt text,
 * download filenames and "Regenerate".
 */
export function normalizeHistory(apiMessages) {
  const messages = apiMessages.map(normalizeApiMessage);

  let lastUserPrompt = "";

  return messages.map((message) => {
    if (message.role === "user") {
      lastUserPrompt = message.content;
      return message;
    }

    if (message.image) {
      return {
        ...message,
        image: { ...message.image, prompt: lastUserPrompt },
      };
    }

    return message;
  });
}

// ------------------------------------------------------------
// Accessibility + downloads
// ------------------------------------------------------------

export function imageAltText(prompt) {
  const text = (prompt || "").trim().replace(/\s+/g, " ");

  if (!text) {
    return "AI-generated image";
  }

  return text.length > 125
    ? `AI-generated image: ${text.slice(0, 122)}...`
    : `AI-generated image: ${text}`;
}

const EXTENSIONS = {
  "image/png": "png",
  "image/jpeg": "jpg",
  "image/webp": "webp",
  "image/gif": "gif",
};

function buildFilename(prompt, mimeType) {
  const slug = (prompt || "image")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);

  const extension = EXTENSIONS[mimeType] || "png";

  return `nexa-${slug || "image"}-${Date.now()}.${extension}`;
}

/**
 * Save an image to disk. Fetches to a blob first because the
 * `download` attribute is ignored for cross-origin URLs (the API
 * lives on a different origin than the page). Works for data:
 * URLs too. Throws on failure so the caller can show feedback.
 */
export async function downloadImage(src, prompt) {
  const response = await fetch(src);

  if (!response.ok) {
    throw new Error(`Download failed (${response.status})`);
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = buildFilename(prompt, blob.type);

  document.body.appendChild(link);
  link.click();
  link.remove();

  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
