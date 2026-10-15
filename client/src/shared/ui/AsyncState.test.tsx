import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AsyncState } from './AsyncState'

describe('AsyncState', () => {
  it('announces loading as a live status', () => {
    render(<AsyncState status="loading">Loaded records</AsyncState>)

    expect(screen.getByRole('status')).toHaveTextContent('Loading records')
  })

  it('announces failures and renders the provided message', () => {
    render(<AsyncState status="error" error="Could not load stock.">Loaded records</AsyncState>)

    expect(screen.getByRole('alert')).toHaveTextContent('Could not load stock.')
  })

  it('shows a useful empty message and otherwise renders its content', () => {
    const { rerender } = render(<AsyncState status="empty" emptyMessage="No stock recorded yet." />)
    expect(screen.getByText('No stock recorded yet.')).toBeInTheDocument()

    rerender(<AsyncState status="success"><p>Stock records</p></AsyncState>)
    expect(screen.getByText('Stock records')).toBeInTheDocument()
  })
})
