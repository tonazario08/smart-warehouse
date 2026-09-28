export interface NavigationItem {
  label: string
  href: string
}

export const operationsNavigation: NavigationItem[] = [
  { label: 'Overview', href: '/dashboard' },
  { label: 'Products', href: '/products' },
  { label: 'Warehouses', href: '/warehouses' },
  { label: 'Stock', href: '/stock' },
  { label: 'Movements', href: '/movements' },
]
