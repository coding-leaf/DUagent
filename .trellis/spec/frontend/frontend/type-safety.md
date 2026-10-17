# Type Safety & Language Conventions (`frontend`)

> Language rules and data validation.

---

## Conventions

1. **JavaScript / JSX**: The frontend is written in standard JavaScript (`.jsx` / `.js`). Do NOT convert files to TypeScript (`.tsx`) unless the user explicitly requests a migration.
2. **Defensive Programming**: Use optional chaining (`?.`) and nullish coalescing (`??`) when handling API response fields that may be absent.
3. **Runtime Validation**: Where critical data structures cross boundaries, validate shape simply with pure JavaScript helper functions or object schema guards.
4. **KISS**: Keep props readable and well-documented through clear naming and default values.
