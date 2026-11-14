from __future__ import annotations
import asyncio
import json
from pathlib import Path
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnableLambda
from langchain_core.callbacks.manager import adispatch_custom_event
from pydantic import Field
import pytest
from httpx import ASGITransport, AsyncClient
from backend.main import create_app
from backend.protocol import ChatRequest, Source, wire_event_adapter
from backend.rag import GroundingError, RagService, exact_quote_verifier

TEXT = '[TEST FIXTURE] The library opens at 09:00.'
META = {'source_id': 'fixture-source-1', 'document_id': 'fixture-document', 'chunk_id': 'fixture-chunk-1', 'title': '[TEST FIXTURE] Handbook', 'page_start': 2, 'section': 'Fixture section', 'url': '/test-documents/fixture-document'}
REQUEST = ChatRequest(protocol_version=1, conversation_id='fixture-conversation', request_id='fixture-request', message_id='fixture-message', question='[TEST] What does this test passage say?', history=[])

class FixtureRetriever(BaseRetriever):
    documents: list[Document] = Field(default_factory=list)
    def _get_relevant_documents(self, query, *, run_manager):
        return self.documents

def service_for(documents=None, *, text=TEXT, source_ids=None):
    async def answer(_):
        # Genuine LCEL streaming fixture: no sleeps, timers or pretend retrieval events.
        for value in (text[:25], text):
            yield {'claims': [{'source_ids': source_ids or ['fixture-source-1'], 'text': value}]}
    return RagService(FixtureRetriever(documents=documents if documents is not None else [Document(page_content=TEXT, metadata=META)]), RunnableLambda(answer).with_config(run_name='grounded_answer'))

@pytest.mark.asyncio
async def test_real_langchain_callbacks_map_to_grounded_sse_events():
    service=service_for()
    events=[event async for event in service.events(REQUEST)]
    types=[event['type'] for event in events]
    assert types[0]=='retrieval_started'
    assert types.index('document_found')<types.index('document_reading')<types.index('document_processed')<types.index('retrieval_completed')
    assert ''.join(e['delta'] for e in events if e['type']=='answer_delta')==TEXT
    assert types[-1]=='completed'
    assert events[-2]['sources'][0]['source_id']==META['source_id']
    assert events[-2]['sources'][0]['page_start']==2
    assert events[-2]['sources'][0]['url']==META['url']
    assert [e['source_ids'] for e in events if e['type']=='answer_delta']==[['fixture-source-1'],['fixture-source-1']]

@pytest.mark.asyncio
async def test_no_documents_does_not_run_model_or_invent_sources():
    called=False
    async def unexpected(_):
        nonlocal called
        called=True
        raise AssertionError('Model must not be invoked without evidence')
    service=RagService(FixtureRetriever(), RunnableLambda(unexpected).with_config(run_name='grounded_answer'))
    events=[e async for e in service.events(REQUEST)]
    assert not called
    assert events[-1]=={'type':'completed','outcome':'no_evidence'}
    assert events[-2]=={'type':'sources','sources':[],'final':True}
    assert not any(e['type']=='document_found' for e in events)

@pytest.mark.asyncio
async def test_source_metadata_must_come_from_ingestion():
    bad=Document(page_content=TEXT,metadata={'title':'Guessed handbook'})
    with pytest.raises(GroundingError,match='authoritative'):
        _=[e async for e in service_for([bad]).events(REQUEST)]

@pytest.mark.asyncio
@pytest.mark.parametrize('text,ids',[(TEXT,['not-retrieved']),('[TEST] Unsupported invented policy.',['fixture-source-1'])])
async def test_unknown_citations_and_unsupported_claims_fail_closed(text,ids):
    emitted=[]
    with pytest.raises(GroundingError):
        async for e in service_for(text=text,source_ids=ids).events(REQUEST):
            emitted.append(e)
    assert not any(e['type']=='completed' for e in emitted)
    assert not any(e['type']=='answer_delta' for e in emitted)

@pytest.mark.asyncio
async def test_deduplication_keeps_distinct_page_chunk_locations():
    documents=[Document(page_content=TEXT,metadata=META),Document(page_content=TEXT,metadata=META),Document(page_content='[TEST] Another page.',metadata={**META,'source_id':'fixture-source-2','chunk_id':'fixture-chunk-2','page_start':3})]
    events=[e async for e in service_for(documents).events(REQUEST)]
    sources=[e['source'] for e in events if e['type']=='document_found']
    assert len(sources)==2
    assert [s['page_start'] for s in sources]==[2,3]
    assert [s['citation_number'] for s in sources]==[1,2]

@pytest.mark.asyncio
async def test_only_explicit_safe_custom_activity_is_forwarded():
    async def answer(_,config):
        await adispatch_custom_event('campus_activity', {'activity_id':'compare','label':'[TEST] Comparing fixture passages','status':'running','summary':'A public activity summary.'},config=config)
        await adispatch_custom_event('private_reasoning', {'secret':'never publish'},config=config)
        yield {'claims':[{'source_ids':['fixture-source-1'],'text':TEXT}]}
        await adispatch_custom_event('campus_activity', {'activity_id':'compare','label':'[TEST] Compared fixture passages','status':'completed'},config=config)
    service=service_for();service.answer_chain=RunnableLambda(answer).with_config(run_name='grounded_answer')
    events=[e async for e in service.events(REQUEST)]
    assert any(e.get('activity_id')=='compare' for e in events)
    assert 'never publish' not in json.dumps(events)

