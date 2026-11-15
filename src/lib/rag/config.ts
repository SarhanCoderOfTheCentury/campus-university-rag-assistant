type RagEnvironment = {
  VITE_RAG_STREAM_URL?: string
  VITE_RAG_CREDENTIALS?: string
}

/** Shared build/runtime configuration. No endpoint or authentication is guessed. */
export function resolveRagConfig(env: RagEnvironment, production: boolean) {
  const endpoint = env.VITE_RAG_STREAM_URL?.trim() || undefined
  const credentials = env.VITE_RAG_CREDENTIALS?.trim() || 'omit'
  if (credentials !== 'omit' && credentials !== 'include' && credentials !== 'same-origin') {
    throw new Error('VITE_RAG_CREDENTIALS must be omit, include, or same-origin.')
  }
  if (endpoint) {
    const localProxy = !production && endpoint.startsWith('/') && !endpoint.startsWith('//') && !endpoint.includes('\\')
    if (!localProxy) {
      let url: URL
      try { url = new URL(endpoint) } catch { throw new Error('VITE_RAG_STREAM_URL must be a full HTTPS backend URL for production.') }
      const localHttp = !production && url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
      if ((url.protocol !== 'https:' && !localHttp) || url.username || url.password || url.hash) {
        throw new Error('VITE_RAG_STREAM_URL must use HTTPS without embedded credentials or a fragment; local HTTP is allowed only in development.')
      }
    }
  }
  return { endpoint, credentials: credentials as RequestCredentials }
}
