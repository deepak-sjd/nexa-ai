from google import genai

from app.core.config import settings


class AIService:

    def __init__(self):
        self.client = genai.Client(
            api_key=settings.gemini_api_key
        )

    def generate_response(
        self,
        user_message: str,
        conversation_history: list[dict] | None = None,
    ) -> str:

        conversation_history = conversation_history or []

        prompt_parts = []

        for message in conversation_history:
            role = message["role"]
            content = message["content"]

            if role == "user":
                prompt_parts.append(f"User: {content}")

            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")

        # Add current user message
        prompt_parts.append(f"User: {user_message}")

        prompt = "\n\n".join(prompt_parts)

        response = self.client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )

        return response.text


# Create one shared AI service
ai_service = AIService()