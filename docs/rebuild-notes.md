# Rebuild notes: how the November 2026 revive actually went

The README says *what* the project is. This file records *how* it got rebuilt: the order
of work, every decision and the reason for it, the mistakes made along the way (mine and
the AI assistant's), how a **$0 budget** shaped the design, and the exact commands used to
verify each step. It is written for my future self, for interviews, and as context for AI
tools that work on this repo later.

Rebuild date: 15 November 2026 (one session, with Claude Code). Original build: 25 March 2026.

---

## 1. The constraint that shaped everything: $0

Every service had to stay on a free tier. Most of the design choices below would have been
different, and easier, with even a small budget.

| Service | Free-tier reality (Nov 2026) | What it forced us to do | With a budget we would... |
|---|---|---|---|
| **Groq** (LLM) | Free key, but tokens-per-minute limits; the original `llama-3.3-70b-versatile` had been **retired**. Only a handful of chat models left (gpt-oss-120b/20b, qwen3.8-27b, allam-2-7b). | Picked the replacement **by eval** (gpt-oss-120b 14/16 vs qwen 10/16). Put the model name in `GROQ_MODEL` so the next retirement is a config change. The eval sleeps 6 s between calls to stay under the rate limit. | Use a paid API with stable model versions (e.g. Claude or GPT) and an SLA; run evals without throttling. |
| **Pinecone** (vector DB) | Free Starter: serverless indexes in `aws us-east-1`. | Code creates the index itself (384 dims, cosine) so a fresh account works. One index, rebuilt in full each time. | Same; the free tier was never the bottleneck. |
| **Hugging Face Spaces** (planned backend host) | **Docker SDK had become "Paid" and CPU Basic was greyed out** on Ved's account; only Gradio on ZeroGPU was free. | Abandoned the plan mid-deployment. Gradio-on-ZeroGPU was rejected: wrapping FastAPI in Gradio is a hack, and every chat would burn GPU quota for work that needs no GPU. | Use a paid HF Space (16 GB RAM) and keep torch + sentence-transformers unchanged. |
| **Render** (actual backend host) | Free web service: **512 MB RAM**, Docker supported, **sleeps after ~15 min idle** (30-60 s cold start). | The torch-based embedder alone peaked at **626 MB**: too big. Swapped to **fastembed** (ONNX runtime, same model, identical vectors): whole API peaks at **277 MB** under 5 concurrent chats. Health-check path set to `/` (free) instead of `/health` (calls Pinecone on every ping). | A $7/month always-on instance: no cold starts, and torch would have fit without a rewrite. |
| **Vercel** (frontend) | Hobby tier, free; auto-deploys from GitHub. | Nothing special; `NEXT_PUBLIC_CHATBOT_API_URL` is baked in at build time, so changing it means a redeploy. | Same. |
| **Embedding model** | Must run on a CPU inside 512 MB. | Kept the small `BAAI/bge-small-en` (384 dims). This is the root of the one remaining eval failure (the `/services` page never ranks in the top 20). | A larger embedder (bge-large, or a hosted embedding API) and/or hybrid keyword + vector search. |

**The lesson:** the constraint was money, not knowledge. The cheapest path cost more
engineering (an embedder swap, a host pivot, memory measurements), but it taught how
runtimes, memory limits and free tiers actually behave, and the result runs for $0/month.

---

## 2. Architecture: before and after

**Before (March 2026)**
```
API startup ──▶ if index empty: Selenium + Chrome scrapes 14 pages ──(errors → "")──▶ embed (torch) ──▶ Pinecone
/chat ──▶ embed question (torch) ──▶ top 3 ──▶ prompt with hard-coded facts ──▶ Groq llama-3.3-70b (temp 0.7)
Not deployed. Windows-only dev script. No eval.
```

**After (November 2026)**
```
Laptop: python build_index.py ──▶ requests (fails loudly) ──▶ title-prefixed chunks + verified facts
        ──▶ fastembed bge-small-en ──▶ Pinecone (full replace, 388 vectors)
Render (Docker, 512 MB): /chat ──▶ fastembed question ──▶ top 5 ──▶ prompt ──▶ Groq gpt-oss-120b (temp 0)
Vercel: Next.js page + widget + DEMO badge ──▶ Render (CORS locked to the Vercel origin)
16-case eval in the repo; results in reports/eval.json.
```

**Design choices and the alternatives we rejected**

| Choice | Alternatives considered | Why this one |
|---|---|---|
| Index built by a separate script | Keep scraping at API startup | Serving and offline jobs have different failure modes; startup scraping hid failures and slowed boot. |
| `requests` + BeautifulSoup | Keep Selenium | Site is server-rendered; text was identical (1090 vs 1088 chars) and no Chrome needed on the server. |
| fastembed (ONNX) | (a) Render with the torch image as-is (397 MB idle of 512: too tight); (b) Pinecone hosted embeddings (would change the model = re-index, more rebuild than revive) | Same model and vectors, so no re-index, and 277 MB peak. One new dependency, approved first. |
| Render | HF Spaces (became paid), Gradio on ZeroGPU (hack, GPU quota) | Free, Docker, 512 MB is enough after the fastembed swap. |
| gpt-oss-120b | qwen3.8-27b | 14/16 vs 10/16 on the identical pipeline. qwen was faster (1.3 s vs 1.9 s median) but less accurate. |
| One facts paragraph | Six one-line facts (original) | One-liners that mostly say "Stackular" matched every query and pushed real content out of the top 3. |
| Page title in front of each chunk | bge query-instruction prefix | Title headers moved the home page's services section to rank 2; the query prefix did not help, so it was left out (simpler). |
| Substring-graded eval | LLM-as-judge | Free, deterministic, every answer saved for eyeballing. Coarse, but enough for 16 cases. |

---

## 3. The process, step by step

Each step was one commit; Ved committed and pushed every one himself, and `main` stayed
working after each.

### Phase 0-1: intake and read-only audit
- Mapped the repo and git history (4 commits, all 25 March 2026).
- Installed into a scratch venv and tried to import the app: **crashed** (`ModuleNotFoundError: langchain_openai`).
- Checked all 14 source URLs still return 200; found the site is server-rendered.
- Found a fourth office (San José, Costa Rica) and Chicago missing from the hard-coded facts; "founded 2015" appears nowhere on the site.
- Found the email/phone live only in `<footer>`, which the scraper deletes.
- Measured the torch embedder: 626 MB peak, 24 s load.
- Scanned git history for leaked keys: none.

### Phase 2: baseline
- Created the Pinecone index and built it with the **original** scraper (392 chunks).
- Wrote 16 eval cases (greeting, founders, offices, email, phone, services, openings, links, industries, values, a case study, two off-topic).
- Original code: **0/16** (Groq 404). Same code with only the model swapped: gpt-oss-120b 14/16, qwen 10/16.
- Read the answers instead of trusting the score: phone was actually right (grader bug), email passed by luck, locations failed on stale prompt text, services failed on retrieval.

### Step 1: hotfix (14/16)
Model swap via `GROQ_MODEL`, dead import removed, index auto-created, widget checks `res.ok`.

### Step 2: indexing that can't fail silently (15/16)
`requests` scraper that raises on failure, `build_index.py`, verified facts paragraph, title-prefixed chunks, bytes-to-BeautifulSoup encoding fix, temperature 0, pinned deps, `.python-version`, eval moved into the repo, `note.txt` deleted.

### Step 3: dev experience
Cross-OS `dev:all`, `.env.example` files, lint error fixed, `turbopack.root` set. Browser-tested the happy path and the API-down fallback.

### Step 4: deployment (and the pivot)
Dockerfile, CORS from `ALLOWED_ORIGINS`, DEMO badge. Planned for HF Spaces; at the dashboard,
Docker turned out to be paid → switched to Render + fastembed (step 4b). Verified in a
container capped at `--memory=512m` before Ved deployed.

### Step 5: documentation
README, learning log, and this file. Live eval over HTTP: **15/16**, median 2.8 s warm.

---

## 4. Mistakes made during the rebuild (not just in the original)

| Mistake | How it showed up | Fix / lesson |
|---|---|---|
| Planned on HF Spaces without checking the account's current free options | Docker was "Paid" at the moment of deploying | Check free tiers live before planning around them; they change. |
| Introduced mojibake when replacing Selenium | "weâ€™re" in chunks: no charset header, so `requests` guessed ISO-8859-1 | Pass `resp.content` (bytes) to BeautifulSoup; spot-check scraped text, don't just count it. |
| Eval grader too strict | Correct phone `888‑278‑8667` (non-breaking hyphens) failed | Normalise unicode dashes/spaces; always read failing answers before believing a score. |
| `load_dotenv()` loaded nothing in the scratch eval | It looks next to the *calling script*, not the working dir | Pass the path explicitly when running from elsewhere. |
| Partial edits when a hook blocked some changes | `main.py` briefly used `ServerlessSpec` before its import landed | After any batch of edits, grep/diff to confirm every piece applied. |
| Real API keys pasted into chat | Convenient, but they are now in a transcript | Put keys straight into `.env`; rotate anything that was pasted. |

---

## 5. Commands we used to verify things (reusable cookbook)

```bash
# Does it install and import from requirements alone? (catches missing deps)
python3.12 -m venv /tmp/v && /tmp/v/bin/pip install -r stackular-api/requirements.txt
cd stackular-api && /tmp/v/bin/python -c "import rag"
```
```bash
# Is the site server-rendered? (if the text is in the raw HTML, you don't need Selenium)
curl -sL -A 'Mozilla/5.0' https://www.stackular.com/about | grep -c "Jason Storch"
```
```bash
# Run the real server and hit it
python -m uvicorn main:app --port 8765
curl -s localhost:8765/health
curl -s -X POST localhost:8765/chat -H 'Content-Type: application/json' -d '{"question":"Who founded Stackular?"}'
```
```bash
# CORS: allowed origin gets the header, others get 400
curl -s -D - -o /dev/null -X OPTIONS https://stackular-chatbot.onrender.com/chat \
  -H 'Origin: https://stackular-chatbot.vercel.app' -H 'Access-Control-Request-Method: POST' | grep -i allow-origin
```
```bash
# Will it fit the free tier? Run the image with the same memory cap and burst it
docker build -t stackular-api-test stackular-api
docker run -d --name sapi --memory=512m -p 10000:10000 -e PORT=10000 --env-file stackular-api/.env stackular-api-test
for i in 1 2 3 4 5; do curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" -X POST localhost:10000/chat \
  -H 'Content-Type: application/json' -d '{"question":"Where are your offices?"}' & done; wait
docker stats --no-stream sapi
docker inspect sapi --format 'OOMKilled={{.State.OOMKilled}}'
```
```bash
# Rebuild the index and run the eval
cd stackular-api && python build_index.py && python -m eval.run_eval
```
```bash
# Check which models a Groq key can use (when a model 404s)
python -c "import os;from dotenv import load_dotenv;load_dotenv();from groq import Groq;print([m.id for m in Groq(api_key=os.getenv('GROQ_API_KEY')).models.list().data])"
```
```bash
# Dry-run staging before every commit (no .env, datasets or junk)
git add -n <paths> && git status --short
```

Other one-off checks done in Python during the session: cosine similarity between
sentence-transformers and fastembed vectors (1.00000), peak RSS of each embedder
(`resource.getrusage`), the top-k chunks for a failing question, and a scan of all 388
chunks for mojibake (0 found).

---

## 6. What I'd do differently next time

1. **Write the eval on day one**, even 10 cases; it would have caught the stale facts in March.
2. **Check every external dependency live** (model list, free tiers) before planning.
3. **Design for the deployment target from the start:** a 512 MB box rules out torch, so pick an ONNX/hosted embedder up front.
4. **Keep offline jobs out of the web server.**
5. **Never let a failure turn into an empty string.**
6. **Read the answers, not just the score.**
