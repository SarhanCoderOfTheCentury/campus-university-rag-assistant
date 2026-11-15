import { useEffect, useState, useSyncExternalStore } from 'react'
import { RagSession } from '@/lib/rag/session'
import { createRagTransport } from '@/lib/rag/transport'
import { resolveRagConfig } from '@/lib/rag/config'
import deployment from '@/config/deployment.json'

export function useRagChat() {
  const [session] = useState(() => {
    const config = resolveRagConfig({ ...import.meta.env, VITE_RAG_STREAM_URL: import.meta.env.VITE_RAG_STREAM_URL ?? deployment.streamUrl }, import.meta.env.PROD)
    // Explicit environment override wins; cancellation must always use the same service.
    const cancelEndpoint = config.endpoint ? new URL('/api/chat/cancel', new URL(config.endpoint, window.location.origin)).href : undefined
    return new RagSession(createRagTransport({ ...config, cancelEndpoint }))
  })
  const state = useSyncExternalStore(session.subscribe, session.getSnapshot, session.getSnapshot)
  useEffect(() => () => session.dispose(), [session])
  return { ...state, session, backendConfigured: session.transport.configured }
}
