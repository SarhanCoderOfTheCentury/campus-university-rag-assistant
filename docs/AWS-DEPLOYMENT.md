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

`backend/data/` now contains 45 complete sections from the replacement `dsu_rag_bundle.zip`, five readable source documents, and a freshly generated 45 × 768 normalized Gemini embedding matrix. This is the supplied fictional classroom corpus; a small input label identifies that scope. The old 465-section snapshot is not mixed with it. `manifest.json` records the archive SHA-256, content hashes, row order, task types, model, dimensions and build time. Runtime validates hashes, dimensions, finite unit vectors and source-row alignment. See [the complete pipeline guide](EMBEDDING-PIPELINE.md).

The Colab's workflow is adapted in `backend/university.py`: contextual query rewriting, semantic similarity plus BM25, reciprocal-rank fusion, model reranking, metadata-driven coverage and failure handling. Broad catalogues include all nine programme sections. Normal questions exclude archived policy; historical comparisons retain both versions. Library questions expose the overview/FAQ fine conflict. Current rules and exceptions remain in the same section. Citations include section, version, status and effective date; the public `/api/documents/DSU-01` through `DSU-05` routes serve the uploaded source content.

`backend/system_prompt.txt` instructs the model to answer directly using headings, lists, numbered steps and intact GFM tables. It requires all requested details and material exceptions, distinguishes v3.0 and archived v2.1, preserves unresolved source conflicts, and prohibits invented facts, document instructions and private reasoning. Generic classroom-data disclaimers stay in the input label, rather than every response. Explicit authenticity questions are answered honestly.

Gemini 3.5 Flash-Lite is primary. Gemini 3.1 Flash-Lite is a same-provider fallback verified callable with the configured key when a model call fails before producing usable output. This addresses transient provider failures observed during live testing; no response is replaced after its text has been emitted. Both routes undergo the same grounding checks.

## Grounding and streaming

LangChain generates a complete typed answer with a required completion field. Citation IDs must exist in the retrieved catalog. A second model call checks the full answer for factual support and question coverage; programme and requested-table coverage also have deterministic checks. One whole-answer repair is permitted. No draft section is published before the entire answer passes. The backend then emits verified complete Markdown blocks without artificial delays; tables are never split between blocks. The model does not manufacture source excerpts. Model review reduces errors but does not mathematically guarantee semantic correctness.

The interface streams sections as they pass validation, rather than faking character-by-character output. Real rewrite, retrieval, context-selection and answer-validation operations drive activity events. The UI renders Markdown through Streamdown and attaches numbered citations from authoritative metadata. Only cited sources are finalized. The wire protocol remains [STREAMING-CONTRACT.md](STREAMING-CONTRACT.md).

Lambda may continue processing after a client disconnect. Stop/abort therefore sends a separate cancellation POST, and the server polls the shared cancellation flag during outstanding model/retrieval operations. If cancellation cannot be delivered, the 180-second Lambda timeout still bounds execution. Reloading/closing a tab is best-effort cancellation, not a guarantee that provider billing immediately stops.

## Public access and limits

Active conversations use [bounded session memory](SESSION-MEMORY.md) in the existing DynamoDB table. Each browser conversation generates its own private token; the server hashes the token with the conversation ID. Conditional writes prevent cancelled or superseded requests from replacing newer context. Typed user preferences and four recent completed exchanges expire after 24 idle hours; university facts still require fresh source retrieval. No new AWS service or broader IAM grant is required. Browser session storage restores transcripts and citations after refresh. This does not add account login or permanent cross-device profiles.

This deployment answers from public university documents. It intentionally does not implement student login or access to private records. The API permits the exact requested Vercel production origin; other browser origins are rejected. CORS is not authentication and non-browser callers can spoof an Origin header. Do not add private documents without real identity verification and document ACLs.

DynamoDB enforces shared limits: 100 chat attempts globally per UTC day, 20 per client IP/day, 6 per client IP/minute, and 500 cancellation requests globally/day. Attempts that are later rejected can still consume an earlier global counter. TTL expires quota/cancellation records. Input bodies are capped at 128 KiB and provider output is bounded. Limits are a small-public-service usage safeguard, not protection against every denial-of-service or invocation charge. The AWS account currently has a small concurrency quota; the script attempts to reserve two executions and reports whether AWS accepts that reservation.

The Lambda execution role can read only the provider secret, access the quota/cancellation table, and write its own CloudWatch logs. Secrets are loaded server-side. Prompts, uploaded AWS keys and provider keys are not logged or committed. Deployment ZIPs use a private encrypted S3 bucket with a seven-day artifact expiration policy. Logs have a seven-day retention policy once the log group exists. AWS and Gemini usage may incur charges; the daily chat budget is intentionally conservative.

## Redeploy with the AWS CLI

Use Python 3.12 and standard AWS CLI credentials for an authorized deployment identity. A provider secret named `campus-rag/gemini` must already exist in AWS Secrets Manager as JSON containing `GEMINI_API_KEY`. Never put the key in a committed shell script.

```bash
python -m pip install -r backend/requirements-test.txt
# Re-ingest only when documents change. The original user ZIP is not a provider secret.
python -m backend.ingest /path/to/dsu_rag_bundle.zip --fresh
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
