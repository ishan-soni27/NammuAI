/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** e.g. "https://kestrel-bay-api.onrender.com/api/v1" (must include /api/v1). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
