# rag.py

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from bs4 import BeautifulSoup
from pinecone import Pinecone, ServerlessSpec
from fastembed import TextEmbedding
import numpy as np
import requests
import os

# llama-3.3-70b-versatile was decommissioned on Groq; override with GROQ_MODEL if this one goes too.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
EMBED_MODEL = "BAAI/bge-small-en"
INDEX_NAME = "bge-small-en"
EMBED_DIM = 384  # bge-small-en output size; the Pinecone index must match


class Embedder:
    """bge-small-en via fastembed (ONNX runtime) instead of sentence-transformers (torch).

    Same weights, same vectors (cosine 1.0 vs the torch version, so the index didn't need
    rebuilding), but no torch: small enough for a 512 MB free Render instance.
    """

    def __init__(self):
        self.model = TextEmbedding(EMBED_MODEL)

    def encode(self, texts: list[str], **_) -> np.ndarray:
        return np.array(list(self.model.embed(texts)))


def get_index():
    """Connect to the Pinecone index, creating it on a fresh account."""
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    if INDEX_NAME not in pc.list_indexes().names():
        print(f"Creating Pinecone index '{INDEX_NAME}'...")
        pc.create_index(INDEX_NAME, dimension=EMBED_DIM, metric="cosine",
                        spec=ServerlessSpec(cloud="aws", region="us-east-1"))
    return pc.Index(INDEX_NAME)

STACKULAR_PAGES = [
    "https://www.stackular.com/",
    "https://www.stackular.com/services/",
    "https://www.stackular.com/about",
    "https://www.stackular.com/industries",
    "https://www.stackular.com/portfolio",
    "https://www.stackular.com/joinus",
    "https://www.stackular.com/contact-us",
    "https://www.stackular.com/privacy-policy",
    "https://www.stackular.com/portfolio/ap-automation-for-global-hospitality-organization",
    "https://www.stackular.com/portfolio/case-management-system-for-healthcare-services-company",
    "https://www.stackular.com/portfolio/ux-redesign-for-international-rideshare-company",
    "https://www.stackular.com/portfolio/extranet-modernization-for-global-hospitality-organization",
    "https://www.stackular.com/portfolio/modern-data-platform-for-healthcare-services-company",
    "https://www.stackular.com/portfolio/procure-to-pay-app-modernization-for-global-hospitality-organization",
]

# One paragraph, not six one-liners: tiny chunks that mostly say "Stackular" matched every
# question and pushed real page content out of the top results. Every fact here was checked
# against stackular.com in Nov 2026 (the email/phone live in the site footer, which the
# scraper strips, so they must be added by hand).
COMPANY_FACTS = (
    "Stackular company facts. Stackular was founded by Jason Storch (Founder & CEO) and "
    "Venkat Varkala (Founder & CTO). Stackular has offices in Columbia, Maryland, USA "
    "(10490 Little Patuxent Pkwy, Columbia, MD 21044); Chicago, Illinois, USA "
    "(3432 W Diversey Ave., Chicago, IL 60647); Hyderabad, India (Sandhya Techno 1, "
    "Gachibowli Road, Raidurg, Hyderabad, TG 500032); and San José, Costa Rica (Plaza Tempo, "
    "Escazú). Email: info@stackular.com. Phone: 1 (888) 278-8667. Contact page: "
    "https://www.stackular.com/contact-us. Open positions: https://www.stackular.com/joinus."
)

# A real page has far more text than this; less means the fetch or the page layout broke.
MIN_PAGE_CHARS = 200


def scrape_page(url: str) -> tuple[str, str]:
    """Fetch a page and return (title, main text). Raises on any failure (no silent "").

    stackular.com is server-rendered, so plain HTTP returns the same text Selenium did
    (checked: /about 1090 vs 1088 chars) without needing Chrome on the server.
    """
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    resp.raise_for_status()
    # Pass bytes, not resp.text: the server sends no charset header, so requests guesses
    # ISO-8859-1 and turns "we’re" into "weâ€™re". BeautifulSoup reads <meta charset> instead.
    soup = BeautifulSoup(resp.content, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else url
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    if len(text) < MIN_PAGE_CHARS:
        raise ValueError(f"only {len(text)} chars of text")
    return title, text


def build_index(index, embedder) -> int:
    """Scrape every page, chunk, embed and replace the index contents. Returns vector count."""
    texts, failures = [], []
    for url in STACKULAR_PAGES:
        try:
            title, text = scrape_page(url)
            texts.append((url, title, text))
            print(f"  OK   {len(text):>6} chars  {url}")
        except Exception as e:
            failures.append(f"{url}: {e}")
            print(f"  FAIL {url}: {e}")
    if failures:
        # Refuse to build a partial index: that is how the old code ended up with only facts.
        raise RuntimeError(f"{len(failures)} page(s) failed, index not changed:\n" + "\n".join(failures))
    texts.append(("company-facts", "Stackular company facts", COMPANY_FACTS))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", " "]
    )
    # Contextual chunk header: prefix each chunk with its page title so the vector knows what
    # the chunk is about (bare service headings on /services were losing to long case studies).
    chunks = [(src, f"[{title}] {c}") for src, title, text in texts for c in splitter.split_text(text)]
    print(f"  {len(texts)} sources -> {len(chunks)} chunks")
    embeddings = embedder.encode([c for _, c in chunks], show_progress_bar=True)

    vectors = [
        {"id": f"chunk_{i}", "values": emb.tolist(), "metadata": {"text": c, "source": src}}
        for i, ((src, c), emb) in enumerate(zip(chunks, embeddings))
    ]
    if index.describe_index_stats().get("total_vector_count", 0) > 0:
        index.delete(delete_all=True)  # full rebuild, so no stale chunks survive
    for i in range(0, len(vectors), 100):
        index.upsert(vectors=vectors[i:i+100])
    return len(vectors)


