# Campus RAG streaming contract (version 1)

This is an application protocol. Its event names are not built-in LangChain events.
The university RAG backend is the authority for evidence metadata and public activity summaries.
No client-generated processing stages, inferred document titles, or synthetic retrieval delays are used.

## Transport

`POST /api/chat/stream`, with JSON request body and `Accept: text/event-stream`.
The frontend uses fetch rather than native EventSource because it needs a POST body, cancellation and existing-session authentication.
The SSE framing is parsed by `eventsource-parser`; UTF-8 chunk boundaries, BOM, CRLF, comments and multi-line SSE data are supported.

Request fields:

| Field | Type | Meaning |
| --- | --- | --- |
| protocol_version | 1 | Contract version |
| conversation_id | string | Frontend conversation identity |
| request_id | string | Unique identity for this submitted question |
| message_id | string | Identity of the new assistant turn |
| question | string, 1–8000 characters | The question, included once |
| history | array of role/content | Previous completed turns only, at most 40 messages |

All identifiers are opaque, nonempty strings, at most 200 characters, without control characters.
The frontend sends UUIDs for new requests and messages. The backend must echo those identities unchanged.
The backend creates a distinct `run_id` and sends `started` as sequence 1.

Every event payload has these fields, in addition to its type-specific fields:

```ts
{
  protocol_version: 1,
  type: EventType,
  conversation_id: string,
  request_id: string,
  message_id: string,
  run_id: string,
  sequence: number // positive integer, increment by exactly one
}
```

SSE `event` must equal the JSON `type`. SSE `id` must equal `${run_id}:${sequence}`.
The stream ends with exactly one `completed` or `error` event followed by EOF. Missing terminal events produce an interrupted state.
Duplicate sequences are idempotent. Sequence gaps, mismatched run identities, unknown references and metadata conflicts interrupt the run rather than contaminating another answer.
There is no automatic POST retry or transparent regeneration. To retry, submit a new question/request.

The FastAPI example uses native `fastapi.sse.EventSourceResponse` and `ServerSentEvent` from tested FastAPI 0.162.7. Its endpoint is an **async generator**, with authorization as a pre-stream dependency. Native SSE supplies keep-alive comments, no-cache and no-buffering headers. Comments keep the connection alive and never become UI progress.

## Event payloads

| type | Additional fields | Actual operation represented |
| --- | --- | --- |
| started | none | Backend accepted this authenticated run; not a claim that retrieval happened |
| retrieval_started | retrieval_id, label, optional detail | A retriever actually started |
| document_found | retrieval_id, source | A genuine retrieved evidence passage with authoritative metadata |
| document_reading | activity_id, document_id, source_ids, optional detail | Backend began reading/preparing those retrieved passages |
| document_processed | activity_id, document_id, optional detail | That exact reading/preparation operation finished |
| retrieval_completed | retrieval_id, source_ids, optional summary | Retriever/context selection finished |
| reasoning_update | activity_id, label, status, optional summary | Explicit public activity or concise evidence-based summary |
| answer_delta | block_id, delta, source_ids, kind | Genuinely new verified answer text for a stable block |
| sources | sources, final | Authoritative list of sources actually cited in the response |
| completed | outcome, optional elapsed_ms | This response finished successfully |
| error | code, message | This run failed; public error message only |

`reasoning_update.status` is `running`, `completed`, or `failed`. Never send hidden reasoning, private scratchpads, provider chain-of-thought tokens or raw stack traces.
A reasoning update replaces that activity's label/summary; it does not append hidden tokens.
The backend may report understanding, comparison, reranking, or analysis stages only if those stages actually run. The provided reference pipeline does not pretend to perform extra stages.

Each `document_processed` matches a preceding `document_reading` with the same activity/document IDs.
Each `document_found` occurs inside the corresponding active retrieval operation.
An existing completed activity cannot restart under the same ID. Use a new activity ID for another operation.

## Evidence metadata

```ts
{
  source_id: string,       // stable ingestion identity for this evidence reference
  document_id: string,     // stable original document identity
  chunk_id: string,        // stable evidence chunk identity
  citation_number: number, // positive integer, assigned by the backend for this response
  title?: string,          // actual original title, never an LLM guess
  url?: string,            // actual authorized URL or origin-relative viewer route
  page_start?: number,     // one-based, from ingestion
  page_end?: number,
  section?: string,
  excerpt: string         // actual retrieved supporting passage, 1–16000 characters
}
```

Omit unavailable metadata instead of sending null or inventing a value. Page ranges must be positive and ordered.
The ingestion pipeline must establish `source_id`, `document_id`, and `chunk_id`; the example rejects documents without them.
If your PDF loader uses zero-based page indexes, normalize its **documented** page index during ingestion. Do not guess page numbers in the UI or model output.
For a plain-text file without page metadata, omit the page fields.

The same `source_id` must retain identical metadata throughout a run. The same document/chunk/page/section reference must not appear under conflicting IDs. Citation numbers must be unique within an answer.
Repeated appearances of the same evidence ID are deduplicated. Different chunks or page references in the same original document remain separate citations.
Numbers are scoped to one answer, not the whole conversation.

