# State Management (`frontend`)

> Managing state across server, global, and local boundaries.

---

## Conventions

1. **Server State**: Managed via **SWR**. Do not manually duplicate server data into global Redux/Zustand or long-lived React context.
2. **Local UI State**: Use React's standard `useState` and `useReducer` inside components.
3. **Global App State**: Use React Context (`context/`) only for genuinely global cross-cutting concerns (e.g. current authenticated user, theme, global modal manager).
4. **KISS**: Do not introduce heavy state management libraries (Redux, MobX, etc.). SWR + Context + `useState` is sufficient.
