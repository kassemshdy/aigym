/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Unset in development and on `main`'s prototype build → the app runs on
   * mocks exactly as it always has. Set only where the API is actually
   * deployed alongside it. See apps/api/AGENTS.md and the Phase 2 boundary
   * note in this app's own AGENTS.md. */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
