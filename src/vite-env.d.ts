/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_RAG_STREAM_URL?: string
  readonly VITE_RAG_CREDENTIALS?: 'omit' | 'include' | 'same-origin'
}
