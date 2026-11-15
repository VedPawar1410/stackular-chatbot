from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import os

load_dotenv()

from rag import EMBED_MODEL, get_index, rag_answer  # noqa: E402 (needs env loaded first)

app = FastAPI()

# CORS — allows the Vercel frontend to call this API
app.add_middleware(
    CORSMiddleware,
    # Comma-separated list, e.g. "https://your-app.vercel.app". Defaults to "*" for local dev.
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Load models once at startup, not per request ──
print("Loading embedding model...")
embedder = SentenceTransformer(EMBED_MODEL)

print("Connecting to Pinecone...")
index = get_index()
# The API only serves; building the index is a separate step (python build_index.py).
if index.describe_index_stats().get("total_vector_count", 0) == 0:
    print("WARNING: Pinecone index is empty. Run `python build_index.py` first.")
print("API ready.")


# ── Request/Response schema ──
class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str


# ── Endpoints ──
@app.get("/")
def root():
    return {"status": "Stackular chatbot API is running"}

@app.get("/health")
def health():
    stats = index.describe_index_stats()
    return {
        "status": "ok",
        "vectors_in_index": stats.get("total_vector_count", 0)
    }

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    answer = rag_answer(request.question, index, embedder)
    return ChatResponse(answer=answer)
