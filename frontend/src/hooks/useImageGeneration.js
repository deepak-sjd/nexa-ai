import { useCallback, useEffect, useRef } from "react";

import { generateImage as requestImage } from "../services/api";

/**
 * Owns the lifecycle of one image request:
 *
 *   user prompt bubble + "pending" assistant placeholder
 *        -> success: placeholder becomes an image message
 *        -> failure: placeholder becomes an error card (with Retry)
 *        -> cancel:  placeholder becomes a "cancelled" card (with Retry)
 *
 * It only talks to the chat through the callbacks it is given, so
 * App.jsx stays in charge of state.
 *
 * Message shapes it writes (all carry a stable `clientId` so React
 * doesn't remount the row when the server id replaces the temp id):
 *   pending: { kind: "image-pending", startedAt, prompt }
 *   error:   { kind: "image-error", error, cancelled?, prompt }
 *   success: { image: { src, prompt }, content: caption }
 */
export function useImageGeneration({
  conversationId,
  setMessages,
  setLoading,
  onConversationUpdate,
}) {
  const abortRef = useRef(null);

  // Never leave a request running after the component goes away.
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const generate = useCallback(
    async (rawPrompt) => {
      const prompt = (rawPrompt || "").trim();

      // One image request at a time.
      if (!prompt || !conversationId || abortRef.current) {
        return false;
      }

      const controller = new AbortController();
      abortRef.current = controller;

      const stamp = Date.now();
      const userClientId = `user-${stamp}`;
      const pendingClientId = `image-${stamp}`;

      setMessages((previous) => [
        ...previous,
        {
          id: userClientId,
          clientId: userClientId,
          role: "user",
          content: prompt,
        },
        {
          id: pendingClientId,
          clientId: pendingClientId,
          role: "assistant",
          content: "",
          kind: "image-pending",
          startedAt: stamp,
          prompt,
        },
      ]);

      setLoading(true);

      const patchPending = (patch) =>
        setMessages((previous) =>
          previous.map((message) =>
            message.clientId === pendingClientId
              ? { ...message, ...patch }
              : message
          )
        );

      try {
        const result = await requestImage({
          prompt,
          conversationId,
          signal: controller.signal,
        });

        patchPending({
          id: result.messageId ?? pendingClientId,
          kind: null,
          startedAt: null,
          content: result.text,
          image: { src: result.src, prompt },
        });

        if (result.conversation) {
          onConversationUpdate?.({ conversation: result.conversation });
        }

        return true;
      } catch (error) {
        const cancelled = error?.name === "AbortError";

        patchPending({
          kind: "image-error",
          startedAt: null,
          cancelled,
          error: cancelled
            ? "Image generation was cancelled."
            : error?.message ||
              "Could not generate that image. Please try again.",
        });

        return false;
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }

        setLoading(false);
      }
    },
    [conversationId, setMessages, setLoading, onConversationUpdate]
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  /**
   * Retry a failed/cancelled request: drop the failed card and the
   * prompt bubble right above it, then run the same prompt again so
   * the transcript doesn't collect duplicates.
   */
  const retry = useCallback(
    (failedClientId, prompt) => {
      setMessages((previous) => {
        const index = previous.findIndex(
          (message) => message.clientId === failedClientId
        );

        if (index === -1) {
          return previous;
        }

        const promptBubble = previous[index - 1];
        const dropPromptBubble =
          promptBubble?.role === "user" && promptBubble.content === prompt;

        return previous.filter(
          (_, position) =>
            position !== index &&
            !(dropPromptBubble && position === index - 1)
        );
      });

      return generate(prompt);
    },
    [generate, setMessages]
  );

  return { generate, cancel, retry };
}
