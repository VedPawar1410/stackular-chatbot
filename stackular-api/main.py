from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from rag import build_index_if_empty, rag_answer
import os

load_dotenv()

app = FastAPI()

# CORS — allows the Vercel frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your Vercel URL after deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Load models once at startup, not per request ──
print("Loading embedding model...")
embedder = SentenceTransformer('BAAI/bge-small-en')

print("Connecting to Pinecone...")
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
INDEX_NAME = "bge-small-en"
if INDEX_NAME not in pc.list_indexes().names():
    # 384 = bge-small-en embedding size; a fresh Pinecone account has no index yet
    print(f"Creating Pinecone index '{INDEX_NAME}'...")
    pc.create_index(INDEX_NAME, dimension=384, metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"))
index = pc.Index(INDEX_NAME)

build_index_if_empty(index, embedder)
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
