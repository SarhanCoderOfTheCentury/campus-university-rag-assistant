from __future__ import annotations
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from dataclasses import dataclass
import inspect
from typing import Any
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable
from .protocol import ChatRequest, Source

class GroundingError(ValueError):
    """Unknown citation, unsupported claim, or invalid evidence metadata."""

Verifier = Callable[[str, list[Source]], bool | Awaitable[bool]]

def exact_quote_verifier(statement: str, sources: list[Source]) -> bool:
    """Fail-closed default: every emitted factual statement is an exact retrieved quote.
    Replace only with an actual tested entailment verifier for generated paraphrases.
    """
    return bool(statement.strip()) and any(statement in source.excerpt for source in sources)

@dataclass
class RagService:
    retriever: BaseRetriever
    # A streaming LCEL chain returning partial {'claims': [{'source_ids': [...], 'text': '...'}]} dictionaries.
    # Set its root run_name to 'grounded_answer'; JsonOutputParser supports these partial dictionaries.
    answer_chain: Runnable
    verify_claim: Verifier = exact_quote_verifier
    max_sources: int = 100

    async def events(self, request: ChatRequest) -> AsyncIterator[dict[str, Any]]:
        catalog: dict[str, Source] = {}
        keys: dict[tuple, str] = {}
        retrieval_id: str | None = None
        documents: list[Document] | None = None
        iterator = self.retriever.astream_events(request.question, version='v2')
        async with aclosing(iterator):
            async for event in iterator:
                if event['event'] == 'on_retriever_start' and not event.get('parent_ids'):
                    retrieval_id = str(event['run_id'])
                    yield {'type': 'retrieval_started', 'retrieval_id': retrieval_id, 'label': 'Searching university documents'}
                elif event['event'] == 'on_retriever_end' and str(event['run_id']) == retrieval_id:
                    documents = list(event['data']['output'])
        if retrieval_id is None or documents is None:
            raise GroundingError('Retriever did not provide the documented LangChain retrieval events')

        context: list[dict[str, Any]] = []
        for document in documents[:self.max_sources]:
            if not isinstance(document, Document):
                raise GroundingError('Retriever returned an invalid document')
            if not document.page_content.strip():
                continue
            # These identifiers must be established by ingestion, never extracted from LLM text.
            metadata = document.metadata
            for name in ('source_id', 'document_id', 'chunk_id'):
                if not isinstance(metadata.get(name), str) or not metadata[name]:
                    raise GroundingError(f'Missing authoritative {name}')
            source_id = metadata['source_id']
            number = catalog[source_id].citation_number if source_id in catalog else len(catalog) + 1
            source = Source(
                source_id=source_id, document_id=metadata['document_id'], chunk_id=metadata['chunk_id'], citation_number=number,
                title=metadata.get('title'), url=metadata.get('url'), page_start=metadata.get('page_start'),
                page_end=metadata.get('page_end'), section=metadata.get('section'), excerpt=document.page_content[:16000],
            )
            identity = (source.document_id, source.chunk_id, source.page_start, source.page_end, source.section)
            if source_id in catalog:
                if catalog[source_id] != source:
                    raise GroundingError('Source metadata changed during a request')
                continue
            if identity in keys:
                raise GroundingError('The same evidence chunk was assigned different source IDs')
            keys[identity] = source_id
            catalog[source_id] = source
            serialized = source.model_dump(exclude_none=True)
            yield {'type': 'document_found', 'retrieval_id': retrieval_id, 'source': serialized}
            activity_id = f'read:{source.source_id}'
            yield {'type': 'document_reading', 'activity_id': activity_id, 'document_id': source.document_id, 'source_ids': [source_id], 'detail': 'Preparing the retrieved passage for the answer context.'}
            # This actual context preparation is the reading operation shown above.
            context.append(serialized)
            yield {'type': 'document_processed', 'activity_id': activity_id, 'document_id': source.document_id, 'detail': 'Retrieved passage included in the answer context.'}
        yield {'type': 'retrieval_completed', 'retrieval_id': retrieval_id, 'source_ids': list(catalog), 'summary': f'Retrieved {len(catalog)} distinct evidence passages.'}
        if not catalog:
            yield {'type': 'answer_delta', 'block_id': 'no-evidence', 'kind': 'notice', 'source_ids': [], 'delta': 'I could not find supporting university documents for this question. Please ask your department or try a more specific question.'}
            yield {'type': 'sources', 'sources': [], 'final': True}
            yield {'type': 'completed', 'outcome': 'no_evidence'}
            return

        yield {'type': 'reasoning_update', 'activity_id': 'prepare-answer', 'label': 'Preparing a source-grounded response', 'status': 'running', 'summary': f'Using {len(catalog)} retrieved passages. Only verified claims can be displayed.'}
        emitted: dict[int, tuple[str, list[str]]] = {}
        custom_status: dict[str, str] = {}
        iterator = self.answer_chain.astream_events({
            'question': request.question,
            'history': [message.model_dump() for message in request.history],
            'evidence': context,
        }, version='v2')
        async with aclosing(iterator):
            async for event in iterator:
                if event['event'] == 'on_custom_event' and event['name'] == 'campus_activity':
                    # Explicit user-facing activity only. Never forward raw model reasoning tokens.
                    data = event['data']
                    activity_id = data.get('activity_id')
                    if not isinstance(activity_id, str) or activity_id == 'prepare-answer':
                        raise GroundingError('Invalid custom activity identity')
                    custom_status[activity_id] = data.get('status')
                    yield {'type': 'reasoning_update', **{key: data[key] for key in ('activity_id', 'label', 'status', 'summary') if key in data}}
                elif event['event'] in ('on_chain_stream', 'on_chain_end') and event['name'] == 'grounded_answer' and not event.get('parent_ids'):
                    partial = event['data'].get('chunk') if event['event'] == 'on_chain_stream' else event['data'].get('output')
                    if not isinstance(partial, dict) or not isinstance(partial.get('claims'), list):
                        continue
                    for index, claim in enumerate(partial['claims']):
                        if not isinstance(claim, dict) or not isinstance(claim.get('text'), str):
                            continue # A real structured-output parser may not have received the text key yet.
                        statement = claim['text']
                        if not statement:
                            continue
                        source_ids = claim.get('source_ids')
                        if not isinstance(source_ids, list) or not source_ids or any(not isinstance(value, str) or value not in catalog for value in source_ids):
                            raise GroundingError('An answer referenced evidence not returned by retrieval')
                        source_ids = list(dict.fromkeys(source_ids))
                        previous_text, previous_ids = emitted.get(index, ('', source_ids))
                        if not statement.startswith(previous_text) or source_ids != previous_ids:
                            raise GroundingError('A streamed claim changed its earlier text or citation IDs')
                        if statement == previous_text:
                            continue
                        valid = self.verify_claim(statement, [catalog[value] for value in source_ids])
                        if inspect.isawaitable(valid):
                            valid = await valid
                        if valid is not True:
                            raise GroundingError('A generated statement was not supported by its cited evidence')
                        # No artificial token splitting or sleeps: emit only genuinely new verified text.
                        yield {'type': 'answer_delta', 'block_id': f'claim-{index}', 'kind': 'grounded', 'source_ids': source_ids, 'delta': statement[len(previous_text):]}
                        emitted[index] = (statement, source_ids)
        if not emitted:
            raise GroundingError('The answer chain returned no verified claims')
        if any(status != 'completed' for status in custom_status.values()):
            raise GroundingError('A custom backend activity did not complete successfully')
        yield {'type': 'reasoning_update', 'activity_id': 'prepare-answer', 'label': 'Prepared a source-grounded response', 'status': 'completed', 'summary': f'Verified {len(emitted)} answer passages against retrieved evidence.'}
        used = {source_id for _, source_ids in emitted.values() for source_id in source_ids}
        yield {'type': 'sources', 'sources': [source.model_dump(exclude_none=True) for source in catalog.values() if source.source_id in used], 'final': True}
        yield {'type': 'completed', 'outcome': 'answered'}
