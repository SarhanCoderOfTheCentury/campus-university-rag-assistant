import asyncio
import pytest
import numpy as np
from types import SimpleNamespace
from rank_bm25 import BM25Okapi
from backend.ingest import normalize
from backend.university import Plan, Section, UniversityAgent
from backend.rag import GroundingError
from backend.protocol import Source

def test_ingestion_preserves_real_metadata_and_policy_scope():
    row={'id':'curated-test','document_file':'04_previous_policy.md','title':'History status','content':'No authenticated older policy exists.','source_url':None,'retrieval_policy':'historical_comparison_only_no_current_policy_answers'}
    records=normalize([row,row])
    assert len(records)==1
    assert records[0]['historical'] is True
    assert records[0]['document_id']=='04_previous_policy.md'
    assert records[0]['url'] is None and records[0]['page_start'] is None

@pytest.mark.asyncio
async def test_unknown_ids_never_reach_the_reviewer():
    agent=object.__new__(UniversityAgent)
    source=Source(source_id='source-1',document_id='doc-1',chunk_id='chunk-1',citation_number=1,excerpt='The fixture degree requires four years.')
    section=Section(source_ids=['unknown'],markdown='A claim.')
    with pytest.raises(GroundingError):await agent.verify(section,{'source-1':source})

@pytest.mark.asyncio
async def test_explicit_cancellation_stops_an_inflight_operation():
    agent=object.__new__(UniversityAgent)
    cleaned=asyncio.Event()
    async def check(_):return True
    async def slow(_):
        try:
            await asyncio.Event().wait()
            yield {}
        finally:cleaned.set()
    agent.cancelled=check
    agent._events=slow
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(anext(agent.events(object())),3)
    assert cleaned.is_set()

@pytest.mark.asyncio
async def test_catalogue_keeps_individual_programme_pages_not_partial_faq():
    agent=object.__new__(UniversityAgent)
    agent.records=[
        {'source_id':'cyber','document_id':'02_products_and_services.md','title':'BS Cyber Security','url':'https://example.invalid/cyber','curated':True,'historical':False,'embedding_text':'Cyber Security degree','content_type':None,'confidence':None},
        {'source_id':'ce','document_id':'02_products_and_services.md','title':'BS Computer Engineering','url':'https://example.invalid/ce','curated':True,'historical':False,'embedding_text':'Computer Engineering degree','content_type':None,'confidence':None},
        {'source_id':'faq','document_id':'faq','title':'Frequently Asked Questions','url':'https://example.invalid/faq','curated':False,'historical':False,'embedding_text':'Degree programmes old list','content_type':None,'confidence':None},
    ]
    agent.vectors=np.eye(3,768,dtype=np.float32)
    agent.bm25=BM25Okapi([r['embedding_text'].lower().split() for r in agent.records])
    async def embed(**_):return SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0]+[0.0]*767)])
    async def rank(_):return SimpleNamespace(ids=['faq','cyber'])
    agent.client=SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(embed_content=embed)))
    agent.structured=lambda _:SimpleNamespace(ainvoke=rank)
    records=await agent.retrieve('What programmes do you offer?',Plan(query='degree programmes',intent='catalogue'))
    assert {r['source_id'] for r in records}=={'cyber','ce'}
