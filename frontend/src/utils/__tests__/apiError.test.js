import { describe, it, expect } from 'vitest'
import { getErrorMessage, getApiErrorMessage } from '../apiError'

describe('getErrorMessage', () => {
  it('returns string detail directly', () => {
    const error = { response: { data: { detail: '服务器错误' } } }
    expect(getErrorMessage(error)).toBe('服务器错误')
  })

  it('returns detail.message when detail is object', () => {
    const error = { response: { data: { detail: { message: '权限不足' } } } }
    expect(getErrorMessage(error)).toBe('权限不足')
  })

  it('formats FastAPI 422 validation error array with min_length', () => {
    const error = {
      response: {
        data: {
          detail: [
            {
              loc: ['body', 'password'],
              msg: 'String should have at least 6 characters',
              type: 'string_too_short',
              ctx: { min_length: 6 },
            },
          ],
        },
      },
    }
    expect(getErrorMessage(error)).toBe('密码至少 6 个字符')
  })

  it('formats FastAPI 422 validation error array with max_length', () => {
    const error = {
      response: {
        data: {
          detail: [
            {
              loc: ['body', 'username'],
              msg: 'String should have at most 20 characters',
              type: 'string_too_long',
              ctx: { max_length: 20 },
            },
          ],
        },
      },
    }
    expect(getErrorMessage(error)).toBe('用户名最多 20 个字符')
  })

  it('formats generic FastAPI 422 validation error array with custom message', () => {
    const error = {
      response: {
        data: {
          detail: [
            {
              loc: ['body', 'email'],
              msg: 'value is not a valid email address',
              type: 'value_error',
            },
          ],
        },
      },
    }
    expect(getErrorMessage(error)).toBe('电子邮箱: value is not a valid email address')
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

  it('provides getApiErrorMessage alias matching getErrorMessage', () => {
    expect(getApiErrorMessage).toBe(getErrorMessage)
  })
})
