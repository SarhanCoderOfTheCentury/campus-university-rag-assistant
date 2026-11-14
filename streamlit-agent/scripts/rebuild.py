import argparse
import os
from dotenv import load_dotenv
from rag.config import ROOT
from rag.embeddings import GeminiEmbeddings
from rag.store import load_demo, load_documents, split_documents, make_store
import json
import numpy as np


def main():
    parser = argparse.ArgumentParser(description='Rebuild from source text; document edits require NEW embeddings.')
    parser.add_argument('--corpus', choices=['demo','dsu'], default='demo')
    parser.add_argument('--chunk-size', type=int, default=1000)
    parser.add_argument('--overlap', type=int, default=150)
    parser.add_argument('--replace-supplied', action='store_true', help='Explicitly replace supplied DSU vectors with the five edited curated documents.')
    args = parser.parse_args()
    load_dotenv(ROOT/'.env')
    emb = GeminiEmbeddings(os.environ.get('GEMINI_API_KEY',''))
    if args.corpus == 'demo':
        _, _, manifest = load_demo(emb, args.chunk_size, args.overlap, rebuild=True)
        print(json.dumps(manifest, indent=2))
    else:
        if not args.replace_supplied:
            parser.error('DSU original chunk/vector alignment is immutable by default. Use --replace-supplied only to replace it with newly embedded curated documents; keep a backup first.')
        chunks = split_documents(load_documents(ROOT/'knowledge/dsu'), args.chunk_size, args.overlap)
        vectors = np.asarray(emb.embed_documents([c.page_content for c in chunks]), dtype=np.float32)
        make_store(chunks, vectors, emb)  # validate before replacing either file
        records = []
        for c in chunks:
            m = c.metadata
            historical = m['source'].startswith('04_')
            records.append({**m,'document':m['source'],'content':c.page_content,
                'retrieval_policy':'historical_comparison_only_no_current_policy_answers' if historical else 'normal'})
        base = ROOT/'data/dsu'
        (base/'chunks.jsonl').write_text('\n'.join(json.dumps(r) for r in records)+'\n')
        np.save(base/'vectors.npy',vectors,allow_pickle=False)
        print('Replaced DSU curated corpus. Restart Streamlit to invalidate cached resources.')

if __name__ == '__main__':
    main()
