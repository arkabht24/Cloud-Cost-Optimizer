from dotenv import load_dotenv
import os

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "azure_best_practices")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
AZURE_SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "3"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0"))
OLLAMA_REQUEST_TIMEOUT = int(os.getenv("OLLAMA_REQUEST_TIMEOUT", "60"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "450"))
ALLOW_TRACE_RESPONSE = os.getenv("ALLOW_TRACE_RESPONSE", "false").lower() == "true"
RAGAS_EVALUATOR_MODEL = os.getenv("RAGAS_EVALUATOR_MODEL", "llama3.2:latest")
RAGAS_API_BASE_URL = os.getenv("RAGAS_API_BASE_URL", "http://127.0.0.1:8000")
ANALYSIS_API_BASE_URL = os.getenv("ANALYSIS_API_BASE_URL", "http://127.0.0.1:8000")
RAGAS_EVALUATOR_PROVIDER = os.getenv("RAGAS_EVALUATOR_PROVIDER", "gemini").lower()
RAGAS_MAX_CASES = int(os.getenv("RAGAS_MAX_CASES", "0"))
RAGAS_REQUEST_TIMEOUT = int(os.getenv("RAGAS_REQUEST_TIMEOUT", "60"))
RAGAS_MAX_RETRIES = int(os.getenv("RAGAS_MAX_RETRIES", "2"))
RAGAS_MAX_WAIT = int(os.getenv("RAGAS_MAX_WAIT", "8"))
RAGAS_JUDGE_CONCURRENCY = int(os.getenv("RAGAS_JUDGE_CONCURRENCY", "4"))
RAGAS_CORRECTNESS_TIMEOUT = int(os.getenv("RAGAS_CORRECTNESS_TIMEOUT", "120"))
RAGAS_CORRECTNESS_MAX_RETRIES = int(os.getenv("RAGAS_CORRECTNESS_MAX_RETRIES", "4"))
RAGAS_CORRECTNESS_MAX_WAIT = int(os.getenv("RAGAS_CORRECTNESS_MAX_WAIT", "20"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GEMINI_OPENAI_BASE_URL = os.getenv(
    "GEMINI_OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
)
