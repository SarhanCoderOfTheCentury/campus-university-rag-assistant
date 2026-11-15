# Campus RAG deployment

Recorded checks: [live-validation.json](live-validation.json) and [the completed Vercel answer screenshot](screenshots/live-rag.jpg). These include real AWS fee/missing-information responses, the Vercel programme-list answer, citation inspection, CORS and cancellation checks. Earlier provider/validation failures were corrected during development; rate limits and provider outages remain possible and are handled without invented answers.

## Services

- Frontend: https://campus-university-rag-assistant-dqa.vercel.app/
- AWS health: https://vrn7rkajt4fke7okwkdrjj5jpq0zhfws.lambda-url.us-east-1.on.aws/health
- SSE API: https://vrn7rkajt4fke7okwkdrjj5jpq0zhfws.lambda-url.us-east-1.on.aws/api/chat/stream
- Cancellation: the same origin, `/api/chat/cancel`.

The React application connects directly to the HTTPS Lambda Function URL. Vercel serves static assets and performs no model execution. Both Lambda Web Adapter and the Function URL use response-streaming mode. There is no extra domain to configure and no always-on RAG VM. Existing EC2 workloads are untouched.

`src/config/deployment.json` contains only a public endpoint, allowing the existing Git-linked Vercel deployment to connect without an additional Vercel secret. `VITE_RAG_STREAM_URL` overrides it; an explicitly blank value disconnects it. Builds validate either endpoint. Provider keys and AWS credentials never belong in frontend variables.

## Dataset and Colab adaptation

`backend/data/` contains 465 normalized passages from the uploaded five-document corpus, original extracted supporting records, five readable curated documents, the policy-conflict record, and a 768-dimensional normalized Gemini embedding matrix. `manifest.json` records the original archive SHA-256, indexed-record hash, vector hash and embedding model. Runtime validates both file hashes and vector dimensions. Index ingestion checkpoints embedding batches and observes actual provider rate-limit waits.

The Colab's workflow is adapted in `backend/university.py`: query rewriting with conversation references, semantic similarity plus BM25, reciprocal-rank fusion, model reranking, bounded multi-document context, and failure handling. Broad programme lists prefer individually sourced curated programme pages over an inconsistent broad FAQ snapshot. Current-policy retrieval excludes historical-only records. Ambiguous flattened fee rows are excluded; numeric fee rows must have verified source alignment.

`backend/system_prompt.txt` instructs the model to answer directly with short paragraphs, headings, bullets and numbered steps. It prohibits invented facts, unsupported currentness, instructions embedded in documents and private model reasoning. It explains the unresolved application-fee conflict and absence of authenticated older policy versions. Source capture dates are unknown; the system does not claim live university verification.

Gemini 3.5 Flash-Lite is primary. Gemini 3.1 Flash-Lite is a same-provider fallback verified callable with the configured key when a model call fails before producing usable output. This addresses transient provider failures observed during live testing; no response is replaced after its text has been emitted. Both routes undergo the same grounding checks.

## Grounding and streaming

LangChain generates structured answer sections progressively. Once a section is fully parsed, its citation IDs must exist in the retrieved catalog. The backend attaches the exact original excerpts directly; the model does not generate quotation strings. A second model call reviews all claims against the full cited passages. One bounded repair is permitted before repeating validation. A failed section never reaches the UI. This reduces unsupported claims but is not a mathematical guarantee of semantic correctness; students must inspect official sources for consequential decisions.

The interface streams sections as they pass validation, rather than faking character-by-character output. Real rewrite, retrieval, context-selection and answer-validation operations drive activity events. The UI renders Markdown through Streamdown and attaches numbered citations from authoritative metadata. Only cited sources are finalized. The wire protocol remains [STREAMING-CONTRACT.md](STREAMING-CONTRACT.md).

Lambda may continue processing after a client disconnect. Stop/abort therefore sends a separate cancellation POST, and the server polls the shared cancellation flag during outstanding model/retrieval operations. If cancellation cannot be delivered, the 180-second Lambda timeout still bounds execution. Reloading/closing a tab is best-effort cancellation, not a guarantee that provider billing immediately stops.

