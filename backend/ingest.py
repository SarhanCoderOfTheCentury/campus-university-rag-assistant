"""Validate, section-chunk, freshly embed and atomically publish an uploaded corpus."""
from __future__ import annotations
import argparse,hashlib,json,os,re,shutil,tempfile,time,zipfile
from pathlib import Path
import numpy as np
from google import genai
from google.genai import types

DATA=Path(__file__).parent/'data'
MODEL='gemini-embedding-001'
DIMENSIONS=768

def sha(value):return hashlib.sha256(value).hexdigest()

def normalize(rows):
    """Legacy ingestion adapter retained for existing exported corpora."""
    result=[];seen=set()
    for row in rows:
        content=row.get('content','').strip()
        if not content or row['id'] in seen:continue
        if row.get('content_type')=='table' and 'fee' in row.get('title','').lower():continue
        seen.add(row['id'])
        result.append({'source_id':row['id'],'document_id':row.get('document_id') or row.get('document_file'),
            'chunk_id':row['id'],'title':row.get('title'),'section':row.get('section') or row.get('title'),
            'url':row.get('source_url'),'page_start':row.get('pdf_page_start'),'excerpt':content,
            'embedding_text':row.get('embedding_text') or content,'curated':row['id'].startswith('curated-'),
            'historical':row.get('retrieval_policy')=='historical_comparison_only_no_current_policy_answers',
            'content_type':row.get('content_type'),'confidence':row.get('confidence'),'source_capture_date':None})
    return result

def bundle_records(rows):
    records=[];ids=set();sections=set()
    for row in rows:
        required=['chunk_id','doc_id','doc_title','doc_type','source_file','section_title','section_index','version','effective_date','status','text']
        if any(key not in row for key in required):raise ValueError('Missing authoritative source metadata')
        if row['chunk_id'] in ids:raise ValueError('Duplicate chunk identity')
        ids.add(row['chunk_id'])
        if row['status'] not in ['current','archived']:raise ValueError('Unknown document status')
        if not re.fullmatch(r'DSU-\d{2}',row['doc_id']):raise ValueError('Invalid document identity')
        source=Path(row['source_file'])
        if source.is_absolute() or '..' in source.parts or source.parts[0]!='knowledge_base':raise ValueError('Untrusted source path')
        text=row['text'].replace('\r\n','\n').strip()
        if not text or len(text)>16000:raise ValueError('Section exceeds safe context size; split at subsection boundaries')
        # Semantic sections are already self-contained. Never split exceptions from rules,
        # change numeric table alignment, or trust the bundle's executable scripts/index.
        section_key=(row['doc_id'],row['section_index'])
        if section_key in sections:raise ValueError('Duplicate section index')
        sections.add(section_key)
        prefix=f"{row['doc_title']} | {row['section_title']} | Version {row['version']} | {row['status']} | Effective {row['effective_date']}"
        embedding_text=prefix+'\n'+text
        digest=sha(embedding_text.encode())
        sid=f"{row['doc_id']}:{row['chunk_id']}:{digest[:12]}"
        records.append({'source_id':sid,'document_id':row['doc_id'],'chunk_id':sid,
            'original_chunk_id':row['chunk_id'],'title':row['doc_title'],
            'section':row['section_title'],'section_index':row['section_index'],
            'version':row['version'],'effective_date':row['effective_date'],'status':row['status'],
            'source_file':row['source_file'],'url':None,'page_start':None,'excerpt':text,
            'embedding_text':embedding_text,'content_sha256':digest,'curated':True,
            'historical':row['status']=='archived','content_type':row['doc_type'],
            'is_programme':row['section_title'].startswith('Program:'),
            'answerable':not(row['doc_id']=='DSU-01' and row['section_index'] in [0,2]),
            'confidence':'supplied_dataset','source_capture_date':None})
    if not records:raise ValueError('Empty corpus')
    return sorted(records,key=lambda r:(r['document_id'],r['section_index']))

def cache_key(record,model=MODEL,dimensions=DIMENSIONS):
    return sha(json.dumps([model,dimensions,'RETRIEVAL_DOCUMENT',record['embedding_text']],ensure_ascii=False).encode())

def normalized_matrix(values,expected):
    matrix=np.asarray(values,dtype=np.float32)
    if matrix.shape!=(expected,DIMENSIONS) or not np.isfinite(matrix).all():raise ValueError('Embedding count, dimensions or finite-value check failed')
    norms=np.linalg.norm(matrix,axis=1,keepdims=True)
    if np.any(norms<1e-8):raise ValueError('Zero embedding vector')
    return matrix/norms

