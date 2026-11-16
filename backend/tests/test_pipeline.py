import json,zipfile
from types import SimpleNamespace
import numpy as np
import pytest
from backend.ingest import bundle_records,cache_key,normalized_matrix,build
from backend.university import Answer
from pathlib import Path
from rank_bm25 import BM25Okapi
from backend.university import UniversityAgent,Plan

def row():return {'chunk_id':'fixture-chunk','doc_id':'DSU-03','doc_title':'Policy','doc_type':'policy','source_file':'knowledge_base/policy.md','section_title':'Attendance','section_index':1,'version':'3.0','effective_date':'2026-08-01','status':'current','text':'## Attendance\nMinimum 75%. Laboratory exception: 85%.'}

def test_section_identity_changes_with_content_and_preserves_exceptions():
    original=bundle_records([row()])[0]
    edited=bundle_records([{**row(),'text':'## Attendance\nChanged rule.'}])[0]
    assert original['source_id']!=edited['source_id']
    assert cache_key(original)!=cache_key(edited)
    assert '85%' in original['excerpt'] and original['version']=='3.0'
    assert original['page_start'] is None and original['url'] is None

def test_unsafe_duplicate_and_missing_metadata_are_rejected():
    with pytest.raises(ValueError):bundle_records([row(),row()])
    with pytest.raises(ValueError):bundle_records([{**row(),'source_file':'../secret'}])
    with pytest.raises(ValueError):bundle_records([{k:v for k,v in row().items() if k!='version'}])

def test_invalid_embeddings_never_publish():
    for values in [np.zeros((1,768)),np.full((1,768),np.nan),np.ones((1,767))]:
        with pytest.raises(ValueError):normalized_matrix(values,1)

def test_pipeline_checkpoint_is_content_addressed_and_manifest_matches_rows(tmp_path):
    archive=tmp_path/'data.zip'
    def write(item):
        with zipfile.ZipFile(archive,'w') as z:z.writestr('chunks.jsonl',json.dumps(item)+'\n')
    calls=[]
    def embed(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0]*768) for _ in kwargs['contents']])
    client=SimpleNamespace(models=SimpleNamespace(embed_content=embed));write(row())
    kwargs={'output':tmp_path/'index','cache_dir':tmp_path/'cache','client':client}
    first=build(archive,**kwargs);second=build(archive,**kwargs)
    assert first['fresh_provider_batches']==1 and second['fresh_provider_batches']==0
    write({**row(),'text':'Changed content with a new rule.'});third=build(archive,**kwargs)
    assert len(calls)==2 and third['fresh_provider_batches']==1
    assert first['source_order']!=third['source_order']
    assert calls[0]['config'].task_type=='RETRIEVAL_DOCUMENT'
    assert np.allclose(np.linalg.norm(np.load(kwargs['output']/'vectors.npy',allow_pickle=False),axis=1),1)

def test_half_finished_answer_is_not_a_complete_response():
    with pytest.raises(ValueError):Answer.model_validate({'sections':[{'source_ids':[],'markdown':'Partial answer'}]})
    with pytest.raises(ValueError):Answer.model_validate({'sections':[],'complete':True})

@pytest.mark.asyncio
@pytest.mark.parametrize('intent',['catalogue','historical','focused'])
async def test_actual_corpus_retrieval_scope_and_required_coverage(intent):
    agent=object.__new__(UniversityAgent);data=Path(__file__).parents[1]/'data'
    agent.records=json.loads((data/'chunks.json').read_text());agent.vectors=np.load(data/'vectors.npy',allow_pickle=False)
    agent.bm25=BM25Okapi([r['embedding_text'].lower().split() for r in agent.records])
    async def embed(**_):return SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0]+[0.0]*767)])
    async def rank(_):return SimpleNamespace(ids=[])
    agent.client=SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(embed_content=embed)))
    agent.structured=lambda _:SimpleNamespace(ainvoke=rank)
    query='library fine' if intent=='focused' else intent
    result=await agent.retrieve(query,Plan(query=query,intent=intent))
    if intent=='catalogue':assert sum(r.get('is_programme',False) for r in result)==9
    if intent=='historical':assert {r['version'] for r in result if r['content_type']=='policy'}=={'3.0','2.1'}
    if intent=='focused':
        assert {'Library Hours and Fines','Library Borrowing','Frequently Asked Questions'} <= {r['section'] for r in result}
        assert all(not r['historical'] for r in result)
