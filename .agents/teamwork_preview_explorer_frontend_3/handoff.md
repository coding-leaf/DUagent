# Handoff Report: AIChat Frontend Audit

## 1. Observation
We conducted a read-only code audit of the frontend `AIChat` workspace, including `frontend/src/pages/AIChat.jsx` and the components under `frontend/src/components/chat/`. The following key segments were observed:

- **SidebarResources.jsx (lines 9-10, 14-35)**: Manages its own resource states and data fetching:
  ```javascript
  const [resources, setResources] = useState([]);
  const [error, setError] = useState(false);
  // ...
  useEffect(() => {
    let active = true;
    if (activeCourseId) {
      setError(false);
      learningService.getResources({ course_id: activeCourseId, page: 1, page_size: 100 })
        .then(res => {
          if (active && res.code === 200 && res.data) {
            setResources(Array.isArray(res.data.resources || res.data) ? (res.data.resources || res.data) : []);
          } else if (active) {
            setError(true);
          }
        })
        .catch(err => {
          console.error(err);
          if (active) setError(true);
        });
    } else {
      setTimeout(() => { if (active) setResources([]); }, 0);
    }
    return () => { active = false; };
  }, [activeCourseId]);
  ```
  It also overrides ESLint checks using `// eslint-disable-next-line react-hooks/set-state-in-effect` on line 17 and uses a hacky `setTimeout` on line 32.

- **ChatContext.jsx (lines 24, 32-43)**: Fetches and stores session lists manually:
  ```javascript
  const [sessions, setSessions] = useState([]);
  // ...
  useEffect(() => {
    if (activeCourseId) {
      chatService.getSessions(activeCourseId).then(res => {
        if (res.code === 200 && res.data) {
          const list = res.data.conversations || res.data;
          setSessions(list);
          if (list.length > 0) setActiveSession(list[0].id);
          else { setActiveSession(null); setMessages([]); }
        }
      }).catch(console.error);
    }
  }, [activeCourseId]);
  ```
  It also uses an ESLint bypass `// eslint-disable-next-line react-hooks/set-state-in-effect` on line 53 when clearing messages.

- **ChatArea.jsx (lines 176-181)**: Contains stub/placeholder controls with no click handlers:
  ```jsx
  <button className="p-1.5 hover:bg-slate-100 hover:text-slate-600 rounded-lg transition-colors cursor-pointer flex items-center justify-center">
    <Icon name="attach_file" className="material-symbols-outlined text-[18px]"/>
  </button>
  <button className="p-1.5 hover:bg-slate-100 hover:text-slate-600 rounded-lg transition-colors cursor-pointer flex items-center justify-center">
    <Icon name="mic" className="material-symbols-outlined text-[18px]"/>
  </button>
  ```

- **Unused imports and Debug logs**: Ripgrep searches confirmed there are no `console.log` statements (only standard clipboard caught errors) and code analysis verified all imports in the target files are actively used.

---

## 2. Logic Chain
1. **Observation 1 (SidebarResources.jsx manual fetching)** -> Direct fetching and state management within a presentation view violates the MVVM design pattern. State management and data retrieval should reside inside a custom hook (ViewModel) or context.
2. **Observation 2 (ChatContext.jsx manual fetching)** -> Setting session list inside a manual `useEffect` hook fails to utilize SWR caching, automatic background revalidation, or simplified data-state management, violating the project-scoped "Reuse-First Principle" which prioritizes SWR over `useEffect` fetching.
3. **Logic regarding Chat Messages**: While SWR is ideal for request-response resources, streaming messages (SSE chunks, dynamic tool-call states, and mermaid diagrams) receive volatile, high-frequency updates. Binding the real-time message stream to an SWR cache could trigger race conditions or background revalidation loops that overwrite active user inputs. Thus, keeping `messages` in local context state is correct, but SWR should still manage the initial session list.
4. **Conclusion**: Modularity and MVVM architecture can be significantly improved by:
   - Creating a new custom hook `useRecommendedResources` to fetch, filter, and recommend resources using SWR.
   - Refactoring `ChatContext.jsx` to fetch the session list via SWR and mutate it optimistically on deletion.
   - Eliminating hacky timeout side effects and ESLint suppression comments in both files.

---

## 3. Caveats
We assumed the SWR configuration on other pages (e.g. `useLearningPath.js`) serves as the architectural standard. We did not write or run code modifications outside our agent folder since this is a read-only investigation task.

---

## 4. Conclusion
The AIChat module is functionally sound but violates architectural directives on SWR caching and MVVM modularity in `SidebarResources.jsx` and `ChatContext.jsx`. Applying SWR to manage session and course resource state will clean up more than 50% of the manual lifecycle logic, eliminate lint bypasses, and improve stability. Detailed recommended changes have been written to `analysis.md`.

---

## 5. Verification Method
To verify the audit and proposed edits:
1. Confirm the exists and contents of `analysis.md` inside `.agents/teamwork_preview_explorer_frontend_3/`.
2. Inspect the proposed custom hook `useRecommendedResources.js` and the refactored files in `analysis.md`.
3. To test compile-time validity after an implementer applies these changes:
   ```bash
   cd frontend
   npm run lint
   npm run build
   ```
   No compilation or lint errors should occur.
