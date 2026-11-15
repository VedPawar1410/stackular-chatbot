"""Scrape stackular.com and (re)build the Pinecone index.

Run once locally, and again whenever the website changes:
    python build_index.py

Fails loudly, leaving the index untouched, if any page can't be fetched.
"""
from dotenv import load_dotenv

load_dotenv()

from rag import Embedder, build_index, check_facts, get_index  # noqa: E402

if __name__ == "__main__":
    print("Loading embedding model...")
    embedder = Embedder()
    index = get_index()
    print("Scraping pages...")
    n = build_index(index, embedder)
    print(f"OK: upserted {n} vectors into the index.")

    # COMPANY_FACTS is hand-written; warn (don't fail) if the site no longer backs a fact.
    print("Checking COMPANY_FACTS against the live site...")
    missing = check_facts()
    if missing:
        print("WARNING: these facts may be outdated; update COMPANY_FACTS in rag.py:")
        for m in missing:
            print(f"  - {m}")
    else:
        print("OK: all company facts still appear on the site.")
