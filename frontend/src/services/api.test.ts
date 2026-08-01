import { afterEach, describe, expect, it, vi } from 'vitest'
import type { InternalAxiosRequestConfig } from 'axios'

vi.mock('./firebase', () => ({ getIdToken: vi.fn() }))

import { getIdToken } from './firebase'
import api, { sleepApi } from './api'

const mockedGetIdToken = vi.mocked(getIdToken)

/** Adapter stub that records the config it was handed and returns an empty 200. */
function stubAdapter() {
  return vi.fn(async (config: InternalAxiosRequestConfig) => ({
    data: {},
    status: 200,
    statusText: 'OK',
    headers: {},
    config,
  }))
}

function authHeader(config: InternalAxiosRequestConfig) {
  const headers = config.headers as unknown as {
    get?: (name: string) => unknown
    Authorization?: unknown
  }
  return typeof headers.get === 'function' ? headers.get('Authorization') : headers.Authorization
}

describe('api auth interceptor', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('attaches the bearer token when the user is signed in', async () => {
    mockedGetIdToken.mockResolvedValue('token-123')
    const adapter = stubAdapter()
    api.defaults.adapter = adapter

    await sleepApi.getRecords()

    expect(adapter).toHaveBeenCalledTimes(1)
    expect(authHeader(adapter.mock.calls[0][0])).toBe('Bearer token-123')
  })

  it('rejects without sending the request when no token is available', async () => {
    mockedGetIdToken.mockResolvedValue(null)
    const adapter = stubAdapter()
    api.defaults.adapter = adapter

    await expect(sleepApi.getRecords()).rejects.toThrow(/not signed in/i)
    expect(adapter).not.toHaveBeenCalled()
  })
})
