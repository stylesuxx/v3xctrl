import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import '@/lib/i18n'
import { useConnectionStore } from '@/stores/connection'
import { ReconnectDialog } from '@/components/shared/ReconnectDialog'

describe('ReconnectDialog', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    useConnectionStore.setState({
      deviceUrl: 'http://test-device',
      connected: false,
      connect: vi.fn().mockRejectedValue(new Error('unreachable')),
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders nothing when not open', () => {
    const { container } = render(
      <ReconnectDialog open={false} onReconnected={vi.fn()} onFailed={vi.fn()} />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('shows rebooting message when open', () => {
    render(
      <ReconnectDialog open={true} onReconnected={vi.fn()} onFailed={vi.fn()} />,
    )
    expect(screen.getByText('Rebooting')).toBeInTheDocument()
    expect(screen.getByText(/waiting for streamer/i)).toBeInTheDocument()
  })

  it('shows spinner while polling', () => {
    const { container } = render(
      <ReconnectDialog open={true} onReconnected={vi.fn()} onFailed={vi.fn()} />,
    )
    expect(container.querySelector('.animate-spin')).toBeInTheDocument()
  })

  it('calls onReconnected when connection succeeds', async () => {
    const onReconnected = vi.fn()
    const connectMock = vi.fn().mockResolvedValue(undefined)
    useConnectionStore.setState({ connect: connectMock })

    render(
      <ReconnectDialog open={true} onReconnected={onReconnected} onFailed={vi.fn()} />,
    )

    // First poll at POLL_INTERVAL (5000ms)
    await act(async () => {
      vi.advanceTimersByTime(5000)
    })

    expect(connectMock).toHaveBeenCalled()
    expect(onReconnected).toHaveBeenCalled()
  })

  it('polls with silent option to suppress toast messages', async () => {
    const connectMock = vi.fn().mockRejectedValue(new Error('unreachable'))
    useConnectionStore.setState({ connect: connectMock })

    render(
      <ReconnectDialog open={true} onReconnected={vi.fn()} onFailed={vi.fn()} />,
    )

    await act(async () => {
      vi.advanceTimersByTime(5000)
    })

    expect(connectMock).toHaveBeenCalledWith('http://test-device', { silent: true })
  })

  it('shows failure state after timeout', async () => {
    const onFailed = vi.fn()

    render(
      <ReconnectDialog open={true} onReconnected={vi.fn()} onFailed={onFailed} />,
    )

    // Advance past timeout (90000ms)
    await act(async () => {
      vi.advanceTimersByTime(90000)
    })

    expect(screen.getByText('Reconnect failed')).toBeInTheDocument()
    expect(screen.getByText(/could not reconnect/i)).toBeInTheDocument()

    // Failure display duration (3000ms)
    await act(async () => {
      vi.advanceTimersByTime(3000)
    })

    expect(onFailed).toHaveBeenCalled()
  })

  it('cleans up timers when closed', async () => {
    const { rerender } = render(
      <ReconnectDialog open={true} onReconnected={vi.fn()} onFailed={vi.fn()} />,
    )

    rerender(
      <ReconnectDialog open={false} onReconnected={vi.fn()} onFailed={vi.fn()} />,
    )

    // Advancing time should not cause errors or callbacks
    await act(async () => {
      vi.advanceTimersByTime(100000)
    })
  })
})
