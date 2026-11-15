# Stackular Website Chatbot (demo)

A RAG chatbot that answers visitor questions about Stackular (services, offices, founders,
open roles, case studies) using text scraped from stackular.com. Built by Ved Pawar as a
portfolio demo; **not the official Stackular website**.

**Live demo:** https://stackular-chatbot.vercel.app (API: https://stackular-chatbot.onrender.com/health)

| Metric (16-case eval, Nov 2026) | Result |
|---|---|
| Live API pass rate | **16 / 16** |
| Median answer latency (live, warm) | 2.7 s |
| Backend memory (512 MB container, 5 concurrent chats) | 277 MB peak |
| Vectors in index | 388 chunks from 14 pages + 1 facts block |

![Chatbot UI](assests/chatbot-ui.png)
*UI from the original March 2026 build; the live site now also shows a yellow "DEMO" badge.*

## How it works

```
 build time (run locally: python build_index.py)
 ┌──────────────┐  requests   ┌───────────────┐  title-prefixed   ┌──────────────┐  fastembed   ┌──────────┐
 │ 14 pages on  │ ──────────▶ │ BeautifulSoup │ ── 500-char ────▶ │ chunks +     │ ───────────▶ │ Pinecone │
 │ stackular.com│  fail loud  │ strip nav/foot│    chunks         │ facts block  │ bge-small-en │ 384-dim  │
 └──────────────┘             └───────────────┘                   └──────────────┘              └────┬─────┘
                                                                                                     │
 request time                                                                                        │ top 5
 ┌───────────────┐  POST /chat  ┌──────────────────────┐  embed question  ┌───────────┐  ◀─────────────┘
 │ Next.js widget│ ───────────▶ │ FastAPI (Render)     │ ───────────────▶ │ retrieve  │
 │ (Vercel)      │ ◀─────────── │ rules prompt + chunks│ ◀── answer ───── │ Groq LLM  │ gpt-oss-120b, temp 0
 └───────────────┘   answer     └──────────────────────┘                  └───────────┘
```

**Why these choices**
- **Index building is a separate script, not API startup.** The server only serves. If any
  page fails to scrape, the build stops and leaves the old index alone instead of quietly
  indexing whatever it got.
- **Plain `requests` instead of Selenium.** stackular.com is server-rendered; both returned
  the same text (/about: 1090 vs 1088 chars), and the server no longer needs Chrome.
- **fastembed (ONNX) instead of sentence-transformers (torch).** Same `BAAI/bge-small-en`
  weights and identical vectors (cosine 1.0), but the image went from 2.2 GB to 803 MB, so
  it fits Render's free 512 MB tier.
- **Page title in front of every chunk** (`[AI-Driven Services | Stackular] ...`) so a chunk's
  vector carries what page it came from.
- **One verified facts paragraph** (founders, 4 offices, email, phone) because the email and
  phone only exist in the site footer, which the scraper strips.
- **Groq model from `GROQ_MODEL` env var.** The original model was retired; the replacement
  was picked by eval (gpt-oss-120b 14/16 vs qwen3.8-27b 10/16 on the same code).
- **Keyword routing to topic pages.** If a question names a topic with its own page
  ("services", "jobs", "industries", "founder"...), retrieval also pulls that page's opening
  chunk (its overview) and its best-matching chunk. Pure vector search with bge-small never
  surfaced `/services` for "What services do you offer?"; full hybrid search would have
  needed a different index type and an extra encoder in 512 MB.
- **Per-IP rate limit (10/min) and a 500-character question cap** to protect the free Groq
  quota; the check runs before any embedding or LLM call.
- **Cold-start handling instead of a keep-alive cron.** The widget pings the API when the
  page loads so a sleeping Render instance starts waking early, and shows "Waking up the
  server..." if an answer takes over 5 s.
- **Fact drift check.** `build_index.py` confirms every hand-written fact still appears on
  the live site and warns if one disappears.

## Built on a $0 budget

