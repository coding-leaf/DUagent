# Quality Guidelines (`frontend`)

> Linting, testing, and UI quality standards.

---

## Conventions

1. **Linting**: Keep code compliant with ESLint rules (`npm run lint`). Fix all syntax and unused variable warnings.
2. **Unit Testing**: Unit and component tests use `vitest` with `@testing-library/react` (`npm run test:unit`).
3. **E2E Testing**: Critical user journey tests use Playwright (`npm run test:e2e`).
4. **User Experience**: Show clear loading spinners/skeletons during SWR fetching, and display user-friendly error notifications (via `sonner` toasts).
5. **Simplicity**: Favor clean, native Tailwind markup over complicated CSS abstractions.
