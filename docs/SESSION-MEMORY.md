# Active conversation memory

Each conversation has a private random capability token generated in the browser. Requests send that token over HTTPS together with the conversation ID and a monotonically increasing turn number. The token is never passed to the model or echoed in SSE events. DynamoDB keys hash the token and conversation ID, so the default initial conversation ID cannot mix different visitors' context.

## What is remembered

The existing LangChain question-planning call now updates a small typed set of session notes: volunteered name, programme interest, campus preference, study level, language, answer style and current topic. Existing nonempty values are retained unless explicitly corrected or forgotten. No extra summarization call is added on every turn. The server also retains at most four recent completed question/answer pairs, bounded to 16,000 characters. Notes and recent turns are supplied to query rewriting and answer generation as untrusted conversation context.

University facts are retrieved again on each factual turn. Memory is never a citation catalog or documentary evidence. A remembered statement about a fee cannot bypass the normal source-support checks. The model is instructed not to put credentials or sensitive personal data into notes, and known credential patterns are redacted from server-side recent context. This is not a comprehensive detector for every kind of sensitive text.

## Isolation, expiry and interrupted requests

DynamoDB conditionally assigns the newest turn as the active owner of its conversation. A superseded request cannot commit notes or a partial answer over a newer turn. A completion is sent only after its memory write succeeds. Cancelled, failed, interrupted and rejected responses do not commit updated notes or transcripts. Existing explicit cancellation checks also reject superseded memory owners.

Memory expires after 24 hours of inactivity. The server checks expiry itself rather than relying on DynamoDB's asynchronous TTL deletion. New conversations use new tokens and do not inherit old notes. Browser account login and cross-device memory are not implemented; this remains a public-document service. The capability token grants access to one conversation context, so do not share browser session-storage exports.

Say **“Forget my name”** to remove that field from notes and the server's recent context, or **“Forget everything”** to clear the retained context. Corrections such as **“Actually, my name is …”** replace the previous preference. Forgetting context does not delete messages already visible in the chat transcript. Starting a new conversation gives a separate context.

## Refresh within the tab

The frontend keeps a validated snapshot in `sessionStorage`, not shared `localStorage`. It restores the active conversation, transcript, citation metadata and memory token after a refresh. In-progress responses are restored as interrupted and never become completed history. Snapshots expire after 24 idle hours, omit redundant nested request histories, and are bounded to 20 conversations, 40 exchanges per saved conversation and approximately 1.5 million serialized characters. While a tab stays open its in-memory transcript is not truncated by those persistence limits.

If storage is denied or full, the open tab continues in memory but refresh restoration is not guaranteed. Closing the tab normally ends browser session storage; browser session-restore features can restore it. Duplicating a tab can copy its existing session storage, depending on the browser; copied conversation tokens refer to the same conversation and still use turn-ownership checks. This is conversation/session memory, not a permanent user profile.

## Checks

Offline tests cover note corrections, forgetting, credential-pattern redaction, whole-pair context limits, expiry before TTL deletion, conditional stale-write rejection, malformed browser snapshots, storage denial, restoration and conversation-token separation. Real DynamoDB checks exercise recall, correction, superseded-write rejection and token isolation. Live checks and the deployed UI additionally verify multi-turn recall and refresh behavior.

See the [transcript-free validation results](session-memory-validation.json) and [updated interface screenshot](screenshots/flaticon-icons.jpg). The browser checks used a synthetic test preference; no conversation transcript or capability token is published in these results.
