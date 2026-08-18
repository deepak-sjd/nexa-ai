from app.services.ai_service import ai_service


print("Testing Gemini...")

response = ai_service.generate_response(
    "Explain artificial intelligence in one simple sentence."
)

print("Gemini response:")
print(response)