Everything runs on free tiers (Groq, Pinecone Starter, Render free, Vercel Hobby), and that
constraint drove the design: the retired Groq model was replaced by eval, the torch embedder
(626 MB) was swapped for fastembed (277 MB peak for the whole API) to fit Render's 512 MB,
and the planned Hugging Face host was dropped when its Docker tier became paid. The full
story (every constraint, the workaround, and what we'd do with a budget), the step-by-step
process, the mistakes made during the rebuild and the verification commands are in
**[docs/rebuild-notes.md](docs/rebuild-notes.md)**.

## Data

- **Source:** 14 public stackular.com pages listed in `stackular-api/rag.py`
  (`STACKULAR_PAGES`): home, services, about, industries, portfolio, careers, contact,
  privacy policy and 6 case studies. Scraped November 2026; about 150k characters of text.
- **Plus** `COMPANY_FACTS` in `rag.py`, each fact checked against the site in Nov 2026.
- Nothing is stored in the repo; the index lives in Pinecone (`bge-small-en`, 384 dims,
  cosine, serverless aws us-east-1). Re-run `python build_index.py` when the site changes.

## Results

Eval: 16 questions in `stackular-api/eval/cases.json`, each graded by substring rules
(must contain / must not contain). Answers are saved in `stackular-api/reports/eval.json`
so every grade can be checked by eye.

| Stage (same 16 cases) | Pass | Notes |
|---|---|---|
| Original code, as committed | **0 / 16** | every request 404: `llama-3.3-70b-versatile` retired on Groq |
| Original code, model swapped to qwen3.8-27b | 10 / 16 | |
| Original code, model swapped to gpt-oss-120b | 14 / 16 | email passed only by decoding it out of a URL in the prompt |
| + fixed facts, chunk headers, temp 0 (local) | 15 / 16 | |
| fastembed build (local) | 16 / 16 | same vectors; services passed on wording, not retrieval |
| Live on Render (first deploy) | 15 / 16 | only `services` failed |
| + keyword routing, 2 chunks per page (local) | 15 / 16 twice | services answer now from `/services` but listed sub-services |
| + routing to page opening + best chunk (local) | 16 / 16 twice | services answer lists the six real categories |
| **Live on Render (final)** | **16 / 16** | median 2.7 s, max 3.4 s |

**Before vs. after**

| | Before (March 2026 code, run Nov 2026) | After |
|---|---|---|
| Fresh install starts | No: `ModuleNotFoundError: langchain_openai` | Yes |
| Answers questions | No (retired model) | 16/16 live |
| Scraping | Selenium + Chrome; a failure became `""` silently | `requests`; any failure stops the build |
| Facts | 2 offices, invented "founded 2015", no email/phone | 4 offices, email, phone, all verified |
| Embedder memory | 626 MB peak (torch) | 277 MB peak for the whole API |
| Docker image | n/a (2.2 GB with torch) | 803 MB |
| Dependencies | unpinned | pinned, Python 3.12 |
| Dev script | Windows only | macOS/Linux (Windows untested) |
| Deployed | No | Vercel + Render (free) |
| Abuse protection | none | 10 req/min per IP (429), 500-char cap |
| Cold start | n/a | pre-warm on page load + "waking up" hint (real cold start not measured) |
| Mobile nav | overflowed off-screen | links hidden below 768 px |
| Hand-written facts | unchecked (2 were wrong) | checked against the live site on every rebuild |

## Project structure

```
stackular-chatbot/
├── package.json              # dev:all runs API + frontend together (concurrently)
├── assests/                  # README screenshots (folder name typo kept from the original)
├── docs/rebuild-notes.md     # how the Nov 2026 rebuild went: constraints, process, commands
├── stackular-api/
│   ├── main.py               # FastAPI app: /, /health, /chat; CORS from ALLOWED_ORIGINS
│   ├── rag.py                # config, scraper, index build, retrieval, prompt, Groq call
│   ├── build_index.py        # CLI: scrape + rebuild the Pinecone index
│   ├── eval/cases.json       # 16 eval questions with grading rules
│   ├── eval/run_eval.py      # runs the eval, writes reports/eval.json
│   ├── reports/eval.json     # latest eval results with every answer
│   ├── Dockerfile            # Render image (fastembed model baked in)
│   ├── requirements.txt      # pinned runtime deps
│   ├── .python-version       # 3.12
│   └── .env.example          # GROQ_API_KEY, PINECONE_API_KEY; optional GROQ_MODEL, ALLOWED_ORIGINS, RATE_LIMIT_PER_MIN
└── stackular-frontend/
    ├── app/page.js           # Stackular-style landing page
    ├── app/layout.js         # root layout, DEMO badge, mounts the widget
    ├── components/ChatWidget.jsx  # floating chat widget, calls POST /chat
    └── .env.example          # NEXT_PUBLIC_CHATBOT_API_URL
```

## Run locally

Needs Python 3.12, Node 18+, a Groq key and a Pinecone key.

```bash
cd stackular-api
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then fill in your keys
python build_index.py            # first time only: scrapes 14 pages, ~388 vectors
cd ..
npm install
cd stackular-frontend && npm install && cd ..
npm run dev:all                  # API on :8000, site on :3000 (keep the venv activated)
```

Open http://localhost:3000. Run the eval (from `stackular-api/`, venv active):

```bash
python -m eval.run_eval
```

## Deployment

- **Backend: Render** free web service, Docker runtime, root directory `stackular-api`,
  health check path `/`. Env vars: `GROQ_API_KEY`, `PINECONE_API_KEY`,
  `ALLOWED_ORIGINS=https://stackular-chatbot.vercel.app`. Render sets `$PORT`.
  Auto-deploys on push to `main`.
- **Frontend: Vercel**, root directory `stackular-frontend`, env var
  `NEXT_PUBLIC_CHATBOT_API_URL=https://stackular-chatbot.onrender.com` (baked in at build
  time, so changing it needs a redeploy). Auto-deploys on push to `main`.
- The Pinecone index is built from a laptop with `python build_index.py`, not on Render.

## Limitations

- **Keyword routing needs a trigger word.** "What services do you offer?" routes to
  `/services`; "What do you do?" doesn't, and falls back to plain vector search, where
  bge-small still ranks `/services` poorly.
- **Cold starts.** Render's free tier sleeps after ~15 min idle; I couldn't measure a real one:
  after 17 minutes without my traffic the instance was still awake (0.2 s), possibly because
  visitors' pre-warm pings kept it up. The pre-warm ping hides part of the wake-up when
  visitors spend a few seconds on the page before asking.
- **The rate limit is demo-grade:** it lives in memory (resets when Render sleeps or
  restarts) and trusts the first `X-Forwarded-For` entry, which a client can fake (verified).
- **The eval is small and coarse:** 16 cases, substring grading, one or two runs per stage.
  Even at temperature 0 the wording varies between runs.
- **`COMPANY_FACTS` is still hand-written.** The drift check confirms each fact still appears
  on its page, not that it is still correct in context.
- **`app/globals.css` is never imported** by the layout, so its rules don't apply (found
  while fixing the mobile nav; left as is to avoid restyling the whole page).
