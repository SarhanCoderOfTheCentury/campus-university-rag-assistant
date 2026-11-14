import argparse
import json
import os
from dotenv import load_dotenv
from rag.config import ROOT, Settings
from rag.embeddings import GeminiEmbeddings
from rag.store import load_corpus
from rag.agent import RAGAgent

def main():
    p = argparse.ArgumentParser()
    p.add_argument('question')
    p.add_argument('--corpus', choices=['dsu','demo'], default='dsu')
    p.add_argument('--k', type=int, default=5)
    args = p.parse_args()
    load_dotenv(ROOT/'.env')
    key = os.getenv('GEMINI_API_KEY','')
    settings = Settings(corpus=args.corpus, k=args.k)
    emb = GeminiEmbeddings(key)
    store, chunks, _ = load_corpus(settings, emb)
    agent = RAGAgent(settings, emb, store, chunks, api_key=key)
    result = agent.ask(args.question)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(1 if result['status']=='api_error' else 0)

if __name__ == '__main__':
    main()