## Public access and limits

This deployment answers from public university documents. It intentionally does not implement student login or access to private records. The API permits the exact requested Vercel production origin; other browser origins are rejected. CORS is not authentication and non-browser callers can spoof an Origin header. Do not add private documents without real identity verification and document ACLs.

DynamoDB enforces shared limits: 100 chat attempts globally per UTC day, 20 per client IP/day, 6 per client IP/minute, and 500 cancellation requests globally/day. Attempts that are later rejected can still consume an earlier global counter. TTL expires quota/cancellation records. Input bodies are capped at 128 KiB and provider output is bounded. Limits are a small-public-service usage safeguard, not protection against every denial-of-service or invocation charge. The AWS account currently has a small concurrency quota; the script attempts to reserve two executions and reports whether AWS accepts that reservation.

The Lambda execution role can read only the provider secret, access the quota/cancellation table, and write its own CloudWatch logs. Secrets are loaded server-side. Prompts, uploaded AWS keys and provider keys are not logged or committed. Deployment ZIPs use a private encrypted S3 bucket with a seven-day artifact expiration policy. Logs have a seven-day retention policy once the log group exists. AWS and Gemini usage may incur charges; the daily chat budget is intentionally conservative.

## Redeploy with the AWS CLI

Use Python 3.12 and standard AWS CLI credentials for an authorized deployment identity. A provider secret named `campus-rag/gemini` must already exist in AWS Secrets Manager as JSON containing `GEMINI_API_KEY`. Never put the key in a committed shell script.

```bash
python -m pip install -r backend/requirements-test.txt
# Re-ingest only when documents change. The original user ZIP is not a provider secret.
python -m backend.ingest /path/to/dsu_five_document_rag.zip
python -m pytest -q
python backend/deploy/package.py
AWS_DEFAULT_REGION=us-east-1 python backend/deploy/deploy.py \
  --zip .deploy/lambda.zip \
  --origin https://campus-university-rag-assistant-dqa.vercel.app
```

The package uses Linux/Python-3.12 wheels and Lambda Adapter layer version 30. It uploads through S3 because dependencies exceed the direct ZIP upload limit. `.deploy/` is ignored by Git and Vercel. The committed `backend/data/` bundle is already built; ingestion is not needed for a code-only deployment. Python runs on AWS, never on Vercel.

After initial provisioning, `python -m backend.deploy.update_code --zip .deploy/lambda.zip` updates code and its release hash without recreating IAM, S3 or DynamoDB resources. Package the current source first. This helper uses the same AWS CLI credentials and existing resources.

For local API work, use AWS credentials that can read this secret/table or configure a separate development account. Set `RAG_ALLOWED_ORIGINS=http://localhost:5173` and launch `uvicorn backend.aws_app:app`. Local calls share configured quota counters, so use separate development resources for sustained testing.

## Verify the connection

```bash
python -m backend.deploy.verify_live \
  https://vrn7rkajt4fke7okwkdrjj5jpq0zhfws.lambda-url.us-east-1.on.aws/api/chat/stream \
  --origin https://campus-university-rag-assistant-dqa.vercel.app \
  --question "What degree programmes does DSU offer?"
```

This runs an actual model request and consumes quota. It checks event types, request identities, sequence continuity, source references and terminal completion. `/health` confirms service/index readiness, not provider availability; a real streamed question is required to test the model connection. Use browser Network tools to confirm the Vercel page POSTs to the AWS host and receives progressive SSE events.

For rollback, revert `src/config/deployment.json` or override the URL in Vercel and redeploy. For an immediate backend stop, set Lambda reserved concurrency to zero using an authorized AWS operator; this blocks new invocations. Rotate the provider secret in Secrets Manager and recycle warm Lambda instances to load a changed key.

Official implementation references: [Lambda Web Adapter](https://github.com/aws/aws-lambda-web-adapter), [AWS response streaming](https://docs.aws.amazon.com/lambda/latest/dg/configuration-response-streaming.html), [LangChain Gemini integration](https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai).
