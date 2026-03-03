import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@/lib/i18n'
import { useConnectionStore } from '@/stores/connection'
import { createApiClient } from '@/api/client'
import { DmesgPage } from '@/pages/DmesgPage'

const BASE = 'http://test-device'

describe('DmesgPage', () => {
  beforeEach(() => {
    useConnectionStore.setState({
      apiClient: createApiClient(BASE),
      connected: true,
    })
  })

  it('renders refresh button', () => {
    render(<DmesgPage />)
    expect(screen.getByText('Refresh')).toBeInTheDocument()
  })

  it('loads dmesg on refresh click', async () => {
    render(<DmesgPage />)
    fireEvent.click(screen.getByText('Refresh'))
    await waitFor(() => {
      expect(screen.getByDisplayValue(/Linux version/)).toBeInTheDocument()
    })
  })
})
