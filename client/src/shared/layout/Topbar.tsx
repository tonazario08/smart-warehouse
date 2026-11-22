import type { ReactNode } from 'react'
import { Breadcrumbs } from './Breadcrumbs'

export function Topbar({ menu }: { menu: ReactNode }) {
  return <header className="app-topbar">{menu}<Breadcrumbs /></header>
}
