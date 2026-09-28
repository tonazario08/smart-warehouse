import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { AppShell } from './AppShell'

describe('AppShell', () => {
  it('uses semantic landmarks and marks the active route', () => {
    render(<MemoryRouter><AppShell
      title="Warehouse"
      activePath="/stock"
      navigationItems={[
        { label: 'Products', href: '/products' },
        { label: 'Stock', href: '/stock' },
      ]}
    >
      <p>Stock by warehouse</p>
    </AppShell></MemoryRouter>)

    expect(screen.getByRole('banner')).toBeInTheDocument()
    expect(screen.getAllByRole('navigation')).toHaveLength(1)
    expect(screen.getByRole('main')).toHaveTextContent('Stock by warehouse')
    expect(screen.getByRole('link', { name: 'Stock' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Products' })).not.toHaveAttribute('aria-current')
  })

  it('places brand, utility header, navigation, and content in mobile reading order', () => {
    const { container } = render(<MemoryRouter><AppShell
      title="Warehouse"
      activePath="/stock"
      navigationItems={[{ label: 'Stock', href: '/stock' }]}
      utility={<button type="button">Account</button>}
    >
      <p>Stock by warehouse</p>
    </AppShell></MemoryRouter>)

    const landmarks = Array.from(container.querySelectorAll('.shell-brand, .utility-header, .route-rail nav, #main-content'))
    expect(landmarks.map((element) => element.matches('nav') ? 'route-rail nav' : element.className)).toEqual([
      'shell-brand',
      'utility-header',
      'route-rail nav',
      'shell-content',
    ])
    expect(screen.getByRole('button', { name: 'Account' })).toBeInTheDocument()
  })

  it('offers a keyboard reachable skip link to the main content', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><AppShell title="Warehouse" activePath="/stock" navigationItems={[]}>
      <p>Stock by warehouse</p>
    </AppShell></MemoryRouter>)

    const skipLink = screen.getByRole('link', { name: 'Skip to main content' })
    expect(skipLink).toHaveAttribute('href', '#main-content')
    expect(skipLink).toHaveClass('skip-link')
    await user.tab()
    expect(skipLink).toHaveFocus()
  })
})
