---
title: Stackular Chatbot API (demo)
emoji: 💬
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

FastAPI backend for the Stackular website chatbot demo (RAG over stackular.com with
Pinecone + bge-small-en + Groq). Built by Ved Pawar as a portfolio demo; not an official
Stackular service.

Endpoints: `GET /health`, `POST /chat` with `{"question": "..."}`.
Needs Space secrets `GROQ_API_KEY` and `PINECONE_API_KEY`. The index is built separately
with `python build_index.py`. See the main repo: https://github.com/VedPawar1410/stackular-chatbot
