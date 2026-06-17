import '@testing-library/jest-dom'
import { vi } from 'vitest'

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock ResizeObserver
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Track fake timers state globally
let isFakeTimersActive = false;
const originalUseFakeTimers = vi.useFakeTimers;
const originalUseRealTimers = vi.useRealTimers;

vi.useFakeTimers = function (options) {
  isFakeTimersActive = true;
  const result = originalUseFakeTimers.call(this, options);
  globalThis.requestAnimationFrame = (cb) => {
    cb();
    return 0;
  };
  return result;
};

vi.useRealTimers = function () {
  isFakeTimersActive = false;
  return originalUseRealTimers.call(this);
};

// Intercept @testing-library/react's waitFor to cleanly handle Vitest fake timers
vi.mock('@testing-library/react', async (importOriginal) => {
  const original = await importOriginal();
  return {
    ...original,
    waitFor: async (callback, options) => {
      if (isFakeTimersActive) {
        originalUseRealTimers();
        try {
          return await original.waitFor(callback, options);
        } finally {
          originalUseFakeTimers();
        }
      }
      return original.waitFor(callback, options);
    }
  };
});
