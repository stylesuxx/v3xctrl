import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@/lib/i18n'
import { PwmControl } from '@/components/shared/PwmControl'

describe('PwmControl', () => {
  it('renders label and value', () => {
    render(
      <PwmControl label="Test" value={1500} onChange={() => {}} onSend={() => {}} />
    )
    expect(screen.getAllByText('Test').length).toBeGreaterThan(0)
    expect(screen.getByDisplayValue('1500')).toBeInTheDocument()
  })

  it('calls onChange when input changes', () => {
    const onChange = vi.fn()
    render(
      <PwmControl label="Test" value={1500} onChange={onChange} onSend={() => {}} />
    )
    fireEvent.change(screen.getByDisplayValue('1500'), { target: { value: '1600' } })
    expect(onChange).toHaveBeenCalledWith(1600)
  })

  it('increments by 10 on +10 click', () => {
    const onChange = vi.fn()
    const onSend = vi.fn()
    render(
      <PwmControl label="Test" value={1500} onChange={onChange} onSend={onSend} />
    )
    fireEvent.click(screen.getByText('+10'))
    expect(onChange).toHaveBeenCalledWith(1510)
    expect(onSend).toHaveBeenCalledWith(1510)
  })

  it('decrements by 10 on -10 click', () => {
    const onChange = vi.fn()
    const onSend = vi.fn()
    render(
      <PwmControl label="Test" value={1500} onChange={onChange} onSend={onSend} />
    )
    fireEvent.click(screen.getByText('-10'))
    expect(onChange).toHaveBeenCalledWith(1490)
    expect(onSend).toHaveBeenCalledWith(1490)
  })

  it('sends current value on Send click', () => {
    const onSend = vi.fn()
    render(
      <PwmControl label="Test" value={1500} onChange={() => {}} onSend={onSend} />
    )
    fireEvent.click(screen.getByText('Send'))
    expect(onSend).toHaveBeenCalledWith(1500)
  })
})
