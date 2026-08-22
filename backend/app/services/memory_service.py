from typing import Any


class MemoryService:
    """
    Manages conversation memory.

    Responsibilities:

    - Store conversation messages in memory
    - Build conversation history
    - Limit history size
    - Prepare history for the LLM
    - Keep conversation memory separate from RAG knowledge
    """

    def __init__(
        self,
        max_messages: int = 20,
    ):
        self.max_messages = max(
            1,
            max_messages,
        )

    # ============================================================
    # BUILD HISTORY
    # ============================================================

    def build_history(
        self,
        messages: list[Any],
    ) -> list[dict[str, str]]:
        """
        Convert database message objects into
        a clean LLM conversation history.
        """

        history = []

        for message in messages:

            role = getattr(
                message,
                "role",
                None,
            )

            content = getattr(
                message,
                "content",
                "",
            )

            if not role:
                continue

            if not content:
                continue

            role = str(role).strip()
            content = str(content).strip()

            if role not in {
                "user",
                "assistant",
                "system",
            }:
                continue

            history.append(
                {
                    "role": role,
                    "content": content,
                }
            )

        # Keep only recent messages
        return history[
            -self.max_messages:
        ]

    # ============================================================
    # ADD MESSAGE
    # ============================================================

    def add_message(
        self,
        history: list[dict[str, str]],
        role: str,
        content: str,
    ) -> list[dict[str, str]]:
        """
        Add a message to an in-memory history.
        """

        if not content or not content.strip():
            return history

        if role not in {
            "user",
            "assistant",
            "system",
        }:
            raise ValueError(
                f"Unsupported message role: {role}"
            )

        history.append(
            {
                "role": role,
                "content": content.strip(),
            }
        )

        return history[
            -self.max_messages:
        ]

    # ============================================================
    # GET RECENT HISTORY
    # ============================================================

    def get_recent_history(
        self,
        history: list[dict[str, str]],
        limit: int | None = None,
    ) -> list[dict[str, str]]:
        """
        Return the most recent messages.
        """

        if not history:
            return []

        requested_limit = (
            limit
            if limit is not None
            else self.max_messages
        )

        requested_limit = max(
            1,
            requested_limit,
        )

        return history[
            -requested_limit:
        ]

    # ============================================================
    # FORMAT FOR LLM
    # ============================================================

    def format_for_llm(
        self,
        history: list[dict[str, str]],
    ) -> str:
        """
        Convert structured conversation history
        into a readable format for the LLM.
        """

        if not history:
            return ""

        parts = []

        for message in history:

            role = message.get(
                "role",
                "",
            )

            content = message.get(
                "content",
                "",
            ).strip()

            if not content:
                continue

            if role == "user":
                parts.append(
                    f"User: {content}"
                )

            elif role == "assistant":
                parts.append(
                    f"Assistant: {content}"
                )

            elif role == "system":
                parts.append(
                    f"System: {content}"
                )

        return "\n\n".join(parts)

    # ============================================================
    # ESTIMATE MEMORY SIZE
    # ============================================================

    def get_message_count(
        self,
        history: list[dict[str, str]],
    ) -> int:
        """
        Return number of messages currently
        included in memory.
        """

        return len(history)


# ================================================================
# SHARED SERVICE INSTANCE
# ================================================================

memory_service = MemoryService(
    max_messages=20,
)