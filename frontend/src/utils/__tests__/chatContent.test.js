import { describe, it, expect } from 'vitest'
import { extractModelText, normalizeMessage, normalizeTextList } from '../chatContent'

describe('chatContent utils', () => {
  describe('extractModelText', () => {
    it('handles null or undefined', () => {
      expect(extractModelText(null)).toBe('')
      expect(extractModelText(undefined)).toBe('')
    })

    it('handles primitives', () => {
      expect(extractModelText(123)).toBe('123')
      expect(extractModelText(true)).toBe('true')
      expect(extractModelText('hello')).toBe('hello')
    })

    it('extracts from object', () => {
      expect(extractModelText({ model_text: 'test' })).toBe('test')
      expect(extractModelText({ content: 'test content' })).toBe('test content')
    })

    it('extracts from JSON string', () => {
      expect(extractModelText('{"model_text": "json test"}')).toBe('json test')
    })

    it('extracts from markdown with JSON envelope', () => {
      const text = 'Here is the response:\n```json\n{"model_text": "markdown test"}\n```'
      expect(extractModelText(text)).toBe('markdown test')
    })
  })

  describe('normalizeTextList', () => {
    it('normalizes single value to array', () => {
      expect(normalizeTextList('test')).toEqual(['test'])
    })

    it('normalizes array of values', () => {
      expect(normalizeTextList(['test1', { model_text: 'test2' }])).toEqual(['test1', 'test2'])
    })

    it('filters out empty values', () => {
      expect(normalizeTextList(['test', null, '', '  '])).toEqual(['test'])
    })
  })

  it('restores persisted tool cards from message metadata', () => {
    const message = normalizeMessage({
      role: 'assistant',
      content: '已读取学习状态。',
      meta: {
        tool_events: [
          {
            type: 'tool_started',
            payload: { tool_call_id: 'tool-1', tool_name: 'read_learning_state' }
          },
          {
            type: 'tool_completed',
            payload: {
              tool_call_id: 'tool-1',
              state: 'success',
              output_summary: '薄弱点已读取'
            }
          }
        ]
      }
    })

    expect(message.toolCalls).toEqual([
      {
        id: 'tool-1',
        name: 'read_learning_state',
        status: 'completed',
        outputSummary: '薄弱点已读取'
      }
    ])
    expect(message.parts.map(part => part.type)).toEqual(['text', 'tool'])
  })

  it('restores persisted text and tool cards in event order', () => {
    const message = normalizeMessage({
      role: 'assistant',
      content: '前半段后半段',
      meta: {
        event_timeline: [
          { type: 'text_delta', payload: { delta: '前半段' } },
          { type: 'tool_started', payload: { tool_call_id: 'tool-1', tool_name: 'read_profile' } },
          { type: 'tool_completed', payload: { tool_call_id: 'tool-1', state: 'success' } },
          { type: 'text_delta', payload: { delta: '后半段' } }
        ]
      }
    })

    expect(message.parts.map(part => part.type)).toEqual(['text', 'tool', 'text'])
    expect(message.parts[0].content).toBe('前半段')
    expect(message.parts[2].content).toBe('后半段')
  })

  it('restores persisted RAG sources from message metadata', () => {
    const message = normalizeMessage({
      role: 'assistant',
      content: '数组说明',
      meta: { sources: [{ source_file: '教材.pdf', snippet: '数组', score: 0.9 }] }
    })
    expect(message.sourceRefs).toEqual([
      { source_file: '教材.pdf', snippet: '数组', score: 0.9 }
    ])
  })
})
