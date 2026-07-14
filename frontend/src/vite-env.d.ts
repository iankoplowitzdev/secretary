/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Deployed Lambda Function URL (US-8). Falls back to the local mock if unset. */
  readonly VITE_FUNCTION_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
