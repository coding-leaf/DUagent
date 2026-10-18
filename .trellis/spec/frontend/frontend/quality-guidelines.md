# Quality Guidelines (`frontend`)

> Linting, testing, and UI quality standards.

---

## Conventions

1. **Linting**: Keep code compliant with ESLint rules (`npm run lint`). Fix all syntax and unused variable warnings.
2. **Unit Testing**: Unit and component tests use `vitest` with `@testing-library/react` (`npm run test:unit`).
3. **E2E Testing**: Critical user journey tests use Playwright (`npm run test:e2e`).
4. **User Experience**: Show clear loading spinners/skeletons during SWR fetching, and display user-friendly error notifications (via `sonner` toasts).
5. **Simplicity**: Favor clean, native Tailwind markup over complicated CSS abstractions.

---

## Build & Lint Gate

Both commands are **mandatory before commit** and must exit 0 with no warnings:

```bash
cd frontend

npm run lint    # ESLint 9 (Flat Config) + eslint-plugin-react-hooks + eslint-plugin-react-refresh
npm run build   # Vite/Rollup production build (AST + bundle validation)
```

`npm run lint` runs `eslint .` against the flat config in `eslint.config.js`, which
enforces React 19 Hook dependency correctness and Fast Refresh component-export
rules. `npm run build` catches JSX syntax errors, unresolved imports, and Rollup AST
failures that lint alone misses — plus it surfaces the bundle-size warning.

> The build prints a `chunks are larger than 500 kB` notice for the Mermaid/KaTeX
> vendor chunks. That notice is informational (code-splitting guidance), not a
> failure; the command still exits 0.

### No TypeScript

The frontend is JavaScript/JSX only. Adding `.ts`/`.tsx` files, a `tsconfig.json`, or
a type-checker step is a redline — see
[architecture-guardrails.md](./architecture-guardrails.md).

### Architecture guardrails

Hard negative constraints that ESLint cannot express — pure-JSX discipline, no heavy
UI libraries, SSE state-machine safe exit, unified request layer — live in
[architecture-guardrails.md](./architecture-guardrails.md). Read it before touching
streaming components or adding dependencies.

---

## Local Verification

```bash
# Frontend only
cd frontend && npm run lint && npm run build

# Whole repo (frontend lint+build, both Python packages, both test suites)
python check_all.py
```
