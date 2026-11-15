# Deploy the frontend on Vercel and connect AWS later

> The AWS connection is now implemented. See [AWS-DEPLOYMENT.md](AWS-DEPLOYMENT.md) for the active endpoint and operating instructions. The staged setup guidance below describes a disconnected/custom deployment. On the current branch, an unset `VITE_RAG_STREAM_URL` uses `src/config/deployment.json`; set an explicitly blank override to disconnect.

## Current boundary

Vercel serves the built React application and its assets. The browser will POST directly to the future AWS HTTPS API and read its Server-Sent Events stream. AWS owns authentication, LangChain execution, document ingestion, embeddings, retrieval, source metadata and provider credentials. No AWS resources or real RAG service are deployed by this preparation.

The existing FastAPI example is in `backend/`; the independent Streamlit application remains in `streamlit-agent/`. Both are excluded from frontend deployment uploads by `.vercelignore`. The obsolete root Vercel Python entrypoint and requirements wrapper were removed; use `backend/requirements.txt` when preparing the AWS service.

## Deploy now

Import `SarhanCoderOfTheCentury/campus-university-rag-assistant` into your Vercel account:

| Setting | Value |
| --- | --- |
| Root directory | `./` (repository root) |
| Framework | Vite |
| Node.js | 22.x |
| Install command | `npm ci` |
| Build command | `npm run build` |
| Output directory | `dist` |
| Production branch | `main` |

Leave `VITE_RAG_STREAM_URL` unset. Do not set a placeholder AWS domain, localhost or `/api/chat/stream` in Production/Preview. Deploying without an endpoint intentionally keeps the existing disconnected state. No LLM key or AWS key is needed on Vercel.

`vercel.json` declares the build, basic response headers, immutable caching for Vite's hashed assets and SPA fallback. `/api` and `/assets` are excluded from the fallback so an unconfigured API or missing asset does not return application HTML. There is no API proxy. SPA fallback only serves the app shell: conversations are still stored in browser memory, with no database, shareable conversation URLs or refresh persistence yet.

## Connect the real AWS API in the next phase

1. Deploy the Python service with a real authenticated RAG implementation and an HTTPS domain. The current example intentionally returns 503 until service and auth factories exist.
2. Keep the request/event format in [STREAMING-CONTRACT.md](STREAMING-CONTRACT.md). Use stable document, chunk, source, conversation, request, message and run IDs. The backend supplies authoritative titles, citations, locations, excerpts and URLs. Do not stream private model reasoning.
3. On AWS, configure `RAG_FACTORY`, `RAG_AUTH_FACTORY` and `RAG_ALLOWED_ORIGINS` as required by `backend/main.py`. `RAG_ALLOWED_ORIGINS` is a comma-separated list of exact browser origins, including scheme and hostname, without paths or trailing slashes. Register the actual Vercel production/custom origin and separately approved preview origins. Never allow all `*.vercel.app` origins. CORS is not authentication; verify users and document permissions on AWS.
4. In Vercel Project Settings → Environment Variables, set `VITE_RAG_STREAM_URL` to the actual complete HTTPS endpoint, normally ending in `/api/chat/stream`. Set Production and Preview separately; use a staging AWS endpoint for previews or leave them disconnected. Redeploy after every change.
5. Select the authentication mode below, then run the acceptance checks against the real deployment.

`src/lib/rag/config.ts` validates the endpoint and credential mode during the build and uses the same logic in the frontend. It rejects HTTP, relative paths, URL credentials and fragments in production. Local development allows loopback HTTP or a relative path backed by the optional Vite dev proxy. A successful build checks syntax, not whether the API is reachable or authorized.

## Authentication

Default `VITE_RAG_CREDENTIALS=omit` means cookies are not sent to AWS. For bearer authentication, connect the transport's existing async `headers(signal)` callback in `src/hooks/use-rag-chat.ts` to the future login session. Return `Authorization: Bearer <short-lived user token>`; the AWS service must validate it and apply document ACLs. Refresh via the actual identity provider. Never set a long-lived bearer token, model key or AWS credential in a `VITE_*` variable.

If the final design uses cross-origin cookies, set `VITE_RAG_CREDENTIALS=include`, redeploy, configure exact CORS origins with `allow_credentials=True`, and set secure cookie attributes appropriate to the domain arrangement. Unrelated-site cookies may be blocked by browser privacy controls; prefer a verified bearer flow or aligned custom domains. Add CSRF protection for cookie-based operations on the server.

The included FastAPI middleware allows POST and the Content-Type/Authorization headers; it handles browser OPTIONS preflights. Ensure any AWS gateway or reverse proxy also passes OPTIONS correctly. CORS error responses should be browser-readable as well.

## Streaming and AWS acceptance criteria

- Accept JSON POSTs and return `Content-Type: text/event-stream`; preserve SSE frames, event names, sequence IDs and request identifiers described in the contract.
- Send real activity and token/source events progressively. Disable response buffering and caching for the streaming path. Use `Cache-Control: no-cache, no-transform`, and preserve native SSE keep-alive comments. Do not cache chat responses in a CDN.
- Keep heartbeat intervals below the shortest browser, proxy and load-balancer idle timeout. The current client aborts after 90 seconds without bytes; the example backend limits a run to 300 seconds. An AWS heartbeat must actually traverse each proxy to reset the browser timeout.
- Verify the selected AWS ingress supports incremental POST streaming for the full run duration. Confirm behavior through the production domain; a local FastAPI test alone cannot validate an AWS gateway or load balancer.
- Propagate browser cancellation/disconnect to retriever/model work. Do not retry generation automatically. Unfinished streams preserve partial answers and display interruption.
- Return 401/403 for authentication failures; return 503 before opening a stream if the service is unavailable. Once streaming starts, emit a typed terminal `error` event on failure or `completed` on success.
- Serve real document URLs or signed viewer links that the browser can open; preserve evidence IDs and access checks. Never expose a private bucket or credentials in citation URLs.

## Verification before considering AWS connected

1. Open the Vercel deployment on desktop and mobile. Confirm all assets load, sidebar/chat navigation works, and the empty state does not scroll.
2. Inspect the browser Network panel. The POST destination must be the intended AWS endpoint; a browser preflight must succeed for the exact frontend origin.
3. Ask a real document-grounded question. Verify activity arrives before the completed answer, inline citations resolve to retrieved evidence, and source links open the correct document/page.
4. Stop generation, switch conversations and submit rapidly. Check cancellation and that events never mix between conversations.
5. Test missing evidence, unauthorized users, unavailable backend and a dropped stream. Confirm no fake answer or successful completion appears.

Local repository checks:

```bash
npm ci
npm test
npm run build
```

The GitHub frontend workflow builds both disconnected and with a non-routable test HTTPS configuration. It does not call that address or claim to validate a live AWS backend. It tests event parsing/state with isolated fixtures. Actual Vercel deployment and AWS connectivity need the account/service configuration above.

## Official references

- [Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite)
- [Vercel project configuration](https://vercel.com/docs/project-configuration/vercel-json)
- [Vite environment variables](https://vite.dev/guide/env-and-mode)
- [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/)

Vite's public variables are embedded into browser assets at build time. Keep all provider and AWS secrets exclusively on the AWS side.
