import { protocolError, type ChatRequest, type EvidenceSource, type RagEvent } from './protocol'

export type RunStatus = 'connecting' | 'processing' | 'answering' | 'completed' | 'failed' | 'interrupted' | 'cancelled'
export type Activity = {
  id: string; kind: 'retrieval' | 'document' | 'discovery' | 'summary'; label: string
  status: 'running' | 'completed' | 'failed' | 'interrupted'
  detail?: string; documentId?: string; sourceIds?: string[]
}
export type AnswerBlock = { id: string; text: string; sourceIds: string[]; kind: 'grounded' | 'notice' }
export type RagRun = {
  request: ChatRequest; runId?: string; sequence: number; status: RunStatus
  activities: Activity[]; sources: Record<string, EvidenceSource>; blocks: AnswerBlock[]
  selectedSourceIds: string[]; sourcesFinal: boolean; reasoningOpen: boolean
  outcome?: 'answered' | 'no_evidence' | 'clarification'; elapsedMs?: number
  error?: { code: string; message: string }
}
export const isRunning = (run: RagRun) => ['connecting', 'processing', 'answering'].includes(run.status)
export const createRun = (request: ChatRequest): RagRun => ({ request, sequence: 0, status: 'connecting', activities: [], sources: {}, blocks: [], selectedSourceIds: [], sourcesFinal: false, reasoningOpen: true })
export const sourceLocation = (s: EvidenceSource) => [s.page_start !== undefined ? `p. ${s.page_start}${s.page_end !== undefined && s.page_end !== s.page_start ? `–${s.page_end}` : ''}` : undefined, s.section].filter(Boolean).join(' · ')
export const sourceTitle = (s: EvidenceSource) => s.title ?? 'Document title not provided'
export const referencedSources = (run: RagRun) => [...new Set(run.blocks.flatMap(b => b.sourceIds))].filter(id => Object.hasOwn(run.sources, id)).map(id => run.sources[id]).sort((a,b) => a.citation_number - b.citation_number)
const sourceKey = (s: EvidenceSource) => JSON.stringify([s.document_id, s.chunk_id, s.page_start, s.page_end, s.section])
function register(catalog: Record<string, EvidenceSource>, incoming: EvidenceSource): Record<string, EvidenceSource> {
  const old = Object.hasOwn(catalog, incoming.source_id) ? catalog[incoming.source_id] : undefined
  if (old) {
    if (JSON.stringify(old) !== JSON.stringify(incoming)) protocolError('The agent changed previously registered source metadata.')
    return catalog
  }
  if (Object.values(catalog).some(s => s.citation_number === incoming.citation_number || sourceKey(s) === sourceKey(incoming))) protocolError('The agent supplied conflicting or duplicate source identities.')
  if (Object.keys(catalog).length >= 500) protocolError('The agent exceeded the source limit.')
  return { ...catalog, [incoming.source_id]: incoming }
}
function requireSources(run: RagRun, ids: string[]) {
  if (new Set(ids).size !== ids.length || ids.some(id => !Object.hasOwn(run.sources, id))) protocolError('The agent referenced an unknown or duplicated source ID.')
}
function activity(run: RagRun, update: Activity): Activity[] {
  const index = run.activities.findIndex(a => a.id === update.id)
  if (index < 0) {
    if (run.activities.length >= 1000) protocolError('The agent exceeded the activity limit.')
    return [...run.activities, update]
  }
  const old = run.activities[index]
  if (old.kind !== update.kind || (old.status !== 'running' && update.status === 'running')) protocolError('The agent sent an invalid activity transition.')
  return run.activities.map((a,i) => i === index ? { ...a, ...update } : a)
}
export function stopRun(run: RagRun, status: 'failed' | 'interrupted' | 'cancelled', code: string, message: string): RagRun {
  if (!isRunning(run)) return run
  return { ...run, status, reasoningOpen: true, error: { code, message }, activities: run.activities.map(a => a.status === 'running' ? { ...a, status: 'interrupted' } : a) }
}

