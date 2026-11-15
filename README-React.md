# Campus — source-grounded university assistant

A responsive React/TypeScript chat interface with real event-driven document activity, streamed answers, numbered evidence citations, and a FastAPI/LangChain integration example.

The production frontend connects to the AWS-hosted LangChain/Gemini agent and the supplied DSU document index. [AWS deployment and connection details](docs/AWS-DEPLOYMENT.md) describe the live endpoint, source limits, cancellation and request budgets. This is a public-document assistant; student login/private-record access is not implemented. Test fixtures remain isolated from the deployed application.

## Run the frontend

Use Node.js 22 (see `.nvmrc` and `package.json`).

```bash
npm ci
npm run dev
```

`npm run build` checks TypeScript and produces `dist/`. The app is a static frontend; Python runs separately.

To connect your actual API, copy `.env.example` to `.env.local` and set:

```dotenv
VITE_RAG_STREAM_URL=http://localhost:8000/api/chat/stream
```

Alternatively use the included development proxy:

```dotenv
VITE_RAG_STREAM_URL=/api/chat/stream
RAG_DEV_API_ORIGIN=http://localhost:8000
```

Restart Vite after changing environment variables. `RAG_DEV_API_ORIGIN` applies only to the local development server. In production, use an HTTPS API URL or configure your own same-origin reverse proxy. Set `VITE_RAG_STREAM_URL` **before building**, then rebuild and redeploy the frontend. Provider keys belong exclusively on the Python server; all `VITE_*` values are public.

The frontend sets `credentials: omit` by default for the future cross-origin AWS API. Set `VITE_RAG_CREDENTIALS=include` only for a real cookie authentication setup. For bearer-token login, provide the transport's async `headers(signal)` callback in `src/hooks/use-rag-chat.ts`, obtaining a short-lived token from your real authentication session. No login screen or credentials are invented in this project.

## Deploy on Vercel

Vercel serves the static React frontend. The planned FastAPI/LangChain pipeline will run separately on AWS. There are no Vercel Python functions or RAG proxy functions in this configuration. See [Vercel + AWS setup](docs/VERCEL-AWS.md) for exact settings, authentication, CORS and streaming checks.

1. Import this repository in Vercel with root directory `./`, framework Vite and Node 22.x. The committed configuration sets install `npm ci`, build `npm run build` and output `dist`.
2. Leave `VITE_RAG_STREAM_URL` unset to use the committed public AWS endpoint in `src/config/deployment.json`. Set it to an explicitly blank value to disconnect the frontend.
3. To override the service, set `VITE_RAG_STREAM_URL` to its full HTTPS `/api/chat/stream` URL and redeploy. Production builds reject localhost, HTTP and relative API paths.
4. Keep `VITE_RAG_CREDENTIALS=omit` for bearer authentication, or explicitly configure `include` for cookies.
5. The production AWS entrypoint uses the real public-document agent, Secrets Manager and DynamoDB request limits. For a private authenticated service, implement identity verification/document ACLs before adding private records. The generic factory example remains available separately.

Vercel preview URLs must be explicitly allowed by the AWS API before they can access it. The browser streams directly from AWS, so RAG generation does not pass through a Vercel function. AWS application/load-balancer timeouts and the frontend idle timeout still apply. Changing Vite environment values requires a rebuild/redeployment.

## What the interface does

- Creates an assistant turn when the Send button is clicked or Enter submits a question. Send is disabled for blank prompts and becomes Stop while generating. Shift+Enter adds a newline and IME composition does not submit accidentally.
- Opens an accessible activity timeline while connecting/processing. Only received backend events create retrieval, document-reading or summary steps. Spinners indicate actual active requests.
- Updates document discovery, reading and completion with authoritative document IDs, titles, excerpts and optional locations. Expanding a step exposes its detail and evidence.
- Streams validated answer blocks and attaches their registered, numbered citations. Hover previews evidence; clicking opens the source inspector. The inspector stays synchronized while events arrive.
- Collapses the timeline after successful completion. Completed steps remain available to reopen. Errors, unexpected EOF, invalid events and cancellations preserve received text and mark unfinished activity interrupted.
- Lists the evidence actually cited in a collapsible Sources section. Repeated source IDs are deduplicated, while separate pages/chunks retain separate references. Missing URLs, titles or page metadata are never guessed.
- Explicitly reports a backend `no_evidence` result. Connection failures say that no supporting sources were received, without claiming a search was performed.
- Stop generating or Escape cancels the active request. A new submission in the same conversation cancels its predecessor; different conversations remain isolated. Unmount cleans up streams, timers and listeners.

