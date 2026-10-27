# State Management (`frontend`)

> Managing state across server, global, and local boundaries.

---

## Conventions

1. **Server State**: Managed via **SWR**. Do not manually duplicate server data into global Redux/Zustand or long-lived React context.
2. **Local UI State**: Use React's standard `useState` and `useReducer` inside components.
3. **Global App State**: Use React Context (`context/`) only for genuinely global cross-cutting concerns (e.g. current authenticated user, theme, global modal manager).
4. **KISS**: Do not introduce heavy state management libraries (Redux, MobX, etc.). SWR + Context + `useState` is sufficient.
5. **SSE Stream Lifecycle & Loading Integrity**: When initiating an SSE stream in `ChatContext` (e.g. `startStream`), only abort prior in-flight network requests (`abortControllerRef.current?.()`). Never invoke broad cleanup functions that reset message `loading` states (such as `cancelStream()`), ensuring newly created placeholder messages maintain `loading: true` and display loading animations until terminal events (`workflow_completed` / `workflow_failed`) arrive.
