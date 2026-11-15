"""Run the 16-case eval against the live index and Groq, and write reports/eval.json.

Usage (from stackular-api/):  python -m eval.run_eval
Each case is graded with case-insensitive substring rules: must_all, must_any, must_any2, must_not.
Answers are saved in the report so every pass/fail can be checked by eye.
"""
import json
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from sentence_transformers import SentenceTransformer  # noqa: E402
from rag import EMBED_MODEL, GROQ_MODEL, get_index, rag_answer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# Models write "888‑278‑8667" with non-breaking hyphens; normalise dashes and spaces first.
DASHES = {0x2010: "-", 0x2011: "-", 0x2012: "-", 0x2013: "-", 0x2014: "-", 0x00A0: " ", 0x202F: " "}


def check(case, answer):
    a = answer.lower().translate(DASHES)
    fails = [f"missing '{w}'" for w in case.get("must_all", []) if w.lower() not in a]
    for key in ("must_any", "must_any2"):
        opts = case.get(key)
        if opts and not any(w.lower() in a for w in opts):
            fails.append(f"none of {opts}")
    fails += [f"contains '{w}'" for w in case.get("must_not", []) if w.lower() in a]
    return fails


def main():
    cases = json.loads((ROOT / "eval" / "cases.json").read_text())
    embedder = SentenceTransformer(EMBED_MODEL)
    index = get_index()

    results = []
    for case in cases:
        start = time.time()
        answer = rag_answer(case["q"], index, embedder)
        latency = round(time.time() - start, 2)
        fails = check(case, answer)
        results.append({"id": case["id"], "q": case["q"], "pass": not fails,
                        "fails": fails, "latency_s": latency, "answer": answer})
        print(f"{'PASS' if not fails else 'FAIL'} {case['id']:<18} {latency:5.2f}s {fails}")
        time.sleep(6)  # stay under Groq free-tier tokens-per-minute

    lat = sorted(r["latency_s"] for r in results)
    summary = {"model": GROQ_MODEL, "passed": sum(r["pass"] for r in results), "total": len(results),
               "median_latency_s": lat[len(lat) // 2], "max_latency_s": lat[-1],
               "date": time.strftime("%Y-%m-%d")}
    print(summary)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "eval.json").write_text(json.dumps({"summary": summary, "results": results}, indent=2))


if __name__ == "__main__":
    main()
