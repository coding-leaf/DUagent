# AdminConsole View Splitting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. If any issues arise, utilize superpowers:systematic-debugging.

**Goal:** Refactor the massive 800-line `AdminConsole.jsx` into a slim Layout shell that delegates domain logic to 4 independent Panel components.

**Architecture:** Domain-driven View Splitting with localized state management.

**Tech Stack:** React (useState, useEffect), TailwindCSS.

---

### Task 1: Extract System Logs Panel

**Files:**
- Create: `src/components/admin/SystemLogsPanel.jsx`
- Modify: `src/pages/AdminConsole.jsx`

- [ ] **Step 1: Create `SystemLogsPanel.jsx`**
Extract all log-related state (`agentLogs`, `operationLogs`, `activeLogType`, `loadingLogs`), the `fetchLogs` function, and the `activeTab === 'logs'` JSX rendering logic into this new component.

- [ ] **Step 2: Update `AdminConsole.jsx`**
Import `<SystemLogsPanel />`. Replace the inline logs JSX with `<SystemLogsPanel />`. Remove all log-related state and functions from `AdminConsole.jsx`.

- [ ] **Step 3: Test and Commit**
Run: `npm run lint` and `npm run build`.
Commit: `refactor: extract SystemLogsPanel from AdminConsole`

---

### Task 2: Extract Registration Codes Panel

**Files:**
- Create: `src/components/admin/RegistrationCodesPanel.jsx`
- Modify: `src/pages/AdminConsole.jsx`

- [ ] **Step 1: Create `RegistrationCodesPanel.jsx`**
Extract all reg-code state, the `fetchRegCodes`, `handleGenerateCode`, `handleRevokeCode`, `handleCopyCode` functions, and its JSX into this new component.

- [ ] **Step 2: Update `AdminConsole.jsx`**
Import `<RegistrationCodesPanel />` and replace the inline JSX. Clean up unused state.

- [ ] **Step 3: Test and Commit**
Run: `npm run lint` and `npm run build`.
Commit: `refactor: extract RegistrationCodesPanel`

---

### Task 3: Extract Catalog Management Panel

**Files:**
- Create: `src/components/admin/CatalogManagementPanel.jsx`
- Modify: `src/pages/AdminConsole.jsx`

- [ ] **Step 1: Create `CatalogManagementPanel.jsx`**
Extract all catalog state, `fetchCatalogs`, `handleCreateCatalog`, `handleOpenCatalog` and the `CourseCatalogDrawer` integration into this component. Note: Move `CourseCatalogDrawer` import here.

- [ ] **Step 2: Update `AdminConsole.jsx`**
Import `<CatalogManagementPanel />` and replace the inline JSX. Remove the `CourseCatalogDrawer` from `AdminConsole.jsx` completely.

- [ ] **Step 3: Test and Commit**
Run: `npm run lint` and `npm run build`.
Commit: `refactor: extract CatalogManagementPanel`

---

### Task 4: Extract User Management Panel

**Files:**
- Create: `src/components/admin/UserManagementPanel.jsx`
- Modify: `src/pages/AdminConsole.jsx`

- [ ] **Step 1: Create `UserManagementPanel.jsx`**
Extract all user state, `fetchUsers`, password reset logic, user removal logic, and the Reset Password Modal JSX into this new component.

- [ ] **Step 2: Update `AdminConsole.jsx`**
Import `<UserManagementPanel />` and replace the inline JSX. By this step, `AdminConsole.jsx` should only contain `activeTab` state and Layout rendering.

- [ ] **Step 3: Test and Commit**
Run: `npm run lint` and `npm run build`.
Commit: `refactor: extract UserManagementPanel, finalizing AdminConsole refactor`