- `dev:all` is untested on Windows.

## Learning log: mistakes and what I learned

Built in layers; each records what went wrong and the lesson.

### Layer 1 - The original build (25 March 2026, Next.js + FastAPI + Selenium + Pinecone + Groq)

*What I built:* in one day at the start of my time at Stackular, a RAG chatbot for the company
website: Selenium scraper, bge-small embeddings in Pinecone, Llama 3.3 70B on Groq, and a
Next.js chat widget.

| # | Mistake | What actually happened | Lesson |
|---|---|---|---|
| 1.1 | **Dead import missing from requirements** | `rag.py` imported `langchain_openai` for a commented-out fallback; it wasn't in `requirements.txt`, so a fresh install crashed on startup. It only worked on my machine. | Test from a clean environment built only from the requirements file. |
| 1.2 | **Hard-coded external model** | Groq retired `llama-3.3-70b-versatile`; by Nov 2026 every `/chat` returned 404 (0/16). | Treat third-party models as config that will change, and have an eval to pick a replacement. |
| 1.3 | **Silent scrape failures** | `scrape_page` caught every error and returned `""`, and the index was built only if empty. On a server without Chrome it would index just the 6 curated facts and never rebuild. | Fail loudly and check counts; a partial index is worse than none. |
| 1.4 | **A browser for a server-rendered site** | Selenium and plain HTTP returned the same text (/about 1088 vs 1090 chars) but Selenium needed Chrome, which blocked deployment. | Check whether you need a browser before adding one. |
| 1.5 | **Cleaner threw away the contact info** | The email and phone only exist in `<footer>`, which the scraper deleted. The bot still "knew" the email because it decoded `info%40stackular.com` from a link in the prompt. | Look at what your cleaning step removes; a passing answer can be passing by accident. |
| 1.6 | **Stale and invented facts** | The prompt said 2 offices (the site lists 4), "headquartered in Columbia" (never stated) and "founded in 2015" (not on the site). | Every hard-coded fact needs a source and a date. |
| 1.7 | **Tiny chunks hijacked retrieval** | For "What services do you offer?" the top 3 results were three one-line curated facts, so the bot said it had no list of services. | Inspect what retrieval actually returns, not just the final answer. |
| 1.8 | **Indexing inside API startup** | Scraping 14 pages ran on boot whenever the index was empty, slowing startup and hiding failures. | Separate offline jobs (build the index) from serving. |
| 1.9 | **No eval** | Nothing told me the bot was wrong about offices or services, or that it had stopped working. | Even 16 hand-written cases beat none. |
| 1.10 | **Loose ends** | Unpinned deps, a Windows-only dev script, `temperature=0.7` for facts, a widget that crashed on a 500, a leftover `note.txt`. | Small hygiene issues are what break a project months later. |

### Layer 2 - The rebuild (November 2026, Claude Code)

*What I did:* measured first (16-case eval), fixed the root causes one commit at a time, and
deployed it for free on Vercel + Render with a visible demo label.

