from langchain_huggingface import HuggingFaceEmbeddings
from config.settings import EMBEDDING_MODEL

def get_embedding_model():
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        # The configured model is downloaded during ingestion. Subsequent API
        # calls must use that cached model rather than performing network checks.
        model_kwargs={"device": "cpu", "local_files_only": True},
        encode_kwargs={"normalize_embeddings": True}
    )
