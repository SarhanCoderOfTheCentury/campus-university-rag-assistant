import { z } from 'zod'

const id = z.string().min(1).max(200).regex(/^[^\u0000-\u001f\u007f]+$/)
const text = z.string().max(32000)
const ids = z.array(id).max(500)
export const sourceSchema = z.object({
  source_id: id,
  document_id: id,
  chunk_id: id,
  citation_number: z.number().int().min(1).max(5000),
  title: z.string().min(1).max(1000).optional(),
  url: z.string().max(4000).optional(),
  page_start: z.number().int().positive().optional(),
  page_end: z.number().int().positive().optional(),
  section: z.string().min(1).max(1000).optional(),
  excerpt: z.string().min(1).max(16000),
}).strict().refine(s => s.page_end === undefined || (s.page_start !== undefined && s.page_end >= s.page_start), 'Invalid page range')
export type EvidenceSource = z.infer<typeof sourceSchema>

const envelope = {
  protocol_version: z.literal(1), conversation_id: id, request_id: id,
  message_id: id, run_id: id, sequence: z.number().int().positive(),
}
const activityStatus = z.enum(['running', 'completed', 'failed'])
export const eventSchema = z.discriminatedUnion('type', [
  z.object({ ...envelope, type: z.literal('started') }).strict(),
  z.object({ ...envelope, type: z.literal('retrieval_started'), retrieval_id: id, label: text.min(1), detail: text.optional() }).strict(),
  z.object({ ...envelope, type: z.literal('document_found'), retrieval_id: id, source: sourceSchema }).strict(),
  z.object({ ...envelope, type: z.literal('document_reading'), activity_id: id, document_id: id, source_ids: ids.min(1), detail: text.optional() }).strict(),
  z.object({ ...envelope, type: z.literal('document_processed'), activity_id: id, document_id: id, detail: text.optional() }).strict(),
  z.object({ ...envelope, type: z.literal('retrieval_completed'), retrieval_id: id, source_ids: ids, summary: text.optional() }).strict(),
  z.object({ ...envelope, type: z.literal('reasoning_update'), activity_id: id, label: text.min(1), status: activityStatus, summary: text.optional() }).strict(),
  z.object({ ...envelope, type: z.literal('answer_delta'), block_id: id, delta: text.min(1), source_ids: ids, kind: z.enum(['grounded', 'notice']) }).strict(),
  z.object({ ...envelope, type: z.literal('sources'), sources: z.array(sourceSchema).max(500), final: z.boolean() }).strict(),
  z.object({ ...envelope, type: z.literal('completed'), outcome: z.enum(['answered', 'no_evidence', 'clarification']), elapsed_ms: z.number().int().nonnegative().optional() }).strict(),
  z.object({ ...envelope, type: z.literal('error'), code: z.string().min(1).max(100), message: text.min(1) }).strict(),
])
export type RagEvent = z.infer<typeof eventSchema>
export type EventType = RagEvent['type']
export type ChatRequest = {
  protocol_version: 1
  conversation_id: string
  request_id: string
  message_id: string
  question: string
  history: { role: 'user' | 'assistant'; content: string }[]
}
export interface RagTransport {
  readonly configured: boolean
  stream(request: ChatRequest, signal: AbortSignal, onEvent: (event: RagEvent) => void): Promise<void>
}
export class RagError extends Error {
  constructor(public readonly code: string, message: string) { super(message); this.name = 'RagError' }
}
export function protocolError(message: string): never { throw new RagError('protocol_error', message) }
export function parseEvent(data: string): RagEvent {
  try { return eventSchema.parse(JSON.parse(data)) }
  catch { return protocolError('The agent returned an invalid activity event. Partial results are preserved.') }
}

/** Accept a URL supplied by the server, never manufacture a document URL. */
export function safeSourceUrl(url?: string): string | undefined {
  if (!url || /[\u0000-\u0020\\]/.test(url)) return undefined
  if (url.startsWith('/') && !url.startsWith('//')) return url
  try { const parsed = new URL(url); return ['https:', 'http:'].includes(parsed.protocol) && !parsed.username && !parsed.password ? url : undefined }
  catch { return undefined }
}
