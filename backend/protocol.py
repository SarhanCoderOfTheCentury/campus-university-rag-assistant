from __future__ import annotations
from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

Identifier = Annotated[str, Field(min_length=1, max_length=200, pattern=r'^[^\x00-\x1f\x7f]+$')]
ShortText = Annotated[str, Field(max_length=32000)]
SourceIds = Annotated[list[Identifier], Field(max_length=500)]

class Source(StrictModel):
    source_id: Identifier
    document_id: Identifier
    chunk_id: Identifier
    citation_number: int = Field(ge=1, le=5000)
    title: str | None = Field(default=None, min_length=1, max_length=1000)
    url: str | None = Field(default=None, max_length=4000)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, min_length=1, max_length=1000)
    excerpt: str = Field(min_length=1, max_length=16000)

    @model_validator(mode='after')
    def page_range(self):
        if self.page_end is not None and (self.page_start is None or self.page_end < self.page_start):
            raise ValueError('Invalid page range')
        return self

class HistoryMessage(StrictModel):
    role: Literal['user', 'assistant']
    content: str = Field(max_length=100000)

class ChatRequest(StrictModel):
    protocol_version: Literal[1]
    conversation_id: Identifier
    request_id: Identifier
    message_id: Identifier
    question: str = Field(min_length=1, max_length=8000)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=40)

class Envelope(StrictModel):
    protocol_version: Literal[1] = 1
    conversation_id: Identifier
    request_id: Identifier
    message_id: Identifier
    run_id: Identifier
    sequence: int = Field(ge=1)

class Started(Envelope):
    type: Literal['started']
class RetrievalStarted(Envelope):
    type: Literal['retrieval_started']
    retrieval_id: Identifier
    label: ShortText = Field(min_length=1)
    detail: ShortText | None = None
class DocumentFound(Envelope):
    type: Literal['document_found']
    retrieval_id: Identifier
    source: Source
class DocumentReading(Envelope):
    type: Literal['document_reading']
    activity_id: Identifier
    document_id: Identifier
    source_ids: SourceIds = Field(min_length=1)
    detail: ShortText | None = None
class DocumentProcessed(Envelope):
    type: Literal['document_processed']
    activity_id: Identifier
    document_id: Identifier
    detail: ShortText | None = None
class RetrievalCompleted(Envelope):
    type: Literal['retrieval_completed']
    retrieval_id: Identifier
    source_ids: SourceIds
    summary: ShortText | None = None
class ReasoningUpdate(Envelope):
    type: Literal['reasoning_update']
    activity_id: Identifier
    label: ShortText = Field(min_length=1)
    status: Literal['running', 'completed', 'failed']
    summary: ShortText | None = None
class AnswerDelta(Envelope):
    type: Literal['answer_delta']
    block_id: Identifier
    delta: ShortText = Field(min_length=1)
    source_ids: SourceIds
    kind: Literal['grounded', 'notice']
class Sources(Envelope):
    type: Literal['sources']
    sources: list[Source] = Field(max_length=500)
    final: bool
class Completed(Envelope):
    type: Literal['completed']
    outcome: Literal['answered', 'no_evidence', 'clarification']
    elapsed_ms: int | None = Field(default=None, ge=0)
class Error(Envelope):
    type: Literal['error']
    code: str = Field(min_length=1, max_length=100)
    message: ShortText = Field(min_length=1)

WireEvent = Annotated[Union[Started, RetrievalStarted, DocumentFound, DocumentReading, DocumentProcessed, RetrievalCompleted, ReasoningUpdate, AnswerDelta, Sources, Completed, Error], Field(discriminator='type')]
wire_event_adapter = TypeAdapter(WireEvent)
