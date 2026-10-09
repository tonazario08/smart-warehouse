import { NavLink } from 'react-router-dom'
import type { Permission } from '../lib/permissions'
import { can } from '../lib/permissions'
import type { Role, User } from '../../types'
import { UserMenu } from './UserMenu'
import warehouseIcon from '../assets/figma/warehouse.svg'
import dashboardIcon from '../assets/figma/dashboard.svg'
import productsIcon from '../assets/figma/products.svg'
import inventoryIcon from '../assets/figma/inventory.svg'
import warehousesIcon from '../assets/figma/warehouses.svg'
import inboundIcon from '../assets/figma/inbound.svg'
import outboundIcon from '../assets/figma/outbound.svg'

type Item = { to: string; label: string; permission: Permission; roles: Role[]; icon: string }
const items: Item[] = [
  { to: '/dashboard', label: 'Bảng điều khiển', permission: 'dashboard:read', roles: ['admin'], icon: dashboardIcon },
  { to: '/products', label: 'Sản phẩm', permission: 'product:read', roles: ['admin', 'client'], icon: productsIcon },
  { to: '/inventory', label: 'Tồn kho', permission: 'inventory:read', roles: ['admin', 'warehouse', 'client'], icon: inventoryIcon },
  { to: '/warehouses', label: 'Kho hàng', permission: 'warehouse:read', roles: ['admin', 'warehouse', 'client'], icon: warehousesIcon },
  { to: '/inbound', label: 'Nhập kho', permission: 'inventory:write', roles: ['admin', 'warehouse'], icon: inboundIcon },
  { to: '/outbound', label: 'Xuất kho', permission: 'inventory:write', roles: ['admin', 'warehouse'], icon: outboundIcon },
]
export function Sidebar({ user, onLogout }: { user: User; onLogout: () => void }) { return <aside className="app-sidebar"><div className="brand"><span className="brand__mark"><img alt="" src={warehouseIcon} /></span><span><strong>Kho thông minh</strong><small>Nền tảng vận hành kho</small></span></div><p className="sidebar-label">KHÔNG GIAN LÀM VIỆC</p><nav className="sidebar-nav" aria-label="Điều hướng chính">{items.filter((item) => item.roles.includes(user.role) && can(user.role, item.permission)).map((item) => <NavLink className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link--active' : ''}`} key={item.to} to={item.to}><img alt="" src={item.icon} /><span>{item.label}</span></NavLink>)}</nav><div className="sidebar-footer"><UserMenu onLogout={onLogout} user={user} /></div></aside> }
