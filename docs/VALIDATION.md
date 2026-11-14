# Validation — 14 November 2026

- TypeScript: 42 tests passed across five files, including validation/reduction of actual FastAPI SSE fixture output.
- Python: 14 tests passed, including native FastAPI serialization, real LangChain retriever callbacks, cancellation cleanup, authorization denial, grounding failures and the actual example factory's incremental JSON parser.
- Production: TypeScript checking and Vite build passed. Vite reports large third-party chunks; answer rendering and Remotion remain lazy-loaded. No bundle-size threshold is claimed.
- Component provenance: all 24 installed registry files match their recorded SHA-256 hashes. UI primitives were not rewritten.
- Browser: submitted an explicitly labelled test question through local FastAPI and LangChain. Confirmed a completed, auto-collapsed timeline, reopening retained retrieval/document activities, inline [1] placement, Sources expansion, and the exact test excerpt/URL in the evidence inspector.
- Responsive browser check: at 390×640 and 800×600, empty-document scroll height equalled viewport height, horizontal width fitted, and no message scroller was mounted. The focused mobile prompt's outline style was `none`. The mobile citation inspector fitted its viewport.
- The temporary test endpoint, development orchestration and viewport harness were removed before the production build. The shipped frontend has no configured university API and no fixture fallback.

Fixtures assert application plumbing only. They do not validate an unseen university corpus, production model, deployment credentials, document ACL implementation, or semantic support for arbitrary paraphrased answers. Those require the real backend integration described in README.md.
