from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
import re

PDF_DIR = "./data/pdfs"

parent_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
child_splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20)


def evidence_role(text: str) -> str:
    """Classify a chunk by the kind of evidence it contributes to a decision."""
    lowered = text.lower()
    if any(marker in lowered for marker in ("known exceptions", "required follow-up", "rollback window", "retained")):
        return "exception"
    if "decision register" in lowered:
        return "decision"
    if any(marker in lowered for marker in ("p95", "unattached", "no reads", "usage", "utilization", "metrics", "snapshot")):
        return "utilization"
    if any(marker in lowered for marker in ("approved", "deferred", "pending")):
        return "decision"
    return "policy"


def resource_names(text: str) -> str:
    """Store likely Azure resource names in Chroma-compatible string metadata."""
    names = sorted(set(re.findall(r"(?<![\w-])[a-z0-9]+(?:-[a-z0-9]+)+(?![\w-])", text.lower())))
    return ",".join(names)


def load_pdfs():
    docs = []
    for filename in os.listdir(PDF_DIR):
        if filename.endswith(".pdf"):
            loader = PyPDFLoader(os.path.join(PDF_DIR, filename))
            docs.extend(loader.load())
    return docs


def get_parent_child_chunks(docs):
    parents = parent_splitter.split_documents(docs)
    for parent in parents:
        parent.metadata["evidence_role"] = evidence_role(parent.page_content)
        parent.metadata["resource_names"] = resource_names(parent.page_content)
    children = []
    for i, parent in enumerate(parents):
        kids = child_splitter.split_documents([parent])
        for chunk_num, kid in enumerate(kids):
            kid.metadata["parent_id"] = i
            kid.metadata["chunk_index"] = chunk_num
        children.extend(kids)
    return parents, children
