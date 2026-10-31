/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "1" in the static GitHub Pages build (no backend: only the client-side Analyst is served). */
  readonly VITE_STATIC?: string;
}
