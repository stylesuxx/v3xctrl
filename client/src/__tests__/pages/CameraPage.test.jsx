import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import '@/lib/i18n'
import { useConnectionStore } from '@/stores/connection'
import { useServicesStore } from '@/stores/services'
import { useConfigStore } from '@/stores/config'
import { useCameraStore } from '@/stores/camera'
import { createApiClient } from '@/api/client'
import { CameraPage } from '@/pages/CameraPage'
import { mockConfig } from '../mocks/data'

const BASE = 'http://test-device'

describe('CameraPage', () => {
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
    })
    useConfigStore.setState({
      config: mockConfig,
      schema: null,
      loading: false,
      error: null,
    })
    useCameraStore.setState({
      settings: {
        brightness: 0,
        contrast: 1.0,
        saturation: 1.0,
        sharpness: 0,
        'lens-position': 0,
        'analogue-gain': 1,
        'exposure-time': 32000,
      },
    })
  })

  it('shows service warning when video service is not active', async () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-video', type: 'simple', state: 'inactive', result: 'success' },
      ],
    })

    render(<CameraPage />)
    await waitFor(() => {
      expect(screen.getByText(/camera settings cannot be applied/i)).toBeInTheDocument()
    })
  })

  it('shows camera controls when video service is active', async () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-video', type: 'simple', state: 'active', result: 'success' },
      ],
    })

    render(<CameraPage />)
    await waitFor(() => {
      expect(screen.getAllByText('Brightness').length).toBeGreaterThan(0)
      expect(screen.getAllByText('Contrast').length).toBeGreaterThan(0)
      expect(screen.getAllByText('Saturation').length).toBeGreaterThan(0)
      expect(screen.getAllByText('Sharpness').length).toBeGreaterThan(0)
    })
  })

  it('shows all camera setting labels', async () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-video', type: 'simple', state: 'active', result: 'success' },
      ],
    })

    render(<CameraPage />)
    await waitFor(() => {
      expect(screen.getAllByText('Lens Position').length).toBeGreaterThan(0)
      expect(screen.getAllByText('Analogue Gain').length).toBeGreaterThan(0)
      expect(screen.getAllByText(/Exposure Time/).length).toBeGreaterThan(0)
    })
  })

  it('renders Set buttons for each setting', async () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-video', type: 'simple', state: 'active', result: 'success' },
      ],
    })

    render(<CameraPage />)
    await waitFor(() => {
      const setButtons = screen.getAllByText('Set')
      expect(setButtons.length).toBe(7)
    })
  })

  it('renders the save settings button', async () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-video', type: 'simple', state: 'active', result: 'success' },
      ],
    })

    render(<CameraPage />)
    await waitFor(() => {
      expect(screen.getByText('Save camera settings')).toBeInTheDocument()
    })
  })

  it('shows info notes for lens, gain, and exposure settings', async () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-video', type: 'simple', state: 'active', result: 'success' },
      ],
    })

    render(<CameraPage />)
    await waitFor(() => {
      expect(screen.getByText(/autofocus is disabled/i)).toBeInTheDocument()
      expect(screen.getByText(/Gain Control/i)).toBeInTheDocument()
      expect(screen.getByText(/Exposure Control/i)).toBeInTheDocument()
    })
  })
})
