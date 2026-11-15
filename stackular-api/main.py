from collections import defaultdict, deque
from threading import Lock
import os
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

from rag import Embedder, get_index, rag_answer  # noqa: E402 (needs env loaded first)

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
embedder = Embedder()

print("Connecting to Pinecone...")
index = get_index()
# The API only serves; building the index is a separate step (python build_index.py).
if index.describe_index_stats().get("total_vector_count", 0) == 0:
    print("WARNING: Pinecone index is empty. Run `python build_index.py` first.")
print("API ready.")


# ── Rate limit: protects the free Groq quota from one client hammering /chat ──
# In-memory, so it resets when the server restarts or Render puts it to sleep. Good enough
# for a demo; a multi-instance or abuse-proof setup would need a shared store like Redis.
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "10"))
_hits: dict[str, deque] = defaultdict(deque)
_hits_lock = Lock()  # sync endpoints run in a thread pool, so guard the shared dict


def client_ip(request: Request) -> str:
    # Behind Render's proxy the real client is the first X-Forwarded-For entry.
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[0].strip() if forwarded else request.client.host


def check_rate_limit(ip: str) -> None:
    now = time.time()
    with _hits_lock:
        hits = _hits[ip]
        while hits and hits[0] < now - 60:  # drop requests older than the 60 s window
            hits.popleft()
        if len(hits) >= RATE_LIMIT_PER_MIN:
            raise HTTPException(status_code=429, detail="Too many messages. Please wait a minute.")
        hits.append(now)


# ── Request/Response schema ──
class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)  # cap prompt size (and token cost)

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
def chat(request: ChatRequest, http_request: Request):
    check_rate_limit(client_ip(http_request))  # before any embedding or LLM work
    answer = rag_answer(request.question, index, embedder)
    return ChatResponse(answer=answer)
