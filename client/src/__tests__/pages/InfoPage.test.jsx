import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import '@/lib/i18n'
import { useConnectionStore } from '@/stores/connection'
import { createApiClient } from '@/api/client'
import { InfoPage } from '@/pages/InfoPage'

const BASE = 'http://test-device'

describe('InfoPage', () => {
  beforeEach(() => {
    useConnectionStore.setState({
      apiClient: createApiClient(BASE),
      connected: true,
    })
  })

  it('shows loading state initially', () => {
    render(<InfoPage />)
    expect(screen.getByText(/fetching info/i)).toBeInTheDocument()
  })

  it('displays hostname and version table after loading', async () => {
    render(<InfoPage />)
    await waitFor(() => {
      expect(screen.getByText('test-streamer')).toBeInTheDocument()
      expect(screen.getByText('v3xctrl')).toBeInTheDocument()
      expect(screen.getByText('1.2.3')).toBeInTheDocument()
    })
  })
})
