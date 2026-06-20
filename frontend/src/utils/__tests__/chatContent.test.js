import { describe, it, expect } from 'vitest'
import { extractModelText, normalizeTextList } from '../chatContent'

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
})