def atomic_json(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)

def build(archive,*,output=DATA,cache_dir=Path('.deploy/embeddings-v2'),fresh=False,client=None):
    with zipfile.ZipFile(archive) as z:
        # Read data only; no pickle, executable bundle code or bundled database loading.
        if z.getinfo('chunks.jsonl').file_size>10_000_000:raise ValueError('Corpus exceeds configured input budget')
        rows=[json.loads(line) for line in z.read('chunks.jsonl').decode('utf-8').splitlines() if line.strip()]
        records=bundle_records(rows)
    output=Path(output);cache_dir.mkdir(parents=True,exist_ok=True)
    cache_path=cache_dir/'checkpoint.json';cache={} if fresh or not cache_path.exists() else json.loads(cache_path.read_text())
    if client is None:
        key=os.getenv('GEMINI_API_KEY')
        if not key:
            import boto3
            key=json.loads(boto3.client('secretsmanager').get_secret_value(SecretId=os.getenv('RAG_PROVIDER_SECRET','campus-rag/gemini'))['SecretString'])['GEMINI_API_KEY']
        client=genai.Client(api_key=key)
    calls=0
    for start in range(0,len(records),8):
        batch=[r for r in records[start:start+8] if cache_key(r) not in cache]
        if batch:
            for attempt in range(7):
                try:
                    response=client.models.embed_content(model=MODEL,contents=[r['embedding_text'] for r in batch],config=types.EmbedContentConfig(task_type='RETRIEVAL_DOCUMENT',output_dimensionality=DIMENSIONS))
                    values=[e.values for e in response.embeddings];normalized_matrix(values,len(batch));break
                except Exception as exc:
                    if getattr(exc,'code',None) not in [429,500,502,503,504] or attempt==6:raise RuntimeError('Embedding failed; published index unchanged') from None
                    delay=min(45,2**attempt+3);print(f'Provider retry in {delay}s; checkpoint retained',flush=True);time.sleep(delay)
            for r,vector in zip(batch,values,strict=True):cache[cache_key(r)]=vector
            atomic_json(cache_path,cache);calls+=1
        print(f'Validated embeddings {min(start+8,len(records))}/{len(records)}',flush=True)
    matrix=normalized_matrix([cache[cache_key(r)] for r in records],len(records))
    output.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='rag-index-',dir=output.parent))
    try:
        atomic_json(staging/'chunks.json',records);np.save(staging/'vectors.npy',matrix,allow_pickle=False)
        docs=staging/'documents';docs.mkdir()
        for docid in dict.fromkeys(r['document_id'] for r in records):
            parts=[r['excerpt'].split('\n',1)[-1] for r in records if r['document_id']==docid]
            (docs/(docid+'.md')).write_text('\n\n'.join(parts)+'\n',encoding='utf-8')
        manifest={'pipeline_version':2,'dataset_sha256':sha(Path(archive).read_bytes()),
            'chunks_sha256':sha((staging/'chunks.json').read_bytes()),'vectors_sha256':sha((staging/'vectors.npy').read_bytes()),
            'embedding_model':MODEL,'dimensions':DIMENSIONS,'chunks':len(records),'documents':len(list(docs.iterdir())),
            'task_type_document':'RETRIEVAL_DOCUMENT','task_type_query':'RETRIEVAL_QUERY','normalized':True,
            'dataset_kind':'fictional_classroom','capture_dates_known':False,
            'chunking':'Complete supplied Markdown sections; version, date and scope prefixed for embedding',
            'rebuilt_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'fresh_provider_batches':calls,
            'source_order':[r['source_id'] for r in records]}
        atomic_json(staging/'manifest.json',manifest)
        # Build into staging first. Publish only a complete, validated release.
        backup=output.with_name(output.name+'.previous')
        if backup.exists():shutil.rmtree(backup)
        if output.exists():output.rename(backup)
        try:staging.rename(output)
        except BaseException:
            if backup.exists():backup.rename(output)
            raise
        if backup.exists():shutil.rmtree(backup)
        print('Published complete index:',len(records),'sections;',calls,'fresh batches',flush=True)
        return manifest
    finally:
        if staging.exists():shutil.rmtree(staging)

def main():
    p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('--output',type=Path,default=DATA);p.add_argument('--fresh',action='store_true',help='Re-embed every section; ignore local checkpoints');a=p.parse_args()
    build(a.archive,output=a.output,fresh=a.fresh)

if __name__=='__main__':main()