/** Pure event reducer: no timers, inferred progress, generated citations, or guessed stages. */
export function applyEvent(run: RagRun, event: RagEvent): RagRun {
  if (!isRunning(run)) return run
  const r = run.request
  if (event.request_id !== r.request_id || event.conversation_id !== r.conversation_id || event.message_id !== r.message_id) protocolError('An event belonged to a different request.')
  if (event.sequence <= run.sequence) return run // Replayed SSE events are idempotent.
  if (event.sequence !== run.sequence + 1) protocolError('An activity event was lost or arrived out of order.')
  if (run.runId && event.run_id !== run.runId) protocolError('An event belonged to a different agent run.')
  if (!run.runId && event.type !== 'started') protocolError('The stream did not begin with a started event.')
  if (run.runId && event.type === 'started') protocolError('The agent restarted an existing run.')
  let next = { ...run, runId: event.run_id, sequence: event.sequence }
  switch (event.type) {
    case 'started': return { ...next, status: 'processing' }
    case 'retrieval_started':
      return { ...next, activities: activity(next, { id: `retrieval:${event.retrieval_id}`, kind: 'retrieval', label: event.label, detail: event.detail, status: 'running' }) }
    case 'document_found': {
      const search = next.activities.find(a => a.id === `retrieval:${event.retrieval_id}` && a.status === 'running')
      if (!search) protocolError('A document arrived without an active retrieval operation.')
      const sources = register(next.sources, event.source)
      const foundId = `found:${event.source.document_id}`
      const previous = next.activities.find(a => a.id === foundId)
      return { ...next, sources, activities: activity(next, { id: foundId, kind: 'discovery', label: `Found ${sourceTitle(event.source)}`, status: 'completed', documentId: event.source.document_id, sourceIds: [...new Set([...(previous?.sourceIds ?? []), event.source.source_id])] }) }
    }
    case 'document_reading': {
      requireSources(next, event.source_ids)
      if (event.source_ids.some(id => next.sources[id].document_id !== event.document_id)) protocolError('Document and evidence IDs did not match.')
      const previous = next.activities.find(a => a.id === `document:${event.activity_id}`)
      if (previous && (previous.documentId !== event.document_id || JSON.stringify(previous.sourceIds) !== JSON.stringify(event.source_ids))) protocolError('A reading activity changed its document or evidence identity.')
      const source = next.sources[event.source_ids[0]]
      return { ...next, activities: activity(next, { id: `document:${event.activity_id}`, kind: 'document', status: 'running', label: sourceTitle(source), detail: event.detail, documentId: event.document_id, sourceIds: event.source_ids }) }
    }
    case 'document_processed': {
      const previous = next.activities.find(a => a.id === `document:${event.activity_id}` && a.documentId === event.document_id && a.status === 'running')
      if (!previous) protocolError('A document completion had no matching reading operation.')
      return { ...next, activities: activity(next, { ...previous, status: 'completed', detail: event.detail ?? previous.detail }) }
    }
    case 'retrieval_completed': {
      requireSources(next, event.source_ids)
      const previous = next.activities.find(a => a.id === `retrieval:${event.retrieval_id}` && a.status === 'running')
      if (!previous) protocolError('Retrieval completion had no matching operation.')
      return { ...next, activities: activity(next, { ...previous, status: 'completed', detail: event.summary ?? previous.detail, sourceIds: event.source_ids }) }
    }
    case 'reasoning_update':
      return { ...next, activities: activity(next, { id: `summary:${event.activity_id}`, kind: 'summary', label: event.label, detail: event.summary, status: event.status }) }
    case 'answer_delta': {
      requireSources(next, event.source_ids)
      if (event.kind === 'grounded' && !event.source_ids.length) protocolError('A document-grounded answer block had no source references.')
      if (event.kind === 'notice' && event.source_ids.length) protocolError('A notice cannot contain document evidence.')
      const index = next.blocks.findIndex(b => b.id === event.block_id)
      const previous = next.blocks[index]
      if (previous && (previous.kind !== event.kind || JSON.stringify(previous.sourceIds) !== JSON.stringify(event.source_ids))) protocolError('The agent changed the evidence for an answer block.')
      if (next.blocks.length >= 500 && !previous) protocolError('The agent exceeded the answer block limit.')
      if (next.blocks.reduce((size,b) => size+b.text.length, 0) + event.delta.length > 1000000) protocolError('The agent exceeded the answer length limit.')
      const block: AnswerBlock = { id: event.block_id, kind: event.kind, text: (previous?.text ?? '') + event.delta, sourceIds: event.source_ids }
      return { ...next, status: 'answering', blocks: previous ? next.blocks.map((b,i) => i === index ? block : b) : [...next.blocks, block] }
    }
    case 'sources': {
      let sources = next.sources
      for (const source of event.sources) sources = register(sources, source)
      if (next.sourcesFinal) protocolError('Sources were updated after finalization.')
      return { ...next, sources, sourcesFinal: event.final, selectedSourceIds: [...new Set(event.sources.map(s => s.source_id))] }
    }
    case 'completed': {
      const referenced = referencedSources(next).map(s => s.source_id).sort()
      if (!next.sourcesFinal || JSON.stringify(referenced) !== JSON.stringify([...next.selectedSourceIds].sort())) protocolError('Final source references did not match the answer citations.')
      if (next.activities.some(a => a.status === 'running' || a.status === 'failed')) protocolError('The agent completed while an activity was unfinished or failed.')
      if (event.outcome === 'answered' && !referenced.length) protocolError('The answer did not cite any retrieved evidence.')
      if (event.outcome !== 'answered' && referenced.length) protocolError('The response outcome contradicted its evidence.')
      if (!next.blocks.some(b => b.text.trim())) protocolError('The agent completed without a response.')
      return { ...next, status: 'completed', outcome: event.outcome, elapsedMs: event.elapsed_ms, reasoningOpen: false }
    }
    case 'error': return stopRun(next, 'failed', event.code, event.message)
  }
}
