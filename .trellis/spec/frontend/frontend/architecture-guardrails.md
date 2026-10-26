# Architecture Guardrails (`frontend`)

> Hard negative constraints (架构红线) plus the explicit escape hatches (显式逃生通道)
> for the React 19 + JSX SPA.

---

## Why This File Exists

The frontend has two failure modes that ESLint cannot catch: a runaway TypeScript
migration nobody asked for, and SSE state machines that leave a spinner spinning
forever after a dropped stream. Both are redlines below.

---

## Hard Negative Constraints (架构红线)

### ❌ 严禁擅自引入 TypeScript (No unsanctioned TypeScript)

This is a **JavaScript / JSX** codebase: `.js` / `.jsx` only.

Forbidden:

- Adding `.ts` / `.tsx` files or a `tsconfig.json`
- Introducing `typescript`, `vue-tsc`, or any type-checker step
- Renaming `.jsx` → `.tsx` "for clarity"
- JSDoc-style `// @ts-` directives

**Why**: TS was deliberately declined. A partial migration doubles the toolchain,
breaks `npm run build` for untouched files, and splits the contributor audience.
Type safety is handled by conventions (see `type-safety.md`), not by a compiler.

**Standard alternative**: use `prop-types`-free, narrowly-scoped components; encode
contract expectations in JSDoc comments where helpful.

### ❌ 严禁引入重型 UI 组件库 (No heavy UI component libraries)

Tailwind utility classes + native HTML elements + `lucide-react` icons. Do not add
MUI, Ant Design, Chakra, Bootstrap, or shadcn-style generator output.

**Why**: Tailwind v4 is the design system. A component library imports its own
reset, its own theming, and its own accessibility opinions, which fight Tailwind
and bloat the bundle (the Vite build already warns about chunks >500 kB).

### ❌ 严禁 SSE 状态机无安全退出 (Never leave an SSE state machine without a safe exit)

Every streaming subscription (`tutoring`, workbench runs, personalized resources)
must reach a terminal state on **all** paths: success, server error, network drop,
component unmount, and user abort.

Requirements:

- `EventSource` / `fetch`-stream cleanup in the `useEffect` return function (close the source, clear timers, reset the ref).
- Errors must flip the state machine to a terminal status **and** surface a `sonner` toast — never leave `isStreaming === true`.
- A disconnected stream must be distinguishable from "still thinking"; show a retry affordance.

**Why**: an unclosed `EventSource` keeps the browser connection pinned and the UI
spinner forever. Users read that as "the app is broken" with no way to recover.

```jsx
// ✅ Required shape
useEffect(() => {
  const controller = new AbortController()
  setStatus('streaming')
  streamChat(payload, {
    signal: controller.signal,
    onDone: () => setStatus('done'),
    onError: (err) => {
      setStatus('error')
      toast.error(err?.message ?? '连接中断，请重试')
    },
  })
  return () => controller.abort()
}, [payload])
```

### ❌ 严禁绕过统一请求层 (No ad-hoc axios/fetch calls)

All HTTP goes through the shared client (`src/api/` + axios interceptors) so the
401 handling, dev token injection, and base URL stay in one place. Direct
`fetch('http://localhost:8000/...')` in a component is forbidden.

### ❌ 严禁在渲染期做副作用 (No side effects during render)

Data fetching belongs in SWR hooks or `useEffect`; never in the component body.
Mutating refs, dispatching, or calling APIs during render breaks React 19's
concurrent rendering.

### ❌ 严禁直接调用裸 `crypto.randomUUID()` 或退出登录漏调 `logout()` (No bare `crypto.randomUUID()` & always clear auth state on logout)

1. **Non-Secure Context UUID Safety**: `crypto.randomUUID` is `undefined` on plain HTTP LAN deployments (`http://<lan-ip>`). Always import `uid()` from `src/utils/id.js` instead of calling `crypto.randomUUID()` directly.
2. **Logout Completeness**: Every "退出登录" button across all role consoles (`TeacherConsole`, `TeacherStudentReport`, `Navbar`, etc.) must destructure `logout` from `useAuth()` and invoke `logout()` before `navigate('/')`.

---

## Escape Hatches (显式逃生通道)

Occasionally a redline needs a documented exception — vendored code, a dataviz
library that cannot be Tailwind-styled, an intentionally persistent stream.

### Rule

1. **Converge.** Keep the exception local to one module/file; never spread it
   across the app.
2. **Declare it inline** with a tagged, reasoned comment:

   ```jsx
   // arch-allow: ts-file (reason: vendor shim copied verbatim from mermaid docs; see #412)
   ```

3. **Use a known tag.** Unknown tags fail review:

   | Tag | Meaning |
   | :-- | :-- |
   | `ts-file` | A `.ts`/`.tsx` file that must stay |
   | `ui-library` | A third-party UI component import |
   | `persistent-stream` | A stream intentionally kept open past unmount |
   | `direct-fetch` | An HTTP call bypassing the shared client |

4. **Keep a reason.** `(reason: ...)` is mandatory.

5. **Re-audit.** Audit with `grep -rn "arch-allow:" frontend/src/`.

### Example: allowed vs. forbidden

```jsx
// ✅ Allowed — one vendored shim, tagged, reasoned
// arch-allow: ts-file (reason: upstream typings for mermaid plugins; no JS equivalent)
import type { MermaidConfig } from './vendor/mermaid.d.ts'


// ❌ Forbidden — UI library creeping in, no tag
import { Button } from '@mui/material'
```

---

## Static Enforcement

```bash
cd frontend

npm run lint    # ESLint 9 flat config + react-hooks + react-refresh
npm run build   # Vite/Rollup AST + bundle check

grep -rn "arch-allow:" src/   # escape-hatch audit
```

The full repo gate is `python check_all.py`.
