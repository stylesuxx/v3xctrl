import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import '@/lib/i18n'
import { useConnectionStore } from '@/stores/connection'
import { useServicesStore } from '@/stores/services'
import { createApiClient } from '@/api/client'
import { ServicesPage } from '@/pages/ServicesPage'

const BASE = 'http://test-device'

describe('ServicesPage', () => {
  beforeEach(() => {
    useConnectionStore.setState({
      apiClient: createApiClient(BASE),
      connected: true,
    })
    useServicesStore.setState({
      services: [],
      loading: false,
      error: null,
      actionsInProgress: {},
      logContent: null,
      logServiceName: null,
      logLoading: false,
    })
  })

  it('shows loading state initially', () => {
    render(<ServicesPage />)
    expect(screen.getByText(/loading services/i)).toBeInTheDocument()
  })

  it('displays services after loading', async () => {
    render(<ServicesPage />)
    await waitFor(() => {
      expect(screen.getByText('v3xctrl-video')).toBeInTheDocument()
      expect(screen.getByText('v3xctrl-control')).toBeInTheDocument()
    })
  })

  it('shows correct status for active services', async () => {
    render(<ServicesPage />)
    await waitFor(() => {
      const activeStatuses = screen.getAllByText('Active')
      expect(activeStatuses.length).toBeGreaterThan(0)
    })
  })

  it('shows spinner for service with action in progress', () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-video', type: 'simple', state: 'active', result: 'success' },
        { name: 'v3xctrl-control', type: 'simple', state: 'inactive', result: 'success' },
      ],
      actionsInProgress: { 'v3xctrl-video': true },
    })

    const { container } = render(<ServicesPage />)

    const spinner = container.querySelector('.animate-spin')
    expect(spinner).toBeInTheDocument()
    expect(screen.getByText('Inactive')).toBeInTheDocument()
  })

  it('disables action buttons for service with action in progress', () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-video', type: 'simple', state: 'active', result: 'success' },
      ],
      actionsInProgress: { 'v3xctrl-video': true },
    })

    render(<ServicesPage />)

    const stopButton = screen.getByText('Stop')
    expect(stopButton).toBeDisabled()
  })

  it('shows error state with retry button', () => {
    useServicesStore.setState({
      error: 'Network error',
      services: [],
    })

    render(<ServicesPage />)
    expect(screen.getByText(/failed to load data/i)).toBeInTheDocument()
    expect(screen.getByText('Retry')).toBeInTheDocument()
  })

  it('shows no services message when list is empty', () => {
    useServicesStore.setState({
      services: [],
      loading: false,
      error: null,
    })

    // Need to prevent fetchServices from running
    useServicesStore.setState({
      fetchServices: () => {},
    })

    render(<ServicesPage />)
    expect(screen.getByText(/no service info/i)).toBeInTheDocument()
  })

  it('shows start button for inactive simple services', () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-control', type: 'simple', state: 'inactive', result: 'success' },
      ],
    })

    render(<ServicesPage />)
    expect(screen.getByText('Start')).toBeInTheDocument()
  })

  it('shows stop button for active simple services', () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-video', type: 'simple', state: 'active', result: 'success' },
      ],
    })

    render(<ServicesPage />)
    expect(screen.getByText('Stop')).toBeInTheDocument()
  })

  it('shows restart button for oneshot services', () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-setup-env', type: 'oneshot', state: 'active', result: 'success' },
      ],
    })

    render(<ServicesPage />)
    expect(screen.getByText('Restart')).toBeInTheDocument()
  })

  it('shows stop button for running oneshot services', () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-setup-env', type: 'oneshot', state: 'activating', result: 'success' },
      ],
    })

    render(<ServicesPage />)
    expect(screen.getByText('Stop')).toBeInTheDocument()
  })

  it('shows correct status labels for different service types', () => {
    useServicesStore.setState({
      services: [
        { name: 'svc-active', type: 'simple', state: 'active', result: 'success' },
        { name: 'svc-inactive', type: 'simple', state: 'inactive', result: 'success' },
        { name: 'svc-oneshot-ran', type: 'oneshot', state: 'active', result: 'success' },
        { name: 'svc-forking-fail', type: 'forking', state: 'inactive', result: 'exit-code' },
      ],
    })

    render(<ServicesPage />)
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Inactive')).toBeInTheDocument()
    expect(screen.getByText('Ran')).toBeInTheDocument()
    expect(screen.getByText('Failed')).toBeInTheDocument()
  })

  it('renders show logs buttons for all services', () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-video', type: 'simple', state: 'active', result: 'success' },
        { name: 'v3xctrl-control', type: 'simple', state: 'inactive', result: 'success' },
      ],
    })

    render(<ServicesPage />)
    const logButtons = screen.getAllByText('Show logs')
    expect(logButtons).toHaveLength(2)
  })

  it('shows log modal with content', () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-video', type: 'simple', state: 'active', result: 'success' },
      ],
      logContent: 'Jan 01 00:00:00 test log line',
      logServiceName: 'v3xctrl-video',
      logLoading: false,
    })

    const { container } = render(<ServicesPage />)
    // Modal should be visible
    const modal = container.querySelector('.fixed.inset-0')
    expect(modal).toBeInTheDocument()
    expect(screen.getByText('Jan 01 00:00:00 test log line')).toBeInTheDocument()
  })

  it('shows loading spinner in log modal', () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-video', type: 'simple', state: 'active', result: 'success' },
      ],
      logLoading: true,
      logServiceName: 'v3xctrl-video',
    })

    const { container } = render(<ServicesPage />)
    // Modal should be visible
    const modal = container.querySelector('.fixed.inset-0')
    expect(modal).toBeInTheDocument()
    // Should have a spinner
    const spinner = modal.querySelector('.animate-spin')
    expect(spinner).toBeInTheDocument()
  })

  it('closes log modal on Escape key', () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-video', type: 'simple', state: 'active', result: 'success' },
      ],
      logContent: 'test log',
      logServiceName: 'v3xctrl-video',
      logLoading: false,
    })

    render(<ServicesPage />)
    expect(screen.getByText('test log')).toBeInTheDocument()

    fireEvent.keyDown(document, { key: 'Escape' })

    // clearLog should have been called
    const state = useServicesStore.getState()
    expect(state.logContent).toBeNull()
    expect(state.logServiceName).toBeNull()
  })

  it('auto-refreshes services on an interval', () => {
    vi.useFakeTimers()
    const fetchServices = vi.fn()
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-video', type: 'simple', state: 'active', result: 'success' },
      ],
      fetchServices,
    })

    render(<ServicesPage />)
    // Initial call on mount
    expect(fetchServices).toHaveBeenCalledTimes(1)

    // Advance 5 seconds - should trigger another fetch
    vi.advanceTimersByTime(5000)
    expect(fetchServices).toHaveBeenCalledTimes(2)

    // Advance another 5 seconds
    vi.advanceTimersByTime(5000)
    expect(fetchServices).toHaveBeenCalledTimes(3)

    vi.useRealTimers()
  })

  it('shows refresh button with spinner when loading', () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-video', type: 'simple', state: 'active', result: 'success' },
      ],
      loading: true,
    })

    render(<ServicesPage />)
    const refreshButton = screen.getByText('Refresh')
    expect(refreshButton).toBeDisabled()
    const spinner = refreshButton.querySelector('.animate-spin')
    expect(spinner).toBeInTheDocument()
  })
})
