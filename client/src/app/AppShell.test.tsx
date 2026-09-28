import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AppShell } from './AppShell'

describe('AppShell', () => {
  it('uses semantic landmarks and marks the active route', () => {
    render(<AppShell
      title="Warehouse"
      activePath="/stock"
      navigationItems={[
        { label: 'Products', href: '/products' },
        { label: 'Stock', href: '/stock' },
      ]}
    >
      <p>Stock by warehouse</p>
    </AppShell>)

    expect(screen.getByRole('banner')).toBeInTheDocument()
    expect(screen.getAllByRole('navigation')).toHaveLength(1)
    expect(screen.getByRole('main')).toHaveTextContent('Stock by warehouse')
    expect(screen.getByRole('link', { name: 'Stock' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Products' })).not.toHaveAttribute('aria-current')
  })
})
