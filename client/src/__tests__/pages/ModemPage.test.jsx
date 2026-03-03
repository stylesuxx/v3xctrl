import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '../mocks/server'
import '@/lib/i18n'
import { useConnectionStore } from '@/stores/connection'
import { useServicesStore } from '@/stores/services'
import { createApiClient } from '@/api/client'
import { ModemPage } from '@/pages/ModemPage'

const BASE = 'http://test-device'

describe('ModemPage', () => {
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
  })

  it('shows service warning when control service is running', async () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-control', type: 'simple', state: 'active', result: 'success' },
      ],
    })

    render(<ModemPage />)
    await waitFor(() => {
      expect(screen.getByText(/modem info cannot be shown/i)).toBeInTheDocument()
    })
  })

  it('fetches and displays modem info when control is inactive', async () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-control', type: 'simple', state: 'inactive', result: 'success' },
      ],
    })

    render(<ModemPage />)
    await waitFor(() => {
      expect(screen.getByText('EC200U V2.0')).toBeInTheDocument()
      expect(screen.getByText('READY')).toBeInTheDocument()
      expect(screen.getByText('1, 3, 7, 20')).toBeInTheDocument()
      expect(screen.getByText('LTE BAND 7')).toBeInTheDocument()
      expect(screen.getByText('Test Carrier')).toBeInTheDocument()
    })
  })

  it('shows loading state while fetching modem info', async () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-control', type: 'simple', state: 'inactive', result: 'success' },
      ],
    })

    // Delay the modem response
    server.use(
      http.get(`${BASE}/modem`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 100))
        return HttpResponse.json({
          data: { version: 'v1', status: 'OK', allowedBands: [], activeBand: '', carrier: '', contexts: [], addresses: [] },
          error: null,
        })
      }),
    )

    render(<ModemPage />)
    expect(screen.getByText(/fetching modem info/i)).toBeInTheDocument()
  })

  it('shows error state on fetch failure', async () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-control', type: 'simple', state: 'inactive', result: 'success' },
      ],
    })

    server.use(
      http.get(`${BASE}/modem`, () =>
        new HttpResponse(
          JSON.stringify({ data: null, error: { message: 'Modem unavailable' } }),
          { status: 500 },
        ),
      ),
    )

    render(<ModemPage />)
    await waitFor(() => {
      expect(screen.getByText(/failed to load data/i)).toBeInTheDocument()
    })
  })

  it('renders modem context and address rows', async () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-control', type: 'simple', state: 'inactive', result: 'success' },
      ],
    })

    render(<ModemPage />)
    await waitFor(() => {
      expect(screen.getByText('Context 1')).toBeInTheDocument()
      expect(screen.getByText('Address 1')).toBeInTheDocument()
      expect(screen.getByText('10.0.0.1')).toBeInTheDocument()
    })
  })

  it('shows reset and refresh buttons', async () => {
    useServicesStore.setState({
      services: [
        { name: 'v3xctrl-control', type: 'simple', state: 'inactive', result: 'success' },
      ],
    })

    render(<ModemPage />)
    await waitFor(() => {
      expect(screen.getByText('Reset')).toBeInTheDocument()
    })
  })
})
