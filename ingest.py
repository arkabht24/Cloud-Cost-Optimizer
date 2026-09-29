from ingestion.pdf_loader import load_pdfs, get_parent_child_chunks
from ingestion.vector_store import store_chunks

if __name__ == "__main__":
    print("Loading PDFs...")
    docs = load_pdfs()

    print("Creating parent-child chunks...")
    parents, children = get_parent_child_chunks(docs)
    print(f"Parents: {len(parents)} | Children: {len(children)}")

    print("Embedding and storing into ChromaDB...")
    store_chunks(parents, children)
    print("Ingestion complete. ChromaDB is ready.")