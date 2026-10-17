# Directory Structure (`frontend`)

> Layout for `frontend/src/`.

---

## Layout

```
frontend/
├── package.json        # Dependencies & scripts (React 19, Vite, Tailwind v4, SWR, Vitest)
├── vite.config.js      # Vite build & plugin configuration
└── src/
    ├── api/            # Low-level Axios instance & API client functions
    ├── assets/         # Static assets (images, SVGs)
    ├── components/     # Reusable UI components (buttons, modals, cards, layouts)
    ├── constants/      # App constants, route paths, configuration values
    ├── context/        # React Context providers for global UI state
    ├── hooks/          # Custom hooks (e.g. data fetching, window sizing, auth state)
    ├── pages/          # Route-level page components
    ├── services/       # Domain-specific API service wrappers
    ├── utils/          # Pure helper functions (formatters, date utils)
    ├── App.jsx         # Root component with router setup
    └── main.jsx        # App entry point mounting into DOM
```

---

## Conventions

- **Pages (`pages/`)**: Top-level page views mapped to React Router routes. Coordinate data fetching and layout.
- **Components (`components/`)**: Keep them modular and focused. Use subfolders for complex features if needed.
- **Services (`services/`)**: Centralize HTTP endpoints and response mapping so components do not make ad-hoc Axios calls.
- **KISS**: Avoid deeply nested folder structures. Keep related files close together.
