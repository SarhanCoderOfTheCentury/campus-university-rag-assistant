from __future__ import annotations
import asyncio
from collections.abc import AsyncIterable, Callable
from contextlib import aclosing
import importlib
import inspect
import logging
import os
from time import monotonic
from typing import Any
from uuid import uuid4
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.sse import EventSourceResponse, ServerSentEvent
from .protocol import ChatRequest, wire_event_adapter
from .rag import RagService, GroundingError

logger = logging.getLogger(__name__)

def load_callable(value: str | None) -> Callable | None:
    if not value:
        return None
    module, separator, name = value.partition(':')
    if not separator:
        raise RuntimeError('Factory settings must use module:function')
    result = getattr(importlib.import_module(module), name)
    if not callable(result):
        raise RuntimeError('Configured factory is not callable')
    return result

async def resolve(value: Any):
    return await value if inspect.isawaitable(value) else value

# Both hooks are server-side. Authentication and document ACLs belong to your deployment.
def create_app(*, service_factory: Callable | None = None, authorize: Callable | None = None) -> FastAPI:
    app = FastAPI(title='Campus RAG event API', version='1.0.0')
    app.state.service_factory = service_factory
    app.state.authorize = authorize
    origins = [value.strip() for value in os.getenv('RAG_ALLOWED_ORIGINS', '').split(',') if value.strip()]
    if '*' in origins:
        raise RuntimeError('Configure exact allowed frontend origins')
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=['POST'], allow_headers=['Content-Type', 'Authorization'], expose_headers=['Content-Type'])

    async def authorized_service(request: Request) -> RagService:
        factory = app.state.service_factory or load_callable(os.getenv('RAG_FACTORY'))
        auth = app.state.authorize or load_callable(os.getenv('RAG_AUTH_FACTORY'))
        if factory is None or auth is None:
            raise HTTPException(503, 'The real university RAG service and authorization hooks are not configured.')
        # The caller's identity must be used by the retriever to apply document access controls.
        principal = await resolve(auth(request))
        if principal is None:
            raise HTTPException(401, 'Authentication required')
        service = await resolve(factory(principal))
        if not isinstance(service, RagService):
            raise HTTPException(503, 'The configured RAG factory is invalid')

        return service

    @app.post('/api/chat/stream', response_class=EventSourceResponse)
    async def chat(body: ChatRequest, service: RagService = Depends(authorized_service)) -> AsyncIterable[ServerSentEvent]:
        run_id = str(uuid4())
        sequence = 0
        start = monotonic()
        def encode(payload: dict) -> ServerSentEvent:
            nonlocal sequence
            sequence += 1
            envelope = {'protocol_version': 1, 'conversation_id': body.conversation_id, 'request_id': body.request_id, 'message_id': body.message_id, 'run_id': run_id, 'sequence': sequence, **payload}
            if payload['type'] == 'completed':
                envelope['elapsed_ms'] = int((monotonic() - start) * 1000)
            validated = wire_event_adapter.validate_python(envelope)
            return ServerSentEvent(event=validated.type, id=f'{run_id}:{sequence}', data=validated.model_dump(exclude_none=True))
        yield encode({'type': 'started'})
        try:
            async with asyncio.timeout(300):
                # aclosing propagates disconnect/cancellation through retriever and model streams.
                async with aclosing(service.events(body)) as events:
                    async for payload in events:
                        yield encode(payload)
        except asyncio.CancelledError:
            raise # Disconnected client: clean up; do not invent a successful completion.
        except TimeoutError:
            yield encode({'type': 'error', 'code': 'timeout', 'message': 'The university assistant exceeded its processing time. Partial results are preserved.'})
        except GroundingError:
            logger.warning('RAG grounding validation failed for run %s', run_id)
            yield encode({'type': 'error', 'code': 'grounding_failed', 'message': 'The agent could not verify this response against its retrieved documents. Partial verified passages are preserved.'})
        except Exception as exc:
            # Do not send provider errors, stack traces, tokens, or raw internal reasoning to the browser.
            logger.error('RAG processing failed for run %s: %s (status %s)', run_id, type(exc).__name__, getattr(exc,'code',None))
            limited='RateLimit' in type(exc).__name__ or getattr(exc,'code',None)==429
            yield encode({'type': 'error', 'code': 'provider_rate_limit' if limited else 'processing_failed', 'message': 'The AI provider is temporarily rate-limited. Please try again shortly. Partial results are preserved.' if limited else 'The university assistant could not complete this request. Partial results are preserved.'})
    return app

app = create_app()
