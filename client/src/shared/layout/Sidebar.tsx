import { NavLink } from 'react-router-dom'
import type { Permission } from '../lib/permissions'
import { can } from '../lib/permissions'
import type { Role, User } from '../../types'
import { UserMenu } from './UserMenu'
import warehouseIcon from '../assets/figma/warehouse.svg'
import dashboardIcon from '../assets/figma/dashboard.svg'
import dashboardInactiveIcon from '../assets/figma/dashboard-inactive.svg'
import productsIcon from '../assets/figma/products.svg'
import productsActiveIcon from '../assets/figma/products-active.svg'
import inventoryIcon from '../assets/figma/inventory.svg'
import inventoryActiveIcon from '../assets/figma/inventory-active.svg'
import warehousesIcon from '../assets/figma/warehouses.svg'
import inboundIcon from '../assets/figma/inbound.svg'
import outboundIcon from '../assets/figma/outbound.svg'
import usersIcon from '../assets/icons/users.svg'
import categoriesIcon from '../assets/icons/categories.svg'
import suppliersIcon from '../assets/icons/suppliers.svg'
import transactionsIcon from '../assets/icons/transactions.svg'
import auditIcon from '../assets/icons/audit.svg'
import forecastingIcon from '../assets/icons/forecasting.svg'
import replenishmentIcon from '../assets/icons/replenishment.svg'
import anomaliesIcon from '../assets/icons/anomalies.svg'
import gisIcon from '../assets/icons/gis.svg'

type Item = { to: string; label: string; permission: Permission; roles: Role[]; icon: string; activeIcon?: string }
const items: Item[] = [
  { to: '/anomalies', label: 'Bất thường', permission: 'anomaly:read', roles: ['admin', 'warehouse'], icon: anomaliesIcon },
  { to: '/forecasting', label: 'Dự báo', permission: 'forecast:read', roles: ['admin', 'warehouse'], icon: forecastingIcon },
  { to: '/replenishment', label: 'Bổ sung hàng', permission: 'replenishment:read', roles: ['admin', 'warehouse'], icon: replenishmentIcon },
  { to: '/dashboard', label: 'Bảng điều khiển', permission: 'dashboard:read', roles: ['admin'], icon: dashboardInactiveIcon, activeIcon: dashboardIcon },
  { to: '/products', label: 'Sản phẩm', permission: 'product:read', roles: ['admin', 'client'], icon: productsIcon, activeIcon: productsActiveIcon },
  { to: '/inventory', label: 'Tồn kho', permission: 'inventory:read', roles: ['admin', 'warehouse', 'client'], icon: inventoryIcon, activeIcon: inventoryActiveIcon },
  { to: '/warehouses', label: 'Kho hàng', permission: 'warehouse:read', roles: ['admin', 'warehouse', 'client'], icon: warehousesIcon },
  { to: '/gis', label: 'Bản đồ kho', permission: 'gis:read', roles: ['admin', 'warehouse'], icon: gisIcon },
  { to: '/inbound', label: 'Nhập kho', permission: 'inventory:write', roles: ['admin', 'warehouse'], icon: inboundIcon },
  { to: '/outbound', label: 'Xuất kho', permission: 'inventory:write', roles: ['admin', 'warehouse'], icon: outboundIcon },
  { to: '/transfers', label: 'Chuyển kho', permission: 'inventory:history:read', roles: ['admin', 'warehouse'], icon: transactionsIcon },
  { to: '/purchase-requests', label: 'Yêu cầu mua hàng', permission: 'purchase_request:read', roles: ['admin', 'warehouse', 'client'], icon: transactionsIcon },
  { to: '/users', label: 'Người dùng', permission: 'user:manage', roles: ['admin'], icon: usersIcon },
  { to: '/categories', label: 'Danh mục', permission: 'catalog:read', roles: ['admin', 'warehouse', 'client'], icon: categoriesIcon },
  { to: '/suppliers', label: 'Nhà cung cấp', permission: 'supplier:read', roles: ['admin', 'warehouse'], icon: suppliersIcon },
  { to: '/transactions', label: 'Giao dịch', permission: 'inventory:history:read', roles: ['admin', 'warehouse'], icon: transactionsIcon },
  { to: '/audit', label: 'Nhật ký quản trị', permission: 'audit:read', roles: ['admin'], icon: auditIcon },
]
export function Sidebar({ user, onLogout }: { user: User; onLogout: () => void }) { return <aside className="app-sidebar"><div className="brand"><span className="brand__mark"><img alt="" src={warehouseIcon} /></span><span><strong>Kho thông minh</strong><small>Nền tảng vận hành kho</small></span></div><p className="sidebar-label">KHÔNG GIAN LÀM VIỆC</p><nav className="sidebar-nav" aria-label="Điều hướng chính">{items.filter((item) => item.roles.includes(user.role) && can(user.role, item.permission)).map((item) => <NavLink aria-label={item.label} title={item.label} className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link--active' : ''}`} key={item.to} to={item.to}>{({ isActive }) => <><img alt="" src={isActive ? item.activeIcon ?? item.icon : item.icon} /><span>{item.label}</span></>}</NavLink>)}</nav><div className="sidebar-footer"><UserMenu onLogout={onLogout} user={user} /></div></aside> }