The existing headerless layout, sidebar toggle, Google Sans, Remotion SVG logo/educational artwork, reduced-motion handling, and appearance controls remain. Interface icons use clean Lucide SVGs with consistent strokes and no 3D effects. Controls use borderless raised surfaces. Keyboard focus still receives a subtle surface lift without adding an outline or ring. The welcome state mounts no message scroller and fits the viewport; chat messages scroll after submission. Conversations and drafts are in memory and reset on reload. Only completed exchanges are sent as history; history is never treated as document evidence.

## Official shadcn components

Verified against the current official [AI Elements documentation](https://ui.shadcn.com/docs/ai-elements) on 14 November 2026. This version documents composition patterns rather than separate exports named `ReasoningTrigger`, `ChainOfThought`, `Response` or `SourcesTrigger`. The implementation follows the current APIs instead of creating imitation aliases.

| Requested function | Current documented implementation used |
| --- | --- |
| Reasoning and collapsible chain of thought | `Trace`, `TraceCollapsible`, `TraceCollapsibleTrigger`, `TraceCollapsibleContent`, `TraceLine`, `TraceIcon`, `TraceTitle`, `TraceDescription` |
| Sources and expandable evidence | The official Sources composition using the same Trace primitives |
| Inline numbered citations | `HoverCard`, `HoverCardTrigger`, `HoverCardContent`, `Button` |
| Streamed answer / Response | `Streamdown` inside `MessageContent`, as documented in Message |
| Active loader | Official `Spinner` |
| Fenced code | `CodeBlock` and its documented subcomponents |
| Prompt, chat, navigation, inspector | `InputGroup`, `Message`, `MessageScroller`, `Bubble`, `Sidebar`, `Sheet`, `Item`, `Badge` |

UI primitives are fetched from the official `base-nova` shadcn registry. `shadcn-provenance.json` records origins and SHA-256 hashes, and `scripts/fetch-shadcn.py` reproduces registry installation with only import/icon alias adaptations. The official CLI was attempted for the additional Spinner/CodeBlock components; its registry request failed in this environment's proxy, so the exact official registry files and dependencies were fetched directly. On a regular network the supported CLI is:

```bash
npx shadcn@latest add trace message message-scroller bubble input-group hover-card spinner code-block sidebar sheet
```

Application components in `src/components/chat/` assemble these official building blocks; they do not implement substitute UI primitives. Custom Remotion SVG artwork remains decorative, as requested. Backend summaries are user-facing activity reports, never hidden model chain-of-thought.

## Connect FastAPI + LangChain

Use Python 3.11+ (verified with 3.12). The example uses FastAPI's native `EventSourceResponse` and LangChain's documented v2 `astream_events`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

On Windows activate with `.venv\Scripts\activate` instead. The supplied example environment files are references; Python does not automatically load them.

1. Ingest your real university documents with stable metadata for every retrieved chunk:

   | Field | Requirement |
   | --- | --- |
   | `source_id` | Stable evidence reference ID |
   | `document_id` | Stable original document ID |
   | `chunk_id` | Stable chunk ID within that document |
   | `title` | Original title, only if known |
   | `url` | Actual accessible document/viewer URL, only if known |
   | `page_start`, `page_end` | Actual one-based page numbers, only if known |
   | `section` | Actual section label, only if known |
   | `Document.page_content` | Exact supporting passage |

   The server assigns citation numbers within each response. It does not derive source metadata from model-generated names. Do not pass a zero-based loader `page` field as a one-based `page_start` without normalizing it during ingestion.

2. Implement your server-side `my_university.auth.authorize_request(request)` hook. Verify your real session/token and return the authenticated principal, or raise `HTTPException(401/403)`. Implement `my_university.rag.build_service(principal)` using that identity to obtain an access-filtered `BaseRetriever` and your actual LangChain chat model:

   ```python
   from backend.example_factory import wire_service

   def build_service(principal):
       retriever = get_access_filtered_retriever(principal)  # your implementation
       model = get_configured_chat_model()                 # your implementation
       return wire_service(retriever, model)
   ```

   These two functions are integration points, not bundled services. Async factories and authorization hooks are supported. Provider/vector database configuration stays on the server.

3. Export your actual module paths and exact allowed frontend origins, then start FastAPI:

   ```bash
   export RAG_FACTORY=my_university.rag:build_service
   export RAG_AUTH_FACTORY=my_university.auth:authorize_request
   export RAG_ALLOWED_ORIGINS=http://localhost:5173,https://campus-university-assistant-ui.roanwand4.chatgpt.site
   uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```

   Substitute the frontend's actual local origin if its port differs. Use your shell's equivalent environment syntax on Windows. An unconfigured server responds with HTTP 503 before opening a stream. Cross-origin cookie authentication needs the appropriate HTTPS cookie configuration for your real deployment. CORS origins are explicit; wildcard credential access is rejected.

4. Set the frontend endpoint as described above. For production, host Python separately and preserve streaming through its reverse proxy. Do not buffer SSE responses. FastAPI supplies heartbeat comments, `Cache-Control: no-cache` and `X-Accel-Buffering: no`. The request is a POST with `Accept: text/event-stream`; there are no automatic retries that could duplicate generation.

5. Test a real question and inspect the timeline, final citations and excerpts. Confirm document access controls also apply to original-document links. The static Site hosts the frontend only; uploading the Python files does not start a Python process there.

### Grounding behavior of the example

The included LangChain chain produces incremental structured claims. The adapter checks each claim against registered source IDs before emitting `answer_delta`. The default verifier permits **exact contiguous quotations from retrieved excerpts only**. Unknown IDs, altered citation assignments, rewritten streamed text and unverified claims end with an error, preserving previously verified passages.

This conservative default avoids asserting that arbitrary paraphrases are proven by attaching a citation. To support natural-language synthesis, supply a real, source-aware entailment verifier through `RagService(verify_claim=...)` and an appropriate structured answer chain. Do not replace it with an unconditional success function. Retrieval relevance, university policy correctness, model/provider configuration and semantic verification of paraphrases remain responsibilities of the real RAG service.

Read [docs/STREAMING-CONTRACT.md](docs/STREAMING-CONTRACT.md) for the complete wire contract, event payloads, lifecycle rules and actual LangChain mapping. `backend/protocol.py` and `src/lib/rag/protocol.ts` enforce the same contract. The implementation never forwards raw reasoning tokens.

## Verification

```bash
pip install -r backend/requirements-test.txt
python -m pytest backend/tests -q
npm test
npm run build
```

The Python suite runs real LangChain `BaseRetriever`/Runnable event streams and FastAPI's native SSE serializer using labelled test documents. It writes `tests/backend-wire.generated.json`; a TypeScript test then validates and reduces those same wire events. Additional tests cover sequence/run isolation, duplicate and unknown source IDs, source conflicts and page references, malformed streams, UTF-8 fragmentation, heartbeat handling, abort/timeouts, rapid requests, partial preservation, unsafe URLs, and rendering of official compositions. The fixtures perform no provider calls and are never enabled in the production app.

## Main files

| File | Purpose |
| --- | --- |
| `src/lib/rag/protocol.ts` | Runtime-validated event, evidence and request types |
| `src/lib/rag/transport.ts` | POST SSE parsing, authentication hook, timeout and cleanup |
| `src/lib/rag/state.ts` | Pure activity/answer/source reducer and invariants |
| `src/lib/rag/session.ts` | Conversation state, cancellation, isolation and history |
| `src/hooks/use-rag-chat.ts` | React subscription and real endpoint configuration |
| `src/components/chat/AssistantTurn.tsx` | Official reasoning, citations, Markdown and Sources assemblies |
| `src/components/chat/SourceInspector.tsx` | Evidence inspector built from official Sheet/Item components |
| `backend/main.py` | Native FastAPI SSE endpoint, auth/service hooks and public errors |
| `backend/rag.py` | Real LangChain callback/event mapping and claim validation |
| `backend/example_factory.py` | Retriever/model wiring reference |
| `backend/protocol.py` | Authoritative Python wire models |
| `docs/STREAMING-CONTRACT.md` | Exact integration contract and constraints |
| `src/components/education/` | Existing Remotion educational artwork |
| `shadcn-provenance.json` | Official component origins and installed hashes |
