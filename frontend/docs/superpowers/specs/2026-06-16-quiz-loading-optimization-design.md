# Design Spec: Quiz Result Loading Screen Optimization

Optimize the waiting experience after completing a quiz. Instead of a short 1.5-second wait with a simple spinner, we will increase the loading/fetching delay to 5 seconds and display a themed loading card with dynamic rotating status messages.

## 1. Requirements

- **Delay Time**: Increase from `1500ms` to `5000ms` to align with the async LLM agent evaluation task on the backend.
- **Copywriting Steps**: Rotate through the following states every 1.25 seconds:
  1. `0.0s - 1.25s`: "正在接收本次作答数据..."
  2. `1.25s - 2.50s`: "正在分析知识点掌握情况..."
  3. `2.50s - 3.75s`: "正在评估薄弱环节与能力表现..."
  4. `3.75s - 5.00s`: "正在生成个性化学习建议..."
- **UI Style**: Match the existing light theme. It should look professional and fit the current layout seamlessly.

## 2. UI & Interaction Design

### Visual Layout
The loading screen will have:
1. Centered loading card matching the size of typical system panels/dialogs (`max-w-md w-full`).
2. An outer spinning progress ring (`animate-spin`) wrapping an inner pulsing AI robot icon (`animate-pulse`) to show active computation.
3. Clean heading: "智能教练评估中".
4. The rotating message paragraph below the header, utilizing smooth text replacement.

### Color Palette (Existing Tokens)
- Card container: `bg-white border border-outline-variant rounded-2xl shadow-sm`
- Text: `text-on-surface` (title) and `text-secondary` (status updates)
- Highlight color: `text-primary` and `text-primary-container`

## 3. Implementation Plan

### `frontend/src/pages/PracticeResult.jsx`
- Define the array of loading texts:
  ```javascript
  const LOADING_TEXTS = [
    "正在接收本次作答数据...",
    "正在分析知识点掌握情况...",
    "正在评估薄弱环节与能力表现...",
    "正在生成个性化学习建议..."
  ];
  ```
- Introduce state variable: `currentTextIndex` starting at `0`.
- Inside `useEffect`, set up a `setInterval` that increments `currentTextIndex` every `1250ms`, capped at `LOADING_TEXTS.length - 1` or wrapping around (we will cap it or let it wrap, capping is better for progressive stages).
- Change `setTimeout` from `1500` to `5000`.
- Update the `if (loading)` block to return the designed UI.

## 4. Verification Plan

- Run `npm run lint` and `npm run build` in the `frontend/` folder to check for syntax and compiler errors.
- Verify visually that the rotating messages update as expected.
