from collections.abc import Generator

from google import genai
from google.genai import types

from app.core.config import settings


class LLMService:
    """
    Handles communication with the Gemini LLM.

    This service is responsible ONLY for:
    - sending prompts to Gemini
    - normal responses
    - streaming responses

    RAG, memory, retrieval, and conversation management
    will be handled by separate services.
    """

    SYSTEM_INSTRUCTION = """
You are NEXA AI, a professional and helpful AI assistant.

Rules:
- Be accurate and clear.
- Answer the user's question directly.
- Use the provided conversation history when relevant.
- Use the provided knowledge/context when available.
- Do not invent facts.
- If the provided context does not contain the answer, say so.
- Keep simple questions concise.
- For technical questions, provide structured explanations.
- Use Markdown when it improves readability.
"""

    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured."
            )

        self.client = genai.Client(
            api_key=settings.gemini_api_key
        )

    # ========================================================
    # BUILD PROMPT
    # ========================================================

    def build_prompt(
        self,
        user_message: str,
        conversation_history: list[dict] | None = None,
        retrieved_context: str | None = None,
    ) -> str:

        conversation_history = conversation_history or []

        prompt_parts = []

        # ----------------------------------------------------
        # CONVERSATION HISTORY
        # ----------------------------------------------------

        if conversation_history:

            prompt_parts.append(
                "CONVERSATION HISTORY:"
            )

            for message in conversation_history:

                role = message.get("role")
                content = message.get(
                    "content",
                    ""
                ).strip()

                if not content:
                    continue

                if role == "user":
                    prompt_parts.append(
                        f"User: {content}"
                    )

                elif role == "assistant":
                    prompt_parts.append(
                        f"Assistant: {content}"
                    )

        # ----------------------------------------------------
        # RAG CONTEXT
        # ----------------------------------------------------

        if retrieved_context:

            prompt_parts.append(
                "\nRELEVANT KNOWLEDGE:"
            )

            prompt_parts.append(
                retrieved_context
            )

        # ----------------------------------------------------
        # CURRENT QUESTION
        # ----------------------------------------------------

        prompt_parts.append(
            "\nCURRENT USER QUESTION:"
        )

        prompt_parts.append(
            user_message
        )

        return "\n\n".join(prompt_parts)

    # ========================================================
    # NORMAL RESPONSE
    # ========================================================

    def generate_response(
        self,
        user_message: str,
        conversation_history: list[dict] | None = None,
        retrieved_context: str | None = None,
    ) -> str:

        prompt = self.build_prompt(
            user_message=user_message,
            conversation_history=conversation_history,
            retrieved_context=retrieved_context,
        )

        response = self.client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=self.SYSTEM_INSTRUCTION,
                max_output_tokens=2048,
            ),
        )

        return response.text or (
            "I'm sorry, but I couldn't generate a response."
        )

    # ========================================================
    # STREAMING RESPONSE
    # ========================================================

    def generate_response_stream(
        self,
        user_message: str,
        conversation_history: list[dict] | None = None,
        retrieved_context: str | None = None,
    ) -> Generator[str, None, None]:

        prompt = self.build_prompt(
            user_message=user_message,
            conversation_history=conversation_history,
            retrieved_context=retrieved_context,
        )

        response_stream = (
            self.client.models.generate_content_stream(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_INSTRUCTION,
                    max_output_tokens=2048,
                ),
            )
        )

        for chunk in response_stream:

            text = getattr(
                chunk,
                "text",
                None
            )

            if text:
                yield text


# ============================================================
# SHARED SERVICE INSTANCE
# ============================================================

llm_service = LLMService()
