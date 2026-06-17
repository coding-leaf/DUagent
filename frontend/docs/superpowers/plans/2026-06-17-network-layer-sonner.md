# Network Layer Sonner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a global HTTP 401 redirect and integrated modern Toast error handling by introducing `sonner` and refactoring `client.js`, while avoiding toast-bombing for component-level 4xx errors.

**Architecture:** Use Axios Interceptors (Proxy pattern) to catch errors globally. Use `sonner` as a headless, stacked global notification center because it supports pure function execution outside of the React Tree.

**Tech Stack:** React, TailwindCSS, Vite, Axios, Sonner.

---

### Task 1: Install Sonner and Add Global Toaster

**Files:**
- Modify: `package.json`
- Modify: `src/App.jsx`

- [ ] **Step 1: Install `sonner`**

Run: `npm install sonner`
Expected: Successfully installs the dependency without conflicts.

- [ ] **Step 2: Add `<Toaster />` and `/login` Route to `App.jsx`**

```jsx
// src/App.jsx
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
// ... existing imports ...

function App() {
  return (
    <Router>
      <Toaster position="top-center" richColors />
      <AuthProvider>
        <CourseProvider>
          <ChatProvider>
            <Routes>
              {/* Alias /login to the Login page for clearer redirects */}
              <Route path="/" element={<Login />} />
              <Route path="/login" element={<Navigate to="/" replace />} />
// ... rest of the existing code ...
```

- [ ] **Step 3: Commit**

```bash
git add package.json package-lock.json src/App.jsx
git commit -m "feat: install sonner, add Toaster and /login alias"
```

---

### Task 2: Refactor API Client Interceptor

**Files:**
- Modify: `src/api/client.js`

- [ ] **Step 1: Update Interceptor with Target Toast Logic and 401 Redirect**

```javascript
// src/api/client.js
import axios from 'axios';
import { toast } from 'sonner';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

apiClient.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    if (error.response) {
      const { status } = error.response;
      if (status === 401) {
        console.error('Authentication failed, token expired.');
        localStorage.removeItem('access_token');
        // No toast needed, redirect is explicit enough
        window.location.href = '/login';
      } else if (status === 403) {
        toast.error('权限不足');
      } else if (status >= 500) {
        toast.error('服务器错误，请稍后重试');
      }
      // Other 4xx errors are passed down to be handled by component catch blocks
      // to avoid toast bombing alongside inline error UI.
    } else {
      console.error('Network Error:', error.message);
      toast.error('网络错误，请检查您的连接');
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

- [ ] **Step 2: Verify application builds successfully**

Run: `npm run build`
Expected: Output showing successful Vite build.

- [ ] **Step 3: Commit**

```bash
git add src/api/client.js
git commit -m "refactor: add global error toast for 5xx/403 and 401 redirect to api client"
```
