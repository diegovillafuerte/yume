import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import axios from 'axios'

// We need to test the interceptor behavior by creating a fresh instance
// since the module-level interceptors are already attached

describe('API client', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('request interceptor', () => {
    it('adds auth_token for non-admin API calls', async () => {
      localStorage.setItem('auth_token', 'user-token-123')

      // Import fresh to get the configured client
      const { api } = await import('./client')

      // Mock the actual request to capture the config
      const mockAdapter = vi.fn().mockResolvedValue({ data: {}, status: 200 })
      api.defaults.adapter = mockAdapter

      await api.get('/locations')

      expect(mockAdapter).toHaveBeenCalled()
      const requestConfig = mockAdapter.mock.calls[0][0]
      expect(requestConfig.headers.Authorization).toBe('Bearer user-token-123')
    })

    it('adds admin_token for admin API calls', async () => {
      localStorage.setItem('admin_token', 'admin-token-456')

      const { api } = await import('./client')
      const mockAdapter = vi.fn().mockResolvedValue({ data: {}, status: 200 })
      api.defaults.adapter = mockAdapter

      await api.get('/admin/stats')

      expect(mockAdapter).toHaveBeenCalled()
      const requestConfig = mockAdapter.mock.calls[0][0]
      expect(requestConfig.headers.Authorization).toBe('Bearer admin-token-456')
    })

    it('does not add Authorization header when no token exists', async () => {
      const { api } = await import('./client')
      const mockAdapter = vi.fn().mockResolvedValue({ data: {}, status: 200 })
      api.defaults.adapter = mockAdapter

      await api.get('/locations')

      expect(mockAdapter).toHaveBeenCalled()
      const requestConfig = mockAdapter.mock.calls[0][0]
      expect(requestConfig.headers.Authorization).toBeUndefined()
    })
  })

  describe('response interceptor', () => {
    it('clears auth and redirects on 401', async () => {
      localStorage.setItem('auth_token', 'expired-token')
      localStorage.setItem('organization', '{}')

      // Mock window.location
      const originalLocation = window.location
      const mockLocation = { href: '' }
      Object.defineProperty(window, 'location', {
        value: mockLocation,
        writable: true,
      })

      const { api } = await import('./client')
      const mockAdapter = vi.fn().mockRejectedValue({
        response: { status: 401 },
      })
      api.defaults.adapter = mockAdapter

      await expect(api.get('/locations')).rejects.toMatchObject({
        response: { status: 401 },
      })

      expect(localStorage.getItem('auth_token')).toBe(null)
      expect(localStorage.getItem('organization')).toBe(null)
      expect(mockLocation.href).toBe('/login')

      // Restore
      Object.defineProperty(window, 'location', {
        value: originalLocation,
        writable: true,
      })
    })

    it('passes through non-401 errors', async () => {
      const { api } = await import('./client')
      const mockAdapter = vi.fn().mockRejectedValue({
        response: { status: 500, data: { error: 'Server error' } },
      })
      api.defaults.adapter = mockAdapter

      await expect(api.get('/locations')).rejects.toMatchObject({
        response: { status: 500 },
      })

      // Should not clear auth on non-401
      // (localStorage was already empty, just verify no redirect)
    })
  })

  describe('configuration', () => {
    it('uses correct base URL', async () => {
      const { api } = await import('./client')
      expect(api.defaults.baseURL).toMatch(/\/api\/v1$/)
    })

    it('sets Content-Type header', async () => {
      const { api } = await import('./client')
      expect(api.defaults.headers['Content-Type']).toBe('application/json')
    })
  })
})
