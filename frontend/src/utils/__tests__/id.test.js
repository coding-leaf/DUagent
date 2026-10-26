import { describe, expect, it, vi } from 'vitest';
import { uid } from '../id';

describe('uid utility', () => {
  it('uses globalThis.crypto.randomUUID when available', () => {
    const spy = vi.spyOn(globalThis.crypto, 'randomUUID').mockReturnValue('mocked-uuid-1234');
    try {
      const id = uid();
      expect(id).toBe('mocked-uuid-1234');
      expect(spy).toHaveBeenCalled();
    } finally {
      spy.mockRestore();
    }
  });

  it('falls back to timestamp and random string when crypto.randomUUID is not available', () => {
    const originalCrypto = globalThis.crypto;
    // Simulate non-secure HTTP context where randomUUID does not exist
    Object.defineProperty(globalThis, 'crypto', {
      value: {},
      writable: true,
      configurable: true
    });

    try {
      const id1 = uid();
      const id2 = uid();

      expect(typeof id1).toBe('string');
      expect(id1.length).toBeGreaterThan(10);
      expect(id1).not.toBe(id2);
    } finally {
      Object.defineProperty(globalThis, 'crypto', {
        value: originalCrypto,
        writable: true,
        configurable: true
      });
    }
  });
});