| # | Decision | Why |
|---|---|---|
| 2.1 | Wrote the eval before changing code | Gave honest before/after numbers: 0/16, then 14, 15, and 15/16 live (1.9). |
| 2.2 | Chose `openai/gpt-oss-120b` by eval; model in `GROQ_MODEL` | 14/16 vs 10/16 for qwen on identical code; next retirement is a config change (1.2). |
| 2.3 | `requests` scraper + fail-loud `build_index.py` | Removes Chrome, no silent partial index, API only serves (1.3, 1.4, 1.8). |
| 2.4 | One verified facts paragraph | Adds email, phone and all offices; drops the invented year; no tiny chunks (1.5, 1.6, 1.7). |
| 2.5 | Page title prefixed to each chunk | Helps vectors know what a chunk is about; the home page's services section now ranks 2nd. |
| 2.6 | Pass bytes, not text, to BeautifulSoup | My own bug: no charset header made `requests` guess ISO-8859-1 and garble apostrophes ("weâ€™re"). Now 0 of 388 chunks garbled. |
| 2.7 | fastembed instead of torch | Same vectors (cosine 1.0, no re-index), 277 MB peak, fits a free 512 MB instance. |
| 2.8 | Render instead of Hugging Face Spaces | The plan was HF Spaces, but Docker Spaces had become paid on my account; I should have checked before planning. |
| 2.9 | `temperature=0`, pinned deps, `.env.example`, CORS from env, cross-OS dev script | Repeatable answers and installs (1.10). |
| 2.10 | Yellow DEMO badge and tab title | It's a portfolio demo of Stackular's site, so it must not pass as the official site. |

*Known gaps I chose not to fix:* services retrieval (needs a better embedder or hybrid
search), no rate limiting, hand-maintained facts, mobile nav overflow, cold starts.

### Layer 3 - Closing the known gaps (November 2026, Claude Code)

*What I did:* fixed the gaps Layer 2 left open, one commit each, staying on free tiers and
adding no new dependencies.

| # | Decision | Why |
|---|---|---|
| 3.1 | Keyword routing to topic pages instead of hybrid search | Fixes the services miss (16/16 on two runs) with ~30 lines; Pinecone hybrid needs a dotproduct index, a full re-index and a sparse encoder in 512 MB. |
| 3.2 | Route to a page's **opening** chunk + its best chunk | My first version took the 2 most similar chunks and still scored 15/16: they were sub-services. The category list was the page's first chunk, ranked only 6th. Most similar is not always most useful; overviews lose similarity contests to details. Needed a `pos` field per chunk and a re-index. |
| 3.3 | In-memory per-IP rate limit (10/min) + 500-char cap | Protects the free Groq quota with no new library; 429 has its own widget message. Verified live: request 11 returns 429. A faked `X-Forwarded-For` bypasses it, which I left as a known limit rather than risk one shared bucket for every visitor. |
| 3.4 | Pre-warm ping + "waking up" hint, not a keep-alive cron | Works with the free tier's sleep instead of gaming it, and makes the wait honest. Tested against a fake 8 s API. |
| 3.5 | Mobile nav rule in a `<style>` tag | The CSS fix first did nothing: `globals.css` was never imported (dead since March). Importing it would restyle the whole page, so I used the pattern the widget already uses. |
| 3.6 | Fact drift check that warns, not fails | Catches changed offices/phone/email at rebuild time without blocking a content refresh. Tested with planted wrong facts ("Founded in 2015", "Boston"). |

*Mistakes I caught along the way:* an early `return` in the widget that would have left the
typing dots spinning forever after a 429 (caught before running it), and the dead
`globals.css` making a correct CSS rule look broken.

*Known gaps I chose not to fix:* routing needs trigger words, demo-grade rate limiting,
cold starts on the free tier, the unused `globals.css`, Windows `dev:all`.

### Key takeaways

1. **Measure before fixing.** The eval found a dead model, stale facts and a lucky pass that reading the code alone missed.
2. **Silent failure is the worst failure.** `except: return ""` turned a missing browser into a quietly wrong chatbot.
3. **Check the plumbing before the algorithm.** Every real bug was config, imports, encodings or cleaning, not the RAG idea.
4. **External services rot.** Models get retired and free tiers change; keep them in config and check them before you plan.
5. **Your own fixes need checking too.** My rebuild added a mojibake bug and a grader bug, and the eval and spot-checks caught both.
6. **A cheap targeted fix can beat a "proper" one.** Keyword routing fixed what hybrid search would have, without a re-architecture.
7. **"The CSS didn't apply" usually means the file isn't loaded.** Check the plumbing before the rule.

## Future improvements

- Hybrid (keyword + vector) search or a stronger embedder, so routing isn't needed.
- A shared store (e.g. Redis) if the rate limit ever needs to be abuse-proof.
- Schedule `build_index.py` so the fact check runs without anyone remembering to.
- Multi-turn memory in the widget.
