from langchain_chroma import Chroma
from ingestion.embedder import get_embedding_model
from config.settings import CHROMA_DB_PATH, COLLECTION_NAME
import json, os

PARENT_STORE_PATH = os.path.join(CHROMA_DB_PATH, "parents.json")


def store_chunks(parents, children):
    # Replace the collection so a re-ingestion updates parent metadata rather
    # than appending duplicate child chunks from a previous ingestion.
    try:
        Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=get_embedding_model(),
            persist_directory=CHROMA_DB_PATH,
        ).delete_collection()
    except Exception:
        # The first ingestion has no collection to remove.
        pass

    # langchain-chroma persists automatically when persist_directory is set.
    Chroma.from_documents(
        documents=children,
        embedding=get_embedding_model(),
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_DB_PATH
    )

    os.makedirs(CHROMA_DB_PATH, exist_ok=True)
    with open(PARENT_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "version": 2,
            "parents": {
                str(i): {"text": parent.page_content, "metadata": parent.metadata}
                for i, parent in enumerate(parents)
            },
        }, f)


def query_vector_store_with_metadata(query, top_k=3):
    """Return unique parent chunks together with their retrieval metadata."""
    db = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embedding_model(),
        persist_directory=CHROMA_DB_PATH
    )
    # Chroma's default distance metric is not guaranteed to satisfy
    # LangChain's [0, 1] relevance-score contract. Query raw distances and
    # convert them only for trace/display purposes; ranking remains Chroma's.
    hits = db.similarity_search_with_score(query, k=top_k)

    with open(PARENT_STORE_PATH, encoding="utf-8") as f:
        stored = json.load(f)
    # Support existing databases until the user re-runs ingestion.
    parents = stored.get("parents", stored) if isinstance(stored, dict) else {}

    seen, results = set(), []
    for hit, distance in hits:
        pid = str(hit.metadata.get("parent_id"))
        if pid not in seen and pid in parents:
            seen.add(pid)
            parent = parents[pid]
            if isinstance(parent, str):
                parent = {"text": parent, "metadata": {}}
            metadata = {**parent.get("metadata", {}), **hit.metadata}
            results.append({
                "id": pid,
                "text": parent["text"],
                "score": round(1 / (1 + max(float(distance), 0.0)), 6),
                "source": metadata.get("source"),
                "page": metadata.get("page"),
                "chunk_index": metadata.get("chunk_index"),
                "evidence_role": metadata.get("evidence_role"),
                "resource_names": metadata.get("resource_names", ""),
            })
    return results


def query_vector_store(query, top_k=3):
    """Backward-compatible text-only retrieval helper."""
    return [item["text"] for item in query_vector_store_with_metadata(query, top_k)]
