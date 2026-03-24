import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../mocks/server'
import '@/lib/i18n'
import { useConnectionStore } from '@/stores/connection'
import { createApiClient } from '@/api/client'
import { InfoPage } from '@/pages/InfoPage'

const BASE = 'http://test-device'

describe('InfoPage', () => {
  beforeEach(() => {
    useConnectionStore.setState({
      apiClient: createApiClient(BASE),
      deviceUrl: BASE,
      connected: true,
    })
  })

  it('stays in loading state without apiClient', () => {
    useConnectionStore.setState({
      apiClient: null,
      deviceUrl: null,
      connected: false,
    })

    render(<InfoPage />)
    expect(screen.getByText(/fetching info/i)).toBeInTheDocument()
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

  it('shows error state and retry button on fetch failure', async () => {
    server.use(
      http.get(`${BASE}/system/info`, () =>
        new HttpResponse(
          JSON.stringify({ data: null, error: { message: 'Server error' } }),
          { status: 500 },
        ),
      ),
    )

    render(<InfoPage />)
    await waitFor(() => {
      expect(screen.getByText(/failed to load data/i)).toBeInTheDocument()
      expect(screen.getByText(/retry/i)).toBeInTheDocument()
    })
  })

  it('displays log archives with file sizes', async () => {
    render(<InfoPage />)
    await waitFor(() => {
      expect(screen.getByText('Persistent Logs')).toBeInTheDocument()
      expect(screen.getByText('archive_4_2026-03-23_18-30.tar.gz')).toBeInTheDocument()
      expect(screen.getByText('archive_3_2026-03-22_12-00.tar.gz')).toBeInTheDocument()
      expect(screen.getByText('archive_2_2026-03-21_09-15.tar.gz')).toBeInTheDocument()
      expect(screen.getByText('archive_1_2026-03-20_22-45.tar.gz')).toBeInTheDocument()
    })
  })

  it('formats file sizes correctly', async () => {
    render(<InfoPage />)
    await waitFor(() => {
      expect(screen.getByText('2.5 MB')).toBeInTheDocument()
      expect(screen.getByText('1.0 MB')).toBeInTheDocument()
      expect(screen.getByText('50.0 KB')).toBeInTheDocument()
      expect(screen.getByText('512 B')).toBeInTheDocument()
    })
  })

  it('renders download links with correct URLs', async () => {
    render(<InfoPage />)
    await waitFor(() => {
      const downloadLinks = screen.getAllByText('Download')
      expect(downloadLinks).toHaveLength(4)
      expect(downloadLinks[0].closest('a')).toHaveAttribute(
        'href',
        `${BASE}/system/logs/archive_4_2026-03-23_18-30.tar.gz`,
      )
    })
  })

  it('shows no archives message when archive list is empty', async () => {
    server.use(
      http.get(`${BASE}/system/logs`, () =>
        HttpResponse.json({ data: { archives: [] }, error: null }),
      ),
    )

    render(<InfoPage />)
    await waitFor(() => {
      expect(screen.getByText('test-streamer')).toBeInTheDocument()
    })
    expect(screen.getByText(/no archives available/i)).toBeInTheDocument()
  })

  it('shows no archives message when log fetch fails', async () => {
    server.use(
      http.get(`${BASE}/system/logs`, () =>
        new HttpResponse(null, { status: 500 }),
      ),
    )

    render(<InfoPage />)
    await waitFor(() => {
      expect(screen.getByText('test-streamer')).toBeInTheDocument()
    })
    expect(screen.getByText(/no archives available/i)).toBeInTheDocument()
  })

  it('renders delete buttons for each archive', async () => {
    render(<InfoPage />)
    await waitFor(() => {
      const deleteButtons = screen.getAllByText('Delete')
      expect(deleteButtons).toHaveLength(4)
    })
  })

  it('calls delete API and refreshes list when confirmed', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    let deleteRequested = false
    server.use(
      http.delete(`${BASE}/system/logs/archive_4_2026-03-23_18-30.tar.gz`, () => {
        deleteRequested = true
        return HttpResponse.json({ data: { message: 'Deleted' }, error: null })
      }),
    )

    render(<InfoPage />)
    await waitFor(() => {
      expect(screen.getByText('archive_4_2026-03-23_18-30.tar.gz')).toBeInTheDocument()
    })

    const deleteButtons = screen.getAllByText('Delete')
    await user.click(deleteButtons[0])

    expect(window.confirm).toHaveBeenCalled()
    await waitFor(() => {
      expect(deleteRequested).toBe(true)
    })

    window.confirm.mockRestore()
  })

  it('does not call delete API when confirmation is cancelled', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(false)

    let deleteRequested = false
    server.use(
      http.delete(`${BASE}/system/logs/:filename`, () => {
        deleteRequested = true
        return HttpResponse.json({ data: { message: 'Deleted' }, error: null })
      }),
    )

    render(<InfoPage />)
    await waitFor(() => {
      expect(screen.getByText('archive_4_2026-03-23_18-30.tar.gz')).toBeInTheDocument()
    })

    const deleteButtons = screen.getAllByText('Delete')
    await user.click(deleteButtons[0])

    expect(window.confirm).toHaveBeenCalled()
    expect(deleteRequested).toBe(false)

    window.confirm.mockRestore()
  })
})
