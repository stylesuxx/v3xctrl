import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '../mocks/server'
import '@/lib/i18n'
import { useConnectionStore } from '@/stores/connection'
import { createApiClient } from '@/api/client'
import { Navbar } from '@/components/layout/Navbar'

const BASE = 'http://test-device'

const TABS = [
  { id: 'editor', labelKey: 'tabs.configEditor' },
  { id: 'services', labelKey: 'tabs.services' },
]

function renderNavbar(props = {}) {
  const defaultProps = {
    tabs: TABS,
    activeTab: 'editor',
    onTabChange: vi.fn(),
    ...props,
  }
  return render(<Navbar {...defaultProps} />)
}

describe('Navbar', () => {
  beforeEach(() => {
    useConnectionStore.setState({
      apiClient: createApiClient(BASE),
      deviceUrl: BASE,
      deviceHostname: 'test-streamer',
      connected: true,
    })
  })

  it('renders brand name', () => {
    renderNavbar()
    expect(screen.getByText('v3xctrl')).toBeInTheDocument()
  })

  it('shows device URL', () => {
    renderNavbar()
    const urlElements = screen.getAllByText(new RegExp(BASE))
    expect(urlElements.length).toBeGreaterThan(0)
  })

  it('shows hostname alongside URL', () => {
    renderNavbar()
    const urlElements = screen.getAllByText(/test-streamer/)
    expect(urlElements.length).toBeGreaterThan(0)
  })

  it('shows URL without hostname when hostname is null', () => {
    useConnectionStore.setState({ deviceHostname: null })
    renderNavbar()
    const urlElements = screen.getAllByText(BASE)
    expect(urlElements.length).toBeGreaterThan(0)
    expect(screen.queryByText(/test-streamer/)).not.toBeInTheDocument()
  })

  it('renders desktop action buttons', () => {
    renderNavbar()
    expect(screen.getAllByText('Disconnect').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Restart').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Shutdown').length).toBeGreaterThan(0)
  })

  it('renders discord link', () => {
    renderNavbar()
    const links = screen.getAllByText(/discord/i)
    expect(links.length).toBeGreaterThan(0)
    const link = links.find((element) => element.closest('a'))
    expect(link.closest('a')).toHaveAttribute('href', 'https://discord.gg/uF4hf8UBBW')
    expect(link.closest('a')).toHaveAttribute('target', '_blank')
  })

  it('opens mobile menu on hamburger click', () => {
    renderNavbar()
    const menuButton = screen.getByRole('button', { name: '' })
    fireEvent.click(menuButton)

    const disconnectButtons = screen.getAllByText('Disconnect')
    expect(disconnectButtons.length).toBeGreaterThanOrEqual(2)
  })

  it('closes mobile menu on second hamburger click', () => {
    renderNavbar()
    const menuButton = screen.getByRole('button', { name: '' })

    fireEvent.click(menuButton)
    expect(screen.getAllByText('Disconnect').length).toBeGreaterThanOrEqual(2)

    fireEvent.click(menuButton)
    // Mobile menu should be closed, only desktop disconnect remains
    expect(screen.getAllByText('Disconnect').length).toBe(1)
  })

  it('disconnects when disconnect is clicked', () => {
    renderNavbar()
    const disconnectButtons = screen.getAllByText('Disconnect')
    fireEvent.click(disconnectButtons[0])

    const state = useConnectionStore.getState()
    expect(state.connected).toBe(false)
    expect(state.deviceUrl).toBeNull()
  })

  it('opens reboot dialog and calls reboot API on restart click', async () => {
    const rebootHandler = vi.fn()
    server.use(
      http.post(`${BASE}/system/reboot`, () => {
        rebootHandler()
        return HttpResponse.json({ data: { message: 'Rebooting...' }, error: null })
      }),
    )

    renderNavbar()
    const restartButtons = screen.getAllByText('Restart')
    fireEvent.click(restartButtons[0])

    await waitFor(() => {
      expect(rebootHandler).toHaveBeenCalled()
    })
    // ReconnectDialog should be open
    expect(screen.getByText(/rebooting/i)).toBeInTheDocument()
  })

  it('opens shutdown dialog on shutdown click', async () => {
    const shutdownHandler = vi.fn()
    server.use(
      http.post(`${BASE}/system/shutdown`, () => {
        shutdownHandler()
        return HttpResponse.json({ data: { message: 'Shutting down...' }, error: null })
      }),
    )

    renderNavbar()
    const shutdownButtons = screen.getAllByText('Shutdown')
    fireEvent.click(shutdownButtons[0])

    await waitFor(() => {
      expect(shutdownHandler).toHaveBeenCalled()
    })
    // CountdownDialog title is "Shutting down" - use getAllByText since title+message both match
    const shutdownTexts = screen.getAllByText(/shutting down/i)
    expect(shutdownTexts.length).toBeGreaterThan(0)
  })

  it('handles reboot API error gracefully', async () => {
    server.use(
      http.post(`${BASE}/system/reboot`, () => {
        return HttpResponse.error()
      }),
    )

    renderNavbar()
    const restartButtons = screen.getAllByText('Restart')
    fireEvent.click(restartButtons[0])

    // Should still open dialog even if API errors (expected during reboot)
    await waitFor(() => {
      expect(screen.getByText(/rebooting/i)).toBeInTheDocument()
    })
  })

  it('closes mobile menu when reboot is clicked from mobile menu', async () => {
    renderNavbar()

    // Open mobile menu
    const menuButton = screen.getByRole('button', { name: '' })
    fireEvent.click(menuButton)
    expect(screen.getAllByText('Restart').length).toBeGreaterThanOrEqual(2)

    // Click restart from mobile menu (last one)
    const restartButtons = screen.getAllByText('Restart')
    fireEvent.click(restartButtons[restartButtons.length - 1])

    // Mobile menu should close
    await waitFor(() => {
      expect(screen.getAllByText('Restart').length).toBe(1)
    })
  })

  it('disconnects from mobile menu and closes menu', () => {
    renderNavbar()

    // Open mobile menu
    const menuButton = screen.getByRole('button', { name: '' })
    fireEvent.click(menuButton)

    // Click disconnect from mobile menu (last one)
    const disconnectButtons = screen.getAllByText('Disconnect')
    fireEvent.click(disconnectButtons[disconnectButtons.length - 1])

    const state = useConnectionStore.getState()
    expect(state.connected).toBe(false)
  })
})