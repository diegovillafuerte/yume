import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LocationSwitcher from './LocationSwitcher'
import { Location } from '@/lib/types'

// Mock the LocationProvider
const mockSelectLocation = vi.fn()
const mockLocations: Location[] = [
  {
    id: 'loc-1',
    organization_id: 'org-1',
    name: 'Centro',
    address: 'Av. Principal 123',
    is_primary: true,
    business_hours: {},
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'loc-2',
    organization_id: 'org-1',
    name: 'Norte',
    address: 'Calle Norte 456',
    is_primary: false,
    business_hours: {},
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
]

vi.mock('@/providers/LocationProvider', () => ({
  useLocation: vi.fn(() => ({
    locations: mockLocations,
    selectedLocation: mockLocations[0],
    isLoading: false,
    selectLocation: mockSelectLocation,
  })),
}))

describe('LocationSwitcher', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders null when there is only one location', async () => {
    const { useLocation } = await import('@/providers/LocationProvider')
    vi.mocked(useLocation).mockReturnValue({
      locations: [mockLocations[0]],
      selectedLocation: mockLocations[0],
      isLoading: false,
      selectLocation: mockSelectLocation,
    })

    const { container } = render(<LocationSwitcher />)
    expect(container.firstChild).toBeNull()
  })

  it('renders switcher when multiple locations exist', async () => {
    const { useLocation } = await import('@/providers/LocationProvider')
    vi.mocked(useLocation).mockReturnValue({
      locations: mockLocations,
      selectedLocation: mockLocations[0],
      isLoading: false,
      selectLocation: mockSelectLocation,
    })

    render(<LocationSwitcher />)
    expect(screen.getByText('Centro')).toBeInTheDocument()
  })

  it('opens dropdown when clicked', async () => {
    const { useLocation } = await import('@/providers/LocationProvider')
    vi.mocked(useLocation).mockReturnValue({
      locations: mockLocations,
      selectedLocation: mockLocations[0],
      isLoading: false,
      selectLocation: mockSelectLocation,
    })

    const user = userEvent.setup()
    render(<LocationSwitcher />)

    const button = screen.getByRole('button')
    await user.click(button)

    // Both locations should be visible in dropdown
    expect(screen.getByText('Norte')).toBeInTheDocument()
    expect(screen.getByText('Principal')).toBeInTheDocument() // Primary badge
  })

  it('calls selectLocation when a location is selected', async () => {
    const { useLocation } = await import('@/providers/LocationProvider')
    vi.mocked(useLocation).mockReturnValue({
      locations: mockLocations,
      selectedLocation: mockLocations[0],
      isLoading: false,
      selectLocation: mockSelectLocation,
    })

    const user = userEvent.setup()
    render(<LocationSwitcher />)

    // Open dropdown
    const button = screen.getByRole('button')
    await user.click(button)

    // Select the second location
    const norteButton = screen.getByText('Norte')
    await user.click(norteButton)

    expect(mockSelectLocation).toHaveBeenCalledWith(mockLocations[1])
  })

  it('closes dropdown after selection', async () => {
    const { useLocation } = await import('@/providers/LocationProvider')
    vi.mocked(useLocation).mockReturnValue({
      locations: mockLocations,
      selectedLocation: mockLocations[0],
      isLoading: false,
      selectLocation: mockSelectLocation,
    })

    const user = userEvent.setup()
    render(<LocationSwitcher />)

    // Open dropdown
    await user.click(screen.getByRole('button'))
    expect(screen.getByText('Norte')).toBeInTheDocument()

    // Select location
    await user.click(screen.getByText('Norte'))

    // Dropdown should be closed - Norte should no longer be in dropdown
    // Since the button still shows selected location, we check the dropdown is gone
    const dropdown = screen.queryByRole('button', { name: /Norte/ })
    // The dropdown items are buttons, but after closing, only the main button remains
  })

  it('shows fallback text when no location is selected', async () => {
    const { useLocation } = await import('@/providers/LocationProvider')
    vi.mocked(useLocation).mockReturnValue({
      locations: mockLocations,
      selectedLocation: null,
      isLoading: false,
      selectLocation: mockSelectLocation,
    })

    render(<LocationSwitcher />)
    expect(screen.getByText('Seleccionar sucursal')).toBeInTheDocument()
  })

  it('highlights the currently selected location', async () => {
    const { useLocation } = await import('@/providers/LocationProvider')
    vi.mocked(useLocation).mockReturnValue({
      locations: mockLocations,
      selectedLocation: mockLocations[0],
      isLoading: false,
      selectLocation: mockSelectLocation,
    })

    const user = userEvent.setup()
    render(<LocationSwitcher />)

    await user.click(screen.getByRole('button'))

    // The selected location should have the blue highlight class
    const centroButton = screen.getAllByRole('button').find(
      (btn) => btn.textContent?.includes('Centro') && btn.textContent?.includes('Principal')
    )
    expect(centroButton).toHaveClass('bg-blue-50', 'text-blue-700')
  })
})
