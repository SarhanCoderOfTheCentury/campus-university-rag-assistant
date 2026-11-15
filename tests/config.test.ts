import { describe, expect, it } from 'vitest'
import { resolveRagConfig } from '../src/lib/rag/config'

describe('AWS frontend configuration', () => {
  it('keeps the backend disconnected when no URL is supplied', () => {
    expect(resolveRagConfig({}, true)).toEqual({ endpoint: undefined, credentials: 'omit' })
  })
  it('supports HTTPS and explicit cookie authentication', () => {
    expect(resolveRagConfig({ VITE_RAG_STREAM_URL: ' https://rag.example.invalid/api/chat/stream ', VITE_RAG_CREDENTIALS: 'include' }, true)).toEqual({ endpoint: 'https://rag.example.invalid/api/chat/stream', credentials: 'include' })
  })
  it.each(['/api/chat/stream', '//rag.example.invalid/stream', 'http://localhost:8000/stream', 'http://rag.example.invalid/stream', 'https://user:secret@rag.example.invalid/stream', 'https://rag.example.invalid/stream#fragment', 'javascript:alert(1)'])('rejects unsafe or local production endpoints: %s', endpoint => {
    expect(() => resolveRagConfig({ VITE_RAG_STREAM_URL: endpoint }, true)).toThrow()
  })
  it('allows local HTTP and a local proxy only in development', () => {
    for (const endpoint of ['http://localhost:8000/api/chat/stream', '/api/chat/stream']) {
      expect(resolveRagConfig({ VITE_RAG_STREAM_URL: endpoint }, false).endpoint).toBe(endpoint)
    }
  })
  it('rejects an invalid credentials mode', () => {
    expect(() => resolveRagConfig({ VITE_RAG_CREDENTIALS: 'yes' }, true)).toThrow()
  })
})
