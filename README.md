# Campus University RAG Assistant

## React frontend on Vercel, LangChain RAG backend on AWS

The root React/Vite application connects to the Python LangChain service on AWS Lambda through a real HTTPS SSE stream. See [the deployed AWS service and operating guide](docs/AWS-DEPLOYMENT.md). The agent searches 465 supplied DSU passages using Gemini embeddings, BM25, reciprocal-rank fusion and reranking, then checks formatted answer sections against retrieved evidence before displaying them with citations.

Frontend: https://campus-university-rag-assistant-dqa.vercel.app/

Use Node.js 22, root directory `./`, install `npm ci`, build `npm run build`, output `dist`. The public AWS endpoint is in `src/config/deployment.json`; an optional `VITE_RAG_STREAM_URL` overrides it. Model credentials and all retrieval execution stay on AWS. This is a public-document assistant with shared usage limits, not an authenticated student-record system.

The production API entrypoint is `backend.aws_app:app`, and the curated system prompt is `backend/system_prompt.txt`. Existing FastAPI protocol examples are preserved. The separate Streamlit application below is not part of the Vercel deployment.

The React/AWS agent has [isolated active-conversation memory](docs/SESSION-MEMORY.md): typed preferences and bounded recent turns in DynamoDB, correction/forget support, stale-request protection and a 24-hour idle expiry. Tab refreshes restore the conversation and citations. Official [Flaticon navigation icons and attribution](FLATICON-LICENSE.md) are included locally without a runtime CDN dependency.

The working **Streamlit + LangChain + Gemini + local FAISS agent** is in [`streamlit-agent/`](streamlit-agent/README.md). It uses the supplied **584 DSU embeddings** and includes an isolated fictional dataset for the assignment's dated-policy and security tests.

The existing React interface and FastAPI integration example are preserved. They remain a separate application; the Streamlit agent is the complete application delivered by this update.

## Run the Streamlit agent

Use Python 3.12:

```bash
cd streamlit-agent
python -m venv .venv
# Activate .venv for your operating system
python -m pip install -r requirements.txt
# Copy .env.example to .env and set GEMINI_API_KEY locally
streamlit run streamlit_app.py
```

For Streamlit Community Cloud, select **`streamlit-agent/streamlit_app.py`**, Python **3.12**, and add `GEMINI_API_KEY` to app secrets. The configurable chat model defaults to `gemini-3.5-flash-lite`. Provider keys are not committed.

## Review the implementation and proof

- [Complete README and assignment checklist](streamlit-agent/README.md)
- [Final 20-question answer/citation results](streamlit-agent/evidence/test_results_20.csv) — **20/20 automatic checks passed**
- [Live checks against the supplied DSU embeddings](streamlit-agent/evidence/dsu_live_checks.csv) — **6/6 passed**
- [Local tests](streamlit-agent/evidence/offline_tests.txt) — **20 passed**
- [Real FAISS vector integrity check](streamlit-agent/evidence/bundle_integrity.json)
- [Retrieval experiments and honest failures](streamlit-agent/docs/retrieval-findings.md)
- [Three-page project report](streamlit-agent/docs/project-report.pdf)
- [3-minute-40-second recorded-evidence walkthrough](streamlit-agent/docs/demo-walkthrough.mp4)
- [Standalone LMS ZIP, below 5 MB](deliverables/Campus-Evidence-Streamlit-Agent.zip)

PASS means the recorded real answer met frozen expected-fact, source and quotation checks. It does not prove universal correctness or semantic entailment. Low-k and semantic-only retrieval failures, initial failed responses and provider limits are retained in the evidence.

The assignment specifies Chroma; this implementation uses **FAISS as requested**. Real DSU snapshots do not provide authenticated previous policy versions. A separate fictional Noor Skills Institute dataset demonstrates those assignment requirements without inventing DSU history.

For the preserved React application, Vercel configuration and backend protocol example, see [the original interface README](README-React.md). That earlier frontend is not silently wired to this new Streamlit application.
