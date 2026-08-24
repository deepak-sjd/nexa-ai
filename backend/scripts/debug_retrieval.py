from app.services.rag_service import rag_service

query = "What is VectorStore?"

result = rag_service.search(query)

print("\nRETRIEVED\n")

for item in result["retrieved"]:
    print("=" * 80)
    print(item.content)
    print("=" * 80)

print("\nCONTEXT\n")
print(result["context"])