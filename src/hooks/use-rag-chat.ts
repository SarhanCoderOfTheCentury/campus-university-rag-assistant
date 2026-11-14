import { useEffect, useState, useSyncExternalStore } from 'react'
import { RagSession } from '@/lib/rag/session'
import { createRagTransport } from '@/lib/rag/transport'

export function useRagChat() {
  const [session] = useState(() => new RagSession(createRagTransport({ endpoint: import.meta.env.VITE_RAG_STREAM_URL })))
  const state = useSyncExternalStore(session.subscribe, session.getSnapshot, session.getSnapshot)
  useEffect(() => () => session.dispose(), [session])
  return { ...state, session, backendConfigured: session.transport.configured }
}
