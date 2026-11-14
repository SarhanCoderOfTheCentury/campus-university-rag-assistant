import { createParser } from 'eventsource-parser'
import { parseEvent, protocolError, RagError, type ChatRequest, type RagEvent, type RagTransport } from './protocol'

export type StreamOptions = {
  endpoint?: string
  idleTimeoutMs?: number
  fetcher?: typeof fetch
  /** Obtain short-lived auth from your real login session. Never put provider secrets in VITE_* variables. */
  headers?: (signal: AbortSignal) => Promise<Record<string, string>>
  credentials?: RequestCredentials
}

/** POST + SSE: one request, no automatic retries that could duplicate generation. */
export function createRagTransport(options: StreamOptions): RagTransport {
  const endpoint = options.endpoint?.trim()
  const fetcher = options.fetcher ?? fetch
  const idleTimeout = options.idleTimeoutMs ?? 90000
  return {
    configured: Boolean(endpoint),
    async stream(request: ChatRequest, signal: AbortSignal, onEvent: (event: RagEvent) => void) {
      if (!endpoint) throw new RagError('not_configured', 'The university knowledge base is not connected yet. Your question was not sent.')
      if (!Number.isFinite(idleTimeout) || idleTimeout < 1000) throw new RagError('configuration_error', 'The stream timeout is not configured correctly.')
      const controller = new AbortController()
      const relayAbort = () => controller.abort(signal.reason)
      signal.addEventListener('abort', relayAbort, { once: true })
      if (signal.aborted) relayAbort()
      let timer: ReturnType<typeof setTimeout> | undefined
      const touch = () => {
        clearTimeout(timer)
        timer = setTimeout(() => controller.abort(new RagError('timeout', 'The agent stopped sending activity. Partial results are preserved.')), idleTimeout)
      }
      let reader: ReadableStreamDefaultReader<Uint8Array> | undefined
      let terminal = false
      let bytes = 0
      try {
        touch()
        const authHeaders = await options.headers?.(controller.signal)
        const response = await fetcher(endpoint, {
          method: 'POST', credentials: options.credentials ?? 'include', signal: controller.signal,
          headers: { ...authHeaders, Accept: 'text/event-stream', 'Content-Type': 'application/json' },
          body: JSON.stringify(request),
        })
        if (!response.ok) {
          const message = response.status === 401 || response.status === 403 ? 'You are not authorized to use this knowledge base.' : response.status === 503 ? 'The university knowledge base is not available yet. No retrieval activity was received.' : `The agent could not accept the request (HTTP ${response.status}).`
          throw new RagError(`http_${response.status}`, message)
        }
        if (!response.headers.get('content-type')?.toLowerCase().startsWith('text/event-stream')) protocolError('The agent returned an unexpected response format.')
        if (!response.body) protocolError('The agent response had no event stream.')
        reader = response.body.getReader()
        const parser = createParser({
          maxBufferSize: 1_000_000,
          onError(error) { if (error.type === 'max-buffer-size-exceeded') throw new RagError('protocol_error', 'An agent event exceeded the allowed size.') },
          onEvent(message) {
            if (terminal || controller.signal.aborted) return
            const event = parseEvent(message.data)
            if (message.event !== event.type) protocolError('The SSE event name did not match its payload.')
            if (message.id !== `${event.run_id}:${event.sequence}`) protocolError('The SSE event ID did not match its payload.')
            if (event.request_id !== request.request_id || event.conversation_id !== request.conversation_id || event.message_id !== request.message_id) protocolError('The stream delivered an event for a different request.')
            onEvent(event)
            if (event.type === 'completed' || event.type === 'error') terminal = true
          },
        })
        const decoder = new TextDecoder('utf-8', { fatal: true })
        while (!terminal) {
          const { done, value } = await reader.read()
          if (done) { parser.feed(decoder.decode()); break }
          touch() // Includes real SSE keep-alive bytes; never creates progress events.
          bytes += value.byteLength
          if (bytes > 8_000_000) protocolError('The agent stream exceeded the allowed size.')
          parser.feed(decoder.decode(value, { stream: true }))
        }
        if (!terminal) throw new RagError('interrupted', 'The connection ended before the agent completed. Partial results are preserved.')
      } catch (error) {
        if (controller.signal.aborted && controller.signal.reason instanceof RagError) throw controller.signal.reason
        if (signal.aborted) throw new RagError('cancelled', 'This request was cancelled.')
        if (error instanceof RagError) throw error
        throw new RagError('interrupted', 'The connection to the agent was interrupted. Partial results are preserved.')
      } finally {
        clearTimeout(timer)
        signal.removeEventListener('abort', relayAbort)
        controller.abort()
        if (reader) { try { await reader.cancel() } catch { /* Already closed or aborted. */ } reader.releaseLock() }
      }
    },
  }
}
