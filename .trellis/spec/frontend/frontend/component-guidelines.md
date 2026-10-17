# Component Guidelines (`frontend`)

> React 19 component design conventions.

---

## Conventions

1. **Functional Components**: Use standard functional components with hooks.
2. **Styling with Tailwind CSS v4**: Use Tailwind CSS utility classes directly on JSX elements. Avoid arbitrary inline styles unless dynamic values (e.g. calculated widths/positions) require them.
3. **Icons**: Use `lucide-react` icons exclusively.
4. **Props**: Destructure props at the function signature with sensible defaults where appropriate.
5. **KISS**: Decompose large components (>300 lines) into smaller, readable subcomponents. Avoid premature generic abstractions (e.g. over-abstracted polymorphic components).
