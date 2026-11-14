/** Test-only metadata. Never imported by the shipped application. */
import { eventSchema, type ChatRequest, type RagEvent, type EvidenceSource } from '../src/lib/rag/protocol'
export const request: ChatRequest = { protocol_version: 1, conversation_id: 'test-conversation', request_id: 'test-request', message_id: 'test-answer', question: '[TEST] When does the fixture library open?', history: [] }
export const source: EvidenceSource = { source_id: 'fixture-source-1', document_id: 'fixture-document', chunk_id: 'fixture-chunk-1', citation_number: 1, title: '[TEST FIXTURE] Handbook', page_start: 2, section: 'Test section', url: '/test-documents/fixture-document', excerpt: '[TEST FIXTURE] The library opens at 09:00.' }
export function event(sequence: number, payload: Record<string, unknown>, target = request): RagEvent {
  return eventSchema.parse({ protocol_version: 1, conversation_id: target.conversation_id, request_id: target.request_id, message_id: target.message_id, run_id: `run-${target.request_id}`, sequence, ...payload })
}
export function happyEvents(target = request): RagEvent[] {
  return [
    { type: 'started' },
    { type: 'retrieval_started', retrieval_id: 'retrieval-1', label: '[TEST] Searching fixture documents' },
    { type: 'document_found', retrieval_id: 'retrieval-1', source },
    { type: 'document_reading', activity_id: 'read-1', document_id: source.document_id, source_ids: [source.source_id] },
    { type: 'document_processed', activity_id: 'read-1', document_id: source.document_id },
    { type: 'retrieval_completed', retrieval_id: 'retrieval-1', source_ids: [source.source_id] },
    { type: 'reasoning_update', activity_id: 'prepare', label: '[TEST] Preparing answer', status: 'running', summary: 'Fixture evidence checked.' },
    { type: 'answer_delta', block_id: 'claim-1', kind: 'grounded', source_ids: [source.source_id], delta: '[TEST FIXTURE] The library ' },
    { type: 'answer_delta', block_id: 'claim-1', kind: 'grounded', source_ids: [source.source_id], delta: 'opens at 09:00.' },
    { type: 'reasoning_update', activity_id: 'prepare', label: '[TEST] Prepared answer', status: 'completed' },
    { type: 'sources', sources: [source, source], final: true },
    { type: 'completed', outcome: 'answered', elapsed_ms: 173 },
  ].map((payload,index) => event(index+1,payload,target))
}
export const encode = (events: RagEvent[], ending = '\n') => events.map(e => `id: ${e.run_id}:${e.sequence}${ending}event: ${e.type}${ending}data: ${JSON.stringify(e)}${ending}${ending}`).join('')