@pytest.mark.asyncio
async def test_closing_a_stream_closes_underlying_langchain_generator():
    closed=asyncio.Event()
    async def answer(_):
        try:
            yield {'claims':[{'source_ids':['fixture-source-1'],'text':TEXT[:25]}]}
            yield {'claims':[{'source_ids':['fixture-source-1'],'text':TEXT}]}
        finally:closed.set()
    service=service_for();service.answer_chain=RunnableLambda(answer).with_config(run_name='grounded_answer')
    stream=service.events(REQUEST)
    async for e in stream:
        if e['type']=='answer_delta':break
    await stream.aclose()
    await asyncio.wait_for(closed.wait(),timeout=2)

@pytest.mark.asyncio
async def test_unconfigured_backend_returns_503_without_faked_activity(monkeypatch):
    monkeypatch.delenv('RAG_FACTORY',raising=False);monkeypatch.delenv('RAG_AUTH_FACTORY',raising=False)
    async with AsyncClient(transport=ASGITransport(app=create_app()),base_url='http://test') as client:
        response=await client.post('/api/chat/stream',json=REQUEST.model_dump())
    assert response.status_code==503
    assert 'retrieval_started' not in response.text

@pytest.mark.asyncio
async def test_authorization_and_document_scope_are_required():
    seen=[]
    async def auth(_):return {'user_id':'fixture-student','allowed_collection':'fixture'}
    def factory(principal):seen.append(principal);return service_for()
    app=create_app(service_factory=factory,authorize=auth)
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response=await client.post('/api/chat/stream',json=REQUEST.model_dump())
    assert response.status_code==200
    assert seen[0]['user_id']=='fixture-student'
    assert response.headers['content-type'].startswith('text/event-stream')
    assert response.headers['x-accel-buffering']=='no'
    wire=[]
    for block in response.text.replace('\r\n','\n').strip().split('\n\n'):
        if not block or block.startswith(':'):continue
        fields=dict(line.split(': ',1) for line in block.split('\n') if ': ' in line)
        if 'data' not in fields:continue
        data=json.loads(fields['data']);parsed=wire_event_adapter.validate_python(data)
        assert fields['event']==parsed.type
        assert fields['id']==f'{parsed.run_id}:{parsed.sequence}'
        wire.append(data)
    assert wire[0]['type']=='started'
    assert wire[-1]['type']=='completed'
    assert [e['sequence'] for e in wire]==list(range(1,len(wire)+1))
    assert all(e['request_id']==REQUEST.request_id for e in wire)
    assert all(e['message_id']==REQUEST.message_id for e in wire)
    assert all(e['conversation_id']==REQUEST.conversation_id for e in wire)
    # Golden backend output is validated against the actual frontend schema by Vitest.
    target=Path(__file__).resolve().parents[2]/'tests'/'backend-wire.generated.json'
    normalized=[{**item, 'run_id':'fixture-backend-run', **({'elapsed_ms':0} if item['type']=='completed' else {})} for item in wire]
    target.write_text(json.dumps(normalized,ensure_ascii=False,indent=2)+'\n')

@pytest.mark.asyncio
async def test_processing_errors_do_not_leak_provider_details():
    async def broken(_):raise RuntimeError('sk-private-provider-key-must-not-leak')
    service=service_for();service.answer_chain=RunnableLambda(broken).with_config(run_name='grounded_answer')
    app=create_app(service_factory=lambda _:service,authorize=lambda _:{'id':'test-only'})
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response=await client.post('/api/chat/stream',json=REQUEST.model_dump())
    assert 'processing_failed' in response.text
    assert 'sk-private-provider' not in response.text
    assert '"type":"completed"' not in response.text

@pytest.mark.asyncio
async def test_auth_denial_does_not_invoke_retrieval():
    invoked=False
    def factory(_):
        nonlocal invoked
        invoked=True
        return service_for()
    app=create_app(service_factory=factory,authorize=lambda _:None)
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response=await client.post('/api/chat/stream',json=REQUEST.model_dump())
    assert response.status_code==401 and not invoked

def test_exact_quote_verifier_rejects_added_facts():
    source=Source(**META,citation_number=1,excerpt=TEXT)
    assert exact_quote_verifier(TEXT,[source])
    assert not exact_quote_verifier(TEXT+' Attendance must be 75%.',[source])


@pytest.mark.asyncio
async def test_example_factory_streams_real_incremental_json_parser():
    """Exercise the actual documented chain wiring, with an explicit test-only model."""
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from backend.example_factory import wire_service
    document = Document(page_content=TEXT, metadata=META)
    response = json.dumps({'claims': [{'source_ids': [document.metadata['source_id']], 'text': document.page_content}]})
    service = wire_service(FixtureRetriever(documents=[document]), FakeListChatModel(responses=[response]))
    events = [event async for event in service.events(REQUEST)]
    deltas = [event for event in events if event['type'] == 'answer_delta']
    assert len(deltas) > 1
    assert ''.join(event['delta'] for event in deltas) == document.page_content
    assert all(event['source_ids'] == [document.metadata['source_id']] for event in deltas)
    assert events[-1] == {'type': 'completed', 'outcome': 'answered'}
