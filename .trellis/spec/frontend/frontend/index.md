# Frontend Guidelines (Package: `frontend`)

> Baseline conventions for the React 19 SPA frontend.

---

## Core Tenets

1. **Code is Truth**: Existing React components and hooks in `frontend/src/` are authoritative.
2. **Fixed Tech Stack**: React 19 + Vite + Tailwind CSS v4 + SWR + Axios + React Router v7 + Lucide React.
3. **Language**: JavaScript / JSX (do NOT introduce TypeScript migrations or arbitrarily convert files to `.tsx` unless explicitly requested by the user).
4. **KISS Principle**: Favor simple functional components with hooks. Avoid heavy third-party UI component libraries; rely on Tailwind utility classes and native HTML elements.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | File organization under `frontend/src/` | Baseline active |
| [Component Guidelines](./component-guidelines.md) | Functional component structure, styling, composition | Baseline active |
| [Hook Guidelines](./hook-guidelines.md) | Custom hooks and SWR data-fetching patterns | Baseline active |
| [State Management](./state-management.md) | SWR server cache, local React state, context | Baseline active |
| [Type Safety](./type-safety.md) | JavaScript/JSX conventions, prop validation | Baseline active |
| [Quality Guidelines](./quality-guidelines.md) | ESLint, Vitest, and Playwright standards | Baseline active |
