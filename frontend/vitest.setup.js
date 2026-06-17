import '@testing-library/jest-dom'
import { vi, expect } from 'vitest'

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

// Intercept vi.useFakeTimers to only apply fake timers for tests that need it (polling tests),
// preventing SWR/waitFor from hanging on standard asynchronous fetch tests.
const originalUseFakeTimers = vi.useFakeTimers;
vi.useFakeTimers = function (options) {
  const state = expect.getState();
  const testName = state?.currentTestName || '';
  if (testName.includes('triggers refresh')) {
    const result = originalUseFakeTimers.call(this, options);
    globalThis.requestAnimationFrame = (cb) => {
      cb();
      return 0;
    };
    return result;
  }
  // For other tests, bypass useFakeTimers
};

vi.mock('@testing-library/react', async (importOriginal) => {
  const original = await importOriginal();
  return {
    ...original,
    waitFor: async (callback, options) => {
      const state = expect.getState();
      const testName = state?.currentTestName || '';
      if (testName.includes('triggers refresh')) {
        vi.useRealTimers();
        try {
          return await original.waitFor(callback, options);
        } finally {
          vi.useFakeTimers();
        }
      }
      return original.waitFor(callback, options);
    }
  };
});
