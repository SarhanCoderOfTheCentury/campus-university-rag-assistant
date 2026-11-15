"""Normalize uploaded DSU source records and build a reproducible local vector index."""
from __future__ import annotations
import argparse,hashlib,json,os,zipfile,time,re
from pathlib import Path
import numpy as np
from google import genai
from google.genai import types

DATA = Path(__file__).parent / 'data'

def normalize(rows):
    result=[];seen=set()
    for row in rows:
        content=row.get('content','').strip()
        if not content or row['id'] in seen: continue
        if row.get('content_type')=='table' and 'fee' in row.get('title','').lower(): continue
        seen.add(row['id'])
        curated=row['id'].startswith('curated-')
        result.append({
            'source_id':row['id'],'document_id':row.get('document_id') or row.get('document_file'),
            'chunk_id':row['id'],'title':row.get('title'), 'section':row.get('section') or row.get('title'),
            'url':row.get('source_url'),'page_start':row.get('pdf_page_start'), 'excerpt':content,
            'embedding_text':row.get('embedding_text') or content,'curated':curated,
            'historical':row.get('retrieval_policy')=='historical_comparison_only_no_current_policy_answers',
            'content_type':row.get('content_type'), 'confidence':row.get('confidence'),
            'source_capture_date':None,
        })
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('archive');args=parser.parse_args()
    archive=Path(args.archive)
    with zipfile.ZipFile(archive) as z:
        base='dsu_five_document_rag/'
        rows=[json.loads(l) for l in z.read(base+'all_chunks_with_curated.jsonl').decode().splitlines()]
        records=normalize(rows);DATA.mkdir(exist_ok=True)
        (DATA/'chunks.json').write_text(json.dumps(records,ensure_ascii=False),encoding='utf-8')
        (DATA/'policy_conflicts.json').write_bytes(z.read(base+'policy_conflicts.json'))
        docs=DATA/'documents';docs.mkdir(exist_ok=True)
        for name in z.namelist():
            if name.startswith(base+'knowledge_documents/') and name.endswith('.md'):
                (docs/Path(name).name).write_bytes(z.read(name))
    if not os.getenv('GEMINI_API_KEY'):
        import boto3
        secret=boto3.client('secretsmanager').get_secret_value(SecretId=os.getenv('RAG_PROVIDER_SECRET','campus-rag/gemini'))
        key=json.loads(secret['SecretString'])['GEMINI_API_KEY']
    else:key=os.environ['GEMINI_API_KEY']
    model='gemini-embedding-001';client=genai.Client(api_key=key)
    cache_path=Path('.deploy/embedding-cache.json');cache_path.parent.mkdir(exist_ok=True)
    cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
    for start in range(0,len(records),8):
        batch=[r for r in records[start:start+8] if r['source_id'] not in cache]
        if batch:
            for attempt in range(12):
                try:
                    response=client.models.embed_content(model=model,contents=[r['embedding_text'] for r in batch],config=types.EmbedContentConfig(task_type='RETRIEVAL_DOCUMENT',output_dimensionality=768))
                    break
                except Exception as exc:
                    if getattr(exc,'code',None)!=429 or attempt==11:raise RuntimeError('Embedding provider failed: '+type(exc).__name__) from None
                    delay=re.search(r'retry in ([\d.]+)s',str(exc),re.I)
                    seconds=min(45,max(10,float(delay.group(1))+2)) if delay else 30
                    print(f'Embedding rate limit: pausing {seconds:.0f}s, checkpoint retained',flush=True);time.sleep(seconds)
            for r,e in zip(batch,response.embeddings):cache[r['source_id']]=e.values
            cache_path.write_text(json.dumps(cache))
        print(f'Embedded {min(start+8,len(records))}/{len(records)} passages',flush=True)
    vectors=[cache[r['source_id']] for r in records]
    matrix=np.asarray(vectors,dtype=np.float32)
    matrix/=np.maximum(np.linalg.norm(matrix,axis=1,keepdims=True),1e-12)
    np.save(DATA/'vectors.npy',matrix,allow_pickle=False)
    manifest={'dataset_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'chunks_sha256':hashlib.sha256((DATA/'chunks.json').read_bytes()).hexdigest(),'vectors_sha256':hashlib.sha256((DATA/'vectors.npy').read_bytes()).hexdigest(),'embedding_model':model,'dimensions':768,'chunks':len(records),'capture_dates_known':False}
    (DATA/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('Index saved:',manifest['chunks'],'passages')

if __name__=='__main__':main()
