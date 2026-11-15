"""Scrape stackular.com and (re)build the Pinecone index.

Run once locally, and again whenever the website changes:
    python build_index.py

Fails loudly, leaving the index untouched, if any page can't be fetched.
"""
from dotenv import load_dotenv

load_dotenv()

from rag import Embedder, build_index, get_index  # noqa: E402

if __name__ == "__main__":
    print("Loading embedding model...")
    embedder = Embedder()
    index = get_index()
    print("Scraping pages...")
    n = build_index(index, embedder)
    print(f"OK: upserted {n} vectors into the index.")
