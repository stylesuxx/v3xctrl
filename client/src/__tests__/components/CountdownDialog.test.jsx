import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import '@/lib/i18n'
import { CountdownDialog } from '@/components/shared/CountdownDialog'

describe('CountdownDialog', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders nothing when not open', () => {
    const { container } = render(
      <CountdownDialog
        open={false}
        title="Test"
        message="Testing..."
        countdownSeconds={5}
      />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders title and message when open', () => {
    render(
      <CountdownDialog
        open={true}
        title="Shutting down"
        message="Shutting down..."
        countdownSeconds={10}
      />,
    )
    expect(screen.getByText('Shutting down')).toBeInTheDocument()
    expect(screen.getByText('Shutting down...')).toBeInTheDocument()
  })

  it('shows countdown seconds', () => {
    render(
      <CountdownDialog
        open={true}
        title="Test"
        message="Testing..."
        countdownSeconds={30}
      />,
    )
    expect(screen.getByText('30 seconds')).toBeInTheDocument()
  })

  it('counts down over time', () => {
    vi.useFakeTimers()
    render(
      <CountdownDialog
        open={true}
        title="Test"
        message="Testing..."
        countdownSeconds={5}
      />,
    )

    expect(screen.getByText('5 seconds')).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(screen.getByText('4 seconds')).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(screen.getByText('3 seconds')).toBeInTheDocument()
  })

  it('shows end state after countdown completes', () => {
    vi.useFakeTimers()
    const onEnd = vi.fn()

    render(
      <CountdownDialog
        open={true}
        title="Shutting down"
        message="Shutting down..."
        countdownSeconds={2}
        onCountdownEnd={onEnd}
        endTitle="Shutdown complete"
        endMessage="Safe to turn off."
      />,
    )

    act(() => {
      vi.advanceTimersByTime(2000)
    })

    expect(screen.getByText('Shutdown complete')).toBeInTheDocument()
    expect(screen.getByText('Safe to turn off.')).toBeInTheDocument()
    expect(onEnd).toHaveBeenCalledTimes(1)
  })

  it('resets when closed and reopened', () => {
    vi.useFakeTimers()

    const { rerender } = render(
      <CountdownDialog
        open={true}
        title="Test"
        message="Testing..."
        countdownSeconds={5}
      />,
    )

    act(() => {
      vi.advanceTimersByTime(3000)
    })

    rerender(
      <CountdownDialog
        open={false}
        title="Test"
        message="Testing..."
        countdownSeconds={5}
      />,
    )

    rerender(
      <CountdownDialog
        open={true}
        title="Test"
        message="Testing..."
        countdownSeconds={5}
      />,
    )

    expect(screen.getByText('5 seconds')).toBeInTheDocument()
  })
})
