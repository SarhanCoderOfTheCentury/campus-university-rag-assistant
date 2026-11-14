"""Offline proof of supplied vector integrity; no Gemini calls."""
import json
import numpy as np
from rag.config import ROOT
from rag.store import load_dsu
from langchain_core.embeddings import Embeddings

class NoNetworkEmbeddings(Embeddings):
    def embed_documents(self, texts):
        raise RuntimeError('No API calls allowed in bundle integrity verification.')
    def embed_query(self, text):
        raise RuntimeError('No API calls allowed in bundle integrity verification.')

def main():
    store, chunks, manifest = load_dsu(NoNetworkEmbeddings())
    vectors = np.load(ROOT/'data/dsu/vectors.npy', allow_pickle=False)
    scores, ids = store.index.search(vectors[:1], 1)
    assert len(chunks) == 584
    assert vectors.shape == (584, 1536)
    assert int(ids[0,0]) == 0 and abs(float(scores[0,0])-1) < 1e-4
    assert np.isfinite(vectors).all()
    assert np.allclose(np.linalg.norm(vectors,axis=1), 1, atol=1e-5)
    print(json.dumps({**manifest, 'self_search_index': int(ids[0,0]),
        'self_search_score':float(scores[0,0]),'all_vectors_unit_normalized':True}, indent=2))

if __name__ == '__main__':
    main()
