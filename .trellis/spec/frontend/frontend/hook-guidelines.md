# Hook Guidelines (`frontend`)

> Custom hooks and data-fetching patterns.

---

## Conventions

1. **Naming**: All custom hooks must start with the `use` prefix (e.g., `useCourses`, `useAuth`).
2. **Data Fetching via SWR**:
   - Prefer SWR (`useSWR`) for fetching server data to gain automatic caching, revalidation, and loading/error states.
   - Combine with `services/` fetcher functions.
3. **Encapsulate Side Effects**: Encapsulate complex `useEffect` chains or event subscriptions inside dedicated custom hooks.
4. **Cleanups**: Always return cleanup functions in `useEffect` when adding event listeners, intervals, or abort controllers.
5. **KISS**: Do not build custom hooks for simple one-line `useState` wrappers.
