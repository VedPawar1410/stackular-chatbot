# Stackular chatbot API

FastAPI backend for the Stackular website chatbot demo: RAG over stackular.com with
Pinecone, bge-small-en (via fastembed) and Groq. Built by Ved Pawar as a portfolio demo;
not an official Stackular service.

- `GET /health` - index vector count
- `POST /chat` with `{"question": "..."}` - returns `{"answer": "..."}`

Env vars: see `.env.example`. Build the index with `python build_index.py`.
Full docs: the repository root README.
