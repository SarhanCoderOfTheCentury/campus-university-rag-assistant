"""Live integration checks against the USER-SUPPLIED 584-vector DSU corpus."""
import json
import os
import re
import time
from dotenv import load_dotenv
from rag.config import ROOT, Settings, REFUSAL
from rag.embeddings import GeminiEmbeddings
from rag.store import load_corpus
from rag.agent import RAGAgent
from .evaluate import write_csv

def main():
    load_dotenv(ROOT/'.env')
    key=os.environ['GEMINI_API_KEY']
    emb=GeminiEmbeddings(key,ROOT/'.cache/queries')
    settings=Settings(corpus='dsu')
    store,chunks,manifest=load_corpus(settings,emb)
    agent=RAGAgent(settings,emb,store,chunks,api_key=key)
    tests=[
        ('fee_conflict','What is the application processing fee? Explain any discrepancy between the FAQ and Spring 2027 notice.',r'1,?000',r'1,?500',r'2,?500'),
        ('transfer','What maximum percentage of total program credits can transfer to DSU?',r'50\s*%'),
        ('application','How do I apply online for admission?',r'apply|application|upload|submit'),
        ('missing_hours','What time does the admissions office open every day?',REFUSAL),
        ('unverified_history','Are there two authenticated old-to-current DSU policy changes with verified effective dates?',r'not|no |unverified|unknown|could not'),
        ('scholarships','Is financial assistance documented, and can you guarantee I qualify?',r'financial|scholarship',r'not|cannot|eligib|condition|could not'),
    ]
    rows=[]
    for case_id,question,*patterns in tests:
        result=agent.ask(question)
        for attempt in range(2):
            if result['status']!='api_error':
                break
            time.sleep(15)
            result=agent.ask(question)
        ok=result['status']!='api_error' and all(re.search(p,result['answer'],re.I) for p in patterns)
        if case_id not in ('missing_hours','unverified_history'):
            ok=ok and bool(result['sources'])
        rows.append({'id':case_id,'question':question,'expected_patterns':json.dumps(patterns),
            'actual_answer':result['answer'],'actual_sources':json.dumps(result['sources'],ensure_ascii=False),
            'status':'BLOCKED' if result['status']=='api_error' else ('PASS' if ok else 'FAIL'),
            'engine_status':result['status'],'corpus_fingerprint':manifest['fingerprint']})
        (ROOT/f'evidence/dsu_{case_id}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        write_csv(ROOT/'evidence/dsu_live_checks.csv',rows)
        print(case_id,rows[-1]['status'],result['answer'][:200],flush=True)
        time.sleep(8)

if __name__=='__main__':
    main()
