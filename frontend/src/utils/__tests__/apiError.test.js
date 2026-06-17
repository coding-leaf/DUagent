import { describe, it, expect } from 'vitest'
import { getErrorMessage } from '../apiError'

describe('getErrorMessage', () => {
  it('returns string detail directly', () => {
    const error = { response: { data: { detail: '服务器错误' } } }
    expect(getErrorMessage(error)).toBe('服务器错误')
  })

  it('returns detail.message when detail is object', () => {
    const error = { response: { data: { detail: { message: '权限不足' } } } }
    expect(getErrorMessage(error)).toBe('权限不足')
  })

  it('returns response data message as fallback', () => {
    const error = { response: { data: { message: '资源不存在' } } }
    expect(getErrorMessage(error)).toBe('资源不存在')
  })

  it('returns error.message when no response', () => {
    const error = { message: '网络连接失败' }
    expect(getErrorMessage(error)).toBe('网络连接失败')
  })

  it('returns fallback when error is empty', () => {
    expect(getErrorMessage(null)).toBe('请求失败')
    expect(getErrorMessage(null, '自定义兜底')).toBe('自定义兜底')
  })
})
