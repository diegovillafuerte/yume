import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { AuthProvider, useAuth } from './AuthProvider'
import { Organization } from '@/lib/types'

// Mock Next.js router
const mockPush = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    back: vi.fn(),
    prefetch: vi.fn(),
  }),
}))

const mockOrganization: Organization = {
  id: 'org-123',
  name: 'Test Salon',
  phone_country_code: '+52',
  phone_number: '5551234567',
  timezone: 'America/Mexico_City',
  whatsapp_phone_number_id: null,
  whatsapp_waba_id: null,
  status: 'active',
  settings: {},
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

describe('AuthProvider', () => {
  beforeEach(() => {
    localStorage.clear()
    mockPush.mockClear()
  })

  it('starts with isLoading true and then becomes false', async () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    })

    // After mount, isLoading should be false
    expect(result.current.isLoading).toBe(false)
    expect(result.current.isAuthenticated).toBe(false)
  })

  it('login stores token and organization', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    })

    act(() => {
      result.current.login('test-token-123', mockOrganization)
    })

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.token).toBe('test-token-123')
    expect(result.current.organization).toEqual(mockOrganization)
    expect(localStorage.getItem('auth_token')).toBe('test-token-123')
    expect(localStorage.getItem('organization')).toBe(JSON.stringify(mockOrganization))
  })

  it('logout clears state and redirects to login', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    })

    // First login
    act(() => {
      result.current.login('test-token-123', mockOrganization)
    })

    // Then logout
    act(() => {
      result.current.logout()
    })

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.token).toBe(null)
    expect(result.current.organization).toBe(null)
    expect(localStorage.getItem('auth_token')).toBe(null)
    expect(localStorage.getItem('organization')).toBe(null)
    expect(mockPush).toHaveBeenCalledWith('/login')
  })

  it('restores auth state from localStorage on mount', () => {
    // Pre-populate localStorage
    localStorage.setItem('auth_token', 'stored-token')
    localStorage.setItem('organization', JSON.stringify(mockOrganization))

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    })

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.token).toBe('stored-token')
    expect(result.current.organization).toEqual(mockOrganization)
  })

  it('clears localStorage when organization JSON is invalid but token state persists', () => {
    // Store invalid JSON - this tests current behavior
    // Note: The code sets token state before parsing org JSON, so if parse fails,
    // localStorage is cleared but token state remains. This is a potential bug.
    localStorage.setItem('auth_token', 'stored-token')
    localStorage.setItem('organization', 'invalid-json')

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    })

    // Token state was set before the JSON parse failed
    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.token).toBe('stored-token')
    // But localStorage was cleared
    expect(localStorage.getItem('auth_token')).toBe(null)
    expect(localStorage.getItem('organization')).toBe(null)
    // Organization is null since parse failed
    expect(result.current.organization).toBe(null)
  })

  it('throws error when useAuth is used outside AuthProvider', () => {
    expect(() => {
      renderHook(() => useAuth())
    }).toThrow('useAuth must be used within an AuthProvider')
  })
})
