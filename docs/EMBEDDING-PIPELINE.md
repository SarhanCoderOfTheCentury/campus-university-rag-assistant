# Replacement corpus and complete-answer pipeline

The React/AWS system uses the uploaded `dsu_rag_bundle.zip` exclusively. The separate Streamlit application is unchanged. The corpus contains five classroom documents, 45 Markdown sections, nine programmes, current policy v3.0 and archived policy v2.1. The small chat-input label says **Classroom dataset · Not official**. Routine answers do not repeat that notice; source provenance remains intact and authenticity questions are answered honestly.

## Rebuild

Use Python 3.12 and `backend/requirements-test.txt`. Supply `GEMINI_API_KEY` through the environment, or authorized AWS credentials that can read the existing provider secret. Never put a key into source control.

```bash
python -m backend.ingest /path/to/dsu_rag_bundle.zip --fresh
python -m pytest -q
python -m backend.deploy.validate_corpus
python backend/deploy/package.py
python -m backend.deploy.update_code --zip .deploy/lambda.zip
```

The real-model regression command consumes provider quota. It can rerun one case with `--case comparison`. `npm test` checks protocol, memory and actual Streamdown GFM rendering; `npm run build` validates TypeScript and builds Vercel's `dist` output on Node 22.

1. Read JSONL data only. Never execute bundled scripts or deserialize its Chroma database, checkpoint or supplied embedding arrays.
2. Validate document identities, source paths, metadata, unique IDs and section sizes. Preserve whole source sections so rules and exceptions cannot be split. Source excerpts are not rewritten.
3. Prefix embedding input with title, section, policy version, status and effective date. Citation IDs bind document ID, supplied chunk ID and content hash. Editing content invalidates its vector cache entry.
4. Generate new `gemini-embedding-001` vectors with `RETRIEVAL_DOCUMENT`, 768 dimensions. This rebuild made six fresh provider batches for all 45 sections. Query vectors use the same manifest model/dimensions with `RETRIEVAL_QUERY`.
5. Check response counts, finite values, nonzero norms and dimensions. Normalize every vector. Checkpoint by text + model + dimensions + task type in ignored `.deploy/embeddings-v2/`; retry transient provider errors with bounded backoff. Omitting `--fresh` resumes matching content only.
6. Build a complete staging directory with readable source documents and a hashed manifest. Publish only after all sections succeed. A failed embedding run leaves the previous published index intact. Redeploying the immutable Lambda ZIP switches the live service to the new corpus.

No URL or page number is inferred from a title. The source viewer routes serve exactly the supplied sections assembled in their original order. Sections with unavailable page metadata omit it. Citation locations preserve version, status and effective date. The overview's classroom disclaimer is retained in its source document.

## Retrieval and answer quality

Hybrid cosine/BM25 ranking uses reciprocal-rank fusion, followed by LLM relevance ranking over real passages. Archived sections are excluded by default. Comparisons include both policy versions; broad catalogues retain all nine programmes even if the reranker drops one. Library queries preserve both Rs. 20 and Rs. 25 fine passages: the corpus does not establish which supersedes the other.

A typed answer contains up to 12 intact Markdown sections plus a completion flag. A whole-answer review checks both grounding and completeness, including exceptions, units, dates, all requested subquestions and unresolved contradictions. A single repair can correct a failed draft. Unknown citations or a second failed review stop the response instead of presenting it as complete. This is a useful validation layer, not a universal proof of factual correctness.

The UI receives genuine progress events while planning, retrieval and generation run. Verified sections stream after whole-answer validation. No synthetic typing delays or invented retrieval stages are added. Streamdown renders complete GFM blocks with incomplete-Markdown repair disabled; tables retain headers, alignment, emphasis, copy/export controls and horizontal scrolling on narrow screens. Tall tables show all rows in the normal conversation scroll.

The corpus replacement creates a new browser storage namespace and a dataset-scoped server memory key. Old cited answers and previous-corpus context do not leak into new sessions. Subsequent turns retain the existing refresh, correction, forgetting, cancellation and concurrency protection mechanisms.

Official references: [Gemini embeddings](https://ai.google.dev/gemini-api/docs/embeddings), [Streamdown GFM](https://streamdown.ai/docs/gfm), [Streamdown typography](https://streamdown.ai/docs/typography).
