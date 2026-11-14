# Three-to-five-minute demonstration

The included video is an automatically assembled walkthrough of recorded, real application outputs. It is not a claim of a human-delivered presentation. Use this script to record your own explanation for the instructor.

1. **0:00–0:30 — Business and pipeline.** Show the DSU corpus (584 vectors, 1,536 dimensions), then switch to the fictional Noor Skills dataset. Explain that fictional facts are isolated from real DSU evidence. Explain that FAISS was requested instead of the assignment's Chroma.
2. **0:30–1:00 — Normal question.** Ask “How much is Web Foundations tuition?” Open the cited filename and its supporting excerpt. Show PKR 12,000 from the course catalogue.
3. **1:00–1:35 — Two documents.** Ask “How much are Web Foundations tuition and the current application processing fee, listed separately?” Show the course catalogue and current policy, PKR 12,000 and PKR 1,500.
4. **1:35–2:10 — Policy comparison.** Ask “Compare old and current certificate attendance rules.” Show archived 75%, current 80%, dates and policy labels. Explain default archived filtering.
5. **2:10–2:35 — Missing answer.** Ask “What is the hostel accommodation price?” Show the exact insufficient-information response rather than an estimate.
6. **2:35–3:10 — Injection.** Show the BANANA instruction in the operations test document, then ask the real processing-fee question. Inspect evidence to prove the injected passage reached the model. Show that the current fee and citations survived.
7. **3:10–3:50 — Failure and investigation.** Open initial vs final CSVs and the retrieval findings. Explain why k=1 cannot supply two independent documents, why omitted refund caveats failed the original oracle, and why an altered quotation was refused. Show one remaining limitation honestly.
8. **3:50–4:15 — Live update explanation.** Explain that editing source text leaves stored embeddings stale. Demonstrate the rebuild command and content fingerprint; do not change expected test answers silently.