def retrieve(question: str, index, embedder, top_k: int = 5) -> list[str]:
    q_embedding = embedder.encode([question]).tolist()[0]
    results = index.query(
        vector=q_embedding,
        top_k=top_k,
        include_metadata=True
    )
    return [match["metadata"]["text"] for match in results["matches"]]


def rag_answer(question: str, index, embedder) -> str:
    chunks = retrieve(question, index, embedder)
    context = "\n\n".join(chunks)

    text = "My expertise is focused on Stackular's services, industries, and company. For anything else, here's how to reach the team: [Contact Stackular](https://www.stackular.com/contact-us)"

    prompt = f"""You are a concise, friendly assistant embedded on the Stackular website.
Stackular is a software consulting and development company with offices in Columbia (Maryland, USA), Chicago (Illinois, USA), Hyderabad (India) and San José (Costa Rica).

You help website visitors — potential clients, job applicants, or general visitors — get clear answers about Stackular.

---

## RESPONSE RULES

### RULE 1 — Answer length
- Always answer in 1–2 sentences maximum.
- Never pad answers with phrases like "you can find more information", "feel free to contact us", or "visit our website" UNLESS the visitor explicitly asks for contact details or more information.
- For greetings (Hi, Hello, Hey, etc.), respond warmly in one sentence only. No company pitch. No links.

### RULE 2 — Links are conditional, not automatic
Only include a link if ONE of these is true:
  (a) The visitor is asking about contact, careers, or privacy — use the designated links below.
  (b) The context is incomplete and the link will directly answer what was asked.
  (c) The visitor explicitly asks "where can I learn more" or similar.

NEVER append a link just to be helpful. If the answer is in the context, the answer alone is sufficient.

Designated links (use ONLY when condition above is met):
- Contact questions → [Contact Stackular](https://www.stackular.com/contact-us#:~:text=info%40stackular.com,888)%20278%2D8667)
- Career questions → [View open positions](https://www.stackular.com/joinus#:~:text=OUR%20CURRENT%20OPENINGS)
- Privacy/data questions → [Privacy Policy](https://www.stackular.com/privacy-policy)
- Portfolio questions → [View Portfolio](https://www.stackular.com/portfolio)

### RULE 3 — Link placement
When a link IS needed, place it on a new line AFTER the answer. Never embed it inside the answer sentence.

### RULE 4 — Lists
Use bullet points only when listing 3 or more items. Never for single items.

### RULE 5 — Off-topic questions
If the question is unrelated to Stackular, respond with exactly:
"{text}"

### RULE 6 — Missing information
If the context does not contain the answer, say so briefly and point to the most relevant page. Never say "I don't have that information" in isolation.

---

## EXAMPLES (follow these exactly)

Q: Hi
A: Hello! Welcome to Stackular — feel free to ask me anything about our services or company. 👋

Q: Where is Stackular located in India?
A: Stackular's India office is located in Hyderabad.

Q: Where is Stackular?
A: Stackular has offices in Columbia, Maryland and Chicago, Illinois in the USA, Hyderabad in India, and San José in Costa Rica.

Q: What projects has Stackular done?
A: Stackular has worked across industries including Commercial and Hospitality, with projects featuring redesigned interfaces, unified entry points, and expanded offerings.
[View Portfolio](https://www.stackular.com/portfolio)

Q: How can I contact Stackular?
A: You can reach the Stackular team directly here:
[Contact Stackular](https://www.stackular.com/contact-us#:~:text=info%40stackular.com,888)%20278%2D8667)

Q: What is the weather today?
A: My expertise is focused on Stackular's services, industries, and company. For anything else, here's how to reach the team: [Contact Stackular](https://www.stackular.com/contact-us)

---

Context from Stackular's website:
{context}

Visitor's question: {question}

Answer:"""

    llm = ChatGroq(
        model=GROQ_MODEL,
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0  # factual Q&A: same question, same answer
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content