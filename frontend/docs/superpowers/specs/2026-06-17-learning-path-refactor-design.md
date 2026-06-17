# Learning Path Refactoring Design Spec

## 1. Objective
Refactor the monolithic `LearningPath.jsx` (437 lines) into a clean, modular architecture using the Container/Presentational pattern and Custom Hook pattern. This aligns with the architectural directive in `AGENTS.md` to eliminate "fat components" and separate concerns.

## 2. Architecture & Design Patterns

### 2.1 Pattern Selection
- **Container/Presentational Pattern**: `LearningPath.jsx` will be simplified to a pure Container, orchestrating state and data. The UI will be delegated to `PathVisualizer` and `NodeResourcePanel`.
- **Custom Hook Pattern**: Data fetching and initialization side-effects will be pushed into a dedicated `useLearningPath` hook to decouple business logic from rendering.

### 2.2 File Distribution
1. **`src/hooks/useLearningPath.js`**
   - **Responsibility**: Fetching `learningPath` and `nodeResources` (preferably utilizing `useSWR` combined with a `fetcherWrapper` for robust error handling, similar to `useTeacherConsoleData`).
   - **Responsibility**: Handling the auto-selection of the initial node (e.g., finding the `in_progress` or `recommended` node on first load).
   - **Responsibility**: Firing the tracking event `learningActivityService.trackActivity` when the active node changes.

2. **`src/components/learning/PathVisualizer.jsx`**
   - **Responsibility**: Rendering the horizontal scrolling path map.
   - **Responsibility**: Managing the mouse-wheel-to-horizontal-scroll DOM interception (`scrollContainerRef` logic). This logic is strictly view-related and belongs here, not in the container.
   - **Props**: `learningPath`, `loading`, `selectedNodeId`, `onSelectNode`.

3. **`src/components/learning/NodeResourcePanel.jsx`**
   - **Responsibility**: Rendering the 4-grid layout for node resources (tutorials, exercises, materials).
   - **Responsibility**: Encapsulating all local UI states (`showAllTutorials`, `showAllExercises`, `showAllMaterials`, `showFullExercises`). The Container should not care about these toggle states.
   - **Props**: `activeCourseId`, `selectedNodeId`, `nodeResources`, `resourcesLoading`.

4. **`src/pages/LearningPath.jsx`**
   - **Responsibility**: Acting as the orchestrator.
   - **State**: Holds only `activeCourseId` (via context) and `selectedNodeId` (local state).
   - **Logic**: Invokes `useLearningPath(activeCourseId, selectedNodeId)` and passes the returned data downstream.

## 3. Data Flow
1. Container retrieves `activeCourseId` from `useCourse()`.
2. Container initializes `selectedNodeId`.
3. Container passes both to `useLearningPath`.
4. `useLearningPath` reacts and fetches the path map and resources for the selected node.
5. If `selectedNodeId` is null, `useLearningPath` auto-computes the default node and returns it (or calls `setSelectedNodeId` via an exported callback).
6. UI components consume the data purely as props.

## 4. Error Handling
- Use `fetcherWrapper` in the custom hook to catch non-200 responses and translate them into a standard `error` state.
- Ensure null-safety in UI components if `nodeResources` is incomplete or missing fields.

## 5. Testing Strategy
- The refactor will be executed via subagents task-by-task.
- `npm run lint` and `npm run build` must pass at every checkpoint to ensure strict code validation.
