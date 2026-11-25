/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Optional override; default is the same site's /api/v1. Must include /api/v1. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
