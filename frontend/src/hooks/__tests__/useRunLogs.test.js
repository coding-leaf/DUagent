import { act, renderHook } from '@testing-library/react';
import { expect, test } from 'vitest';
import { useRunLogs } from '../useRunLogs';

test('useRunLogs normalizes events and keeps the latest 300 entries', () => {
  const { result } = renderHook(() => useRunLogs());

  act(() => {
    for (let index = 0; index < 301; index += 1) {
      result.current.appendRunLog({
        type: 'debug_log',
        run_id: `run-${index}`,
        payload: {
          event: `event-${index}`,
          source: 'test',
          trace_id: `trace-${index}`,
          span_id: `span-${index}`,
          span_kind: 'tool',
          phase: 'end'
        }
      });
    }
  });

  expect(result.current.runLogs).toHaveLength(300);
  expect(result.current.runLogs[0].message).toBe('event-1');
  expect(result.current.runLogs[0].traceId).toBe('trace-1');
  expect(result.current.runLogs[0].spanId).toBe('span-1');
  expect(result.current.runLogs[0].spanKind).toBe('tool');
  expect(result.current.runLogs[0].phase).toBe('end');
  expect(result.current.runLogs.at(-1).runId).toBe('run-300');

  act(() => {
    result.current.clearRunLogs();
  });

  expect(result.current.runLogs).toHaveLength(0);
});
