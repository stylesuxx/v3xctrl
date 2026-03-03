import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@/lib/i18n'
import { ServiceWarning } from '@/components/shared/ServiceWarning'

describe('ServiceWarning', () => {
  it('renders nothing when not visible', () => {
    const { container } = render(
      <ServiceWarning message="Test warning" visible={false} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders warning when visible', () => {
    render(<ServiceWarning message="Test warning" visible={true} />)
    expect(screen.getByText('Test warning')).toBeInTheDocument()
  })
})
