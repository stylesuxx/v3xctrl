import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@/lib/i18n'
import { Footer } from '@/components/layout/Footer'

describe('Footer', () => {
  it('renders copyright with current year', () => {
    render(<Footer />)
    const year = new Date().getFullYear()
    expect(screen.getByText(new RegExp(`${year}`))).toBeInTheDocument()
  })

  it('renders all social links', () => {
    render(<Footer />)
    expect(screen.getByText('YouTube')).toBeInTheDocument()
    expect(screen.getByText('Discord')).toBeInTheDocument()
    expect(screen.getByText('Instagram')).toBeInTheDocument()
    expect(screen.getByText('Report an issue')).toBeInTheDocument()
  })

  it('renders links with correct targets', () => {
    render(<Footer />)
    const links = screen.getAllByRole('link')
    const externalLinks = links.filter((l) => l.getAttribute('target') === '_blank')
    expect(externalLinks.length).toBe(4)
  })
})
