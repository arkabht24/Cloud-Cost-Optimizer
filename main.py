from rag.chain import run_chain


def main():
    print("Azure Cost Optimizer - Powered by RAG + Gemini")
    print("Type 'exit' to quit\n")

    resource_group = input("Enter Azure Resource Group name: ").strip()

    while True:
        question = input("Ask a cost optimization question: ").strip()

        if question.lower() == "exit":
            break

        if not question:
            continue

        print("\nAnalyzing...\n")

        response = run_chain(question, resource_group)

        print(f"Advice:\n{response}\n")
        print("-" * 60 + "\n")


if __name__ == "__main__":
    main()