Only server-provided http(s) URLs and safe origin-relative viewer routes can become links. Missing/unsafe URLs get an evidence inspector, not a guessed download link. The backend/viewer must enforce document access permissions.
Model-authored markdown links/images do not create clickable supporting evidence in this interface.

## Answer blocks and inline citation timing

An answer is an ordered list of stable `block_id`s. A block is a claim or a paragraph whose statements are supported by its `source_ids`.
Send multiple `answer_delta`s with the same block ID to append actual streamed text.
A block's `kind` and `source_ids` are immutable after the first delta.

- `kind: "grounded"` requires at least one already-registered evidence ID.
- `kind: "notice"` requires an empty source list and is for non-factual operational messages/clarifications, never uncited university policy.
- Register sources through `document_found` (or an early `sources` event) **before** referencing them in a delta.
- Citations render as numbered shadcn buttons beside the block. Their numbers and metadata are taken from the registered backend sources.
- If a claim's support is not known until the end of a sentence, buffer that sentence on the backend until validated, then emit it. Do not temporarily publish unverified factual text or invent preliminary citations.
- Never chop a completed answer into artificial delayed tokens. Emit only genuinely available, verified deltas.

The final `sources` event must set `final: true` and contain exactly the deduplicated union of all cited source IDs. Retrieved-but-unused documents must not be listed as supporting answer sources.
A successful `completed` event is rejected if sources do not match citations, a step is unfinished/failed, or no response text arrived.
`outcome` is `answered` (requires cited evidence), `no_evidence` (no supporting evidence), or `clarification` (no document-grounded assertions).

The frontend renders the explicit no-support message on a `no_evidence` outcome. For network/configuration failures it says that no sources were **received**, rather than claiming a search found nothing.

## LangChain mapping in the included backend

| Actual LangChain event / operation | Application event |
| --- | --- |
| Root on_retriever_start from BaseRetriever.astream_events(version="v2") | retrieval_started |
| Root on_retriever_end and its actual Document objects | document_found |
| Real passage validation and context preparation | document_reading, document_processed |
| Context preparation completed | retrieval_completed |
| Explicit on_custom_event named campus_activity | reasoning_update |
| Root grounded_answer on_chain_stream / on_chain_end with structured claims | verified answer_delta |
| Completed citation validation | sources, completed |
| Retriever/model/validation failure | error |

Raw `on_chat_model_stream` reasoning tokens are deliberately not forwarded. The reference chain uses `JsonOutputParser` and incremental claim dictionaries; the adapter emits only new verified text.
The default verifier permits exact retrieved quotations. For generated paraphrases or synthesis, install an actual entailment/grounding verifier through `RagService.verify_claim`; never replace it with an unconditional success function.
ID validation proves a citation refers to retrieved evidence. Semantic support for generated paraphrases must be established by that real verifier, not by a frontend animation.

To report extra real stages, dispatch a public custom event from an actual LangChain node:

```python
from langchain_core.callbacks.manager import adispatch_custom_event

await adispatch_custom_event(
    "campus_activity",
    {
        "activity_id": actual_stage_id,
        "label": public_stage_label,
        "status": "running",
        "summary": safe_public_summary,
    },
    config=config,
)
# Run the actual operation, then report completed (or let an exception fail the run).
```

Do not dispatch a canned list of stages merely to keep the screen busy.

## Cancellation, errors, and isolation

Each conversation can have one active request. A new submission in that conversation cancels its earlier request before installing a new callback target.
Other conversations can stream independently. Switching views does not transfer source catalogs or events between them.
Stop/Escape aborts fetch immediately, marks unfinished activities interrupted, and preserves partial text/citations.
Unmounting aborts all active requests. All fetch readers, abort listeners and idle timers are cleaned up.
The server async-generator cleanup closes the underlying LangChain event iterators.

The client idle timeout is 90 seconds; real keep-alive bytes reset it. The example backend has a 300-second run limit.
The client caps event buffers, total stream bytes, activity/source counts and answer length. It preserves received data on malformed events, EOF, timeouts or errors and never marks such a run completed.

## Official references checked for this implementation

- https://ui.shadcn.com/docs/ai-elements
- https://ui.shadcn.com/docs/ai-elements/base/reasoning.md
- https://ui.shadcn.com/docs/ai-elements/base/chain-of-thought.md
- https://ui.shadcn.com/docs/ai-elements/base/sources.md
- https://ui.shadcn.com/docs/ai-elements/base/inline-citation.md
- https://ui.shadcn.com/docs/ai-elements/base/message.md
- https://ui.shadcn.com/docs/components/base/code-block.md
- https://streamdown.ai/docs/usage
- https://github.com/rexxars/eventsource-parser
- https://fastapi.tiangolo.com/tutorial/server-sent-events/
- https://reference.langchain.com/python/langchain-core/runnables/base/Runnable/astream_events
