# Retrieval findings

Actual Gemini answers are in the linked CSVs. Expected answers and sources were frozen before running the tests. PASS is an automatic oracle result, with quotations retained for review.

- Final 20-question suite: 20/20 PASS; 0 FAIL; 0 BLOCKED.
- DSU supplied-corpus checks: 6/6 PASS; 0 FAIL; 0 BLOCKED.

## Fixed six-question k experiment

| k | Answer verdicts | Expected sources + fact patterns in packed context | Extra source files retrieved |
| --- | --- | --- | --- |
| 1 | 1/6 PASS; 5 FAIL; 0 BLOCKED | 2/6 | 1/6 |
| 3 | 3/6 PASS; 3 FAIL; 0 BLOCKED | 4/6 | 3/6 |
| 5 | 5/6 PASS; 1 FAIL; 0 BLOCKED | 5/6 | 5/6 |

The six unchanged questions are T02 (course tuition), T03 (current fee), T06 (refund), T10 (two charges), T12 (attendance plus correction), and T14 (old/current attendance). The corpus fingerprint is fixed throughout this sweep. Required-evidence coverage checks the frozen expected fact patterns in the packed passages and metadata, not just the filename.

At k=1, a question needing two independent documents cannot receive all its required evidence. More chunks can restore coverage, but may introduce unrelated source files. For T02, the 1,000-character semantic index ranked a Git Teamwork passage above the Web Foundations passage; the answer correctly refused when the needed price was absent. The extra-evidence column is a source-level proxy; it does not identify every irrelevant paragraph within an otherwise relevant document. The CSV preserves the actual answer so evidence coverage can be distinguished from generation correctness.

## Chunking experiment

| Characters / overlap | Answer verdicts |
| --- | --- |
| 1000 / 150 | 2/3 PASS; 1 FAIL; 0 BLOCKED |
| 600 / 100 | 3/3 PASS; 0 FAIL; 0 BLOCKED |

Only chunk size/overlap changed for these three questions (T02, T10, T12), at k=5 with semantic retrieval. Smaller chunks make passages more focused, but can separate the main rule from its exception or metadata. A larger k alone cannot repair missing evidence that was split away or not selected.

## Hybrid stretch comparison

| Method | Answer verdicts |
| --- | --- |
| semantic | 5/6 PASS; 1 FAIL; 0 BLOCKED |
| hybrid | 6/6 PASS; 0 FAIL; 0 BLOCKED |

Both methods use the same six questions, corpus, 1,000/150-character chunking and k=5. Hybrid is semantic + BM25 fused by ranks; it is not a different embedding model. Optional rewrite and LLM re-ranking are implemented but are not part of this controlled method comparison.

## Failures and interpretation

The first run omitted the processing-fee caveat from two refund answers. A stricter general prompt now requests relevant non-refundable charges and exceptions. A DSU answer compressed repeated source lines into a noncontiguous quotation; the validator refused it. One bounded repair now requests a shorter exact quotation from the same context. First-run CSVs remain in evidence/initial_run.

Remaining failures are reported below without changing the test oracle:

- k experiment, T02, k=1: FAIL — No valid supported answer: insufficient
- k experiment, T06, k=1: FAIL — Expected fact/version not present: non.refundable
- k experiment, T10, k=1: FAIL — No valid supported answer: insufficient
- k experiment, T12, k=1: FAIL — Expected supporting sources not cited: 03_current_policy.md
- k experiment, T14, k=1: FAIL — Expected supporting sources not cited: 04_previous_policy.md
- k experiment, T02, k=3: FAIL — No valid supported answer: insufficient
- k experiment, T06, k=3: FAIL — Expected fact/version not present: non.refundable
- k experiment, T10, k=3: FAIL — No valid supported answer: insufficient
- k experiment, T10, k=5: FAIL — Expected supporting sources not cited: 03_current_policy.md
- Chunking, T10, k=5: FAIL — Expected supporting sources not cited: 03_current_policy.md
- Hybrid, T10, k=5: FAIL — Expected supporting sources not cited: 03_current_policy.md
Best observed semantic k: 5 (5/6 answers passed). The default hybrid k=5 achieved 6/6 PASS; 0 FAIL; 0 BLOCKED.

The strongest setting on this small experiment is the one with the highest recorded answer correctness and full evidence coverage, not necessarily the largest k. Ties and failures are visible in the tables. This sample is too small to establish a universal best configuration. API rate limits, uncertain DSU capture dates, source-level relevance proxies, and citation-versus-entailment gaps remain practical limits.

The tests are independent questions; neither generated answers nor expected answers are indexed into the knowledge base. No production response is hardcoded to a test question.
