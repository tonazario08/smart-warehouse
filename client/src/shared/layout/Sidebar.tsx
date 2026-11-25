import type { Ref } from 'react'
import { NavLink } from 'react-router-dom'
import type { Permission } from '../lib/permissions'
import { can } from '../lib/permissions'
import type { User } from '../../types'
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
import assistantIcon from '../assets/icons/assistant.svg'

type Item = { to: string; label: string; permission: Permission; icon: string; activeIcon?: string }
const items: Item[] = [
  { to: '/anomalies', label: 'Bất thường', permission: 'anomaly:read', icon: anomaliesIcon },
  { to: '/forecasting', label: 'Dự báo', permission: 'forecast:read', icon: forecastingIcon },
  { to: '/replenishment', label: 'Bổ sung hàng', permission: 'replenishment:read', icon: replenishmentIcon },
  { to: '/assistant', label: 'Trợ lý kho', permission: 'assistant:read', icon: assistantIcon },
  { to: '/dashboard', label: 'Bảng điều khiển', permission: 'dashboard:read', icon: dashboardInactiveIcon, activeIcon: dashboardIcon },
  { to: '/products', label: 'Sản phẩm', permission: 'product:read', icon: productsIcon, activeIcon: productsActiveIcon },
  { to: '/inventory', label: 'Tồn kho', permission: 'inventory:read', icon: inventoryIcon, activeIcon: inventoryActiveIcon },
  { to: '/warehouses', label: 'Kho hàng', permission: 'warehouse:read', icon: warehousesIcon },
  { to: '/gis', label: 'Bản đồ kho', permission: 'gis:read', icon: gisIcon },
  { to: '/inbound', label: 'Nhập kho', permission: 'inventory:write', icon: inboundIcon },
  { to: '/outbound', label: 'Xuất kho', permission: 'inventory:write', icon: outboundIcon },
  { to: '/transfers', label: 'Chuyển kho', permission: 'inventory:history:read', icon: transactionsIcon },
  { to: '/purchase-requests', label: 'Yêu cầu mua hàng', permission: 'purchase_request:read', icon: transactionsIcon },
  { to: '/users', label: 'Người dùng', permission: 'user:manage', icon: usersIcon },
  { to: '/categories', label: 'Danh mục', permission: 'catalog:read', icon: categoriesIcon },
  { to: '/suppliers', label: 'Nhà cung cấp', permission: 'supplier:read', icon: suppliersIcon },
  { to: '/transactions', label: 'Giao dịch', permission: 'inventory:history:read', icon: transactionsIcon },
  { to: '/audit', label: 'Nhật ký quản trị', permission: 'audit:read', icon: auditIcon },
]
const groups = [
  { label: 'Vận hành', paths: ['/dashboard', '/products', '/inventory', '/warehouses', '/inbound', '/outbound', '/transfers', '/purchase-requests'] },
  { label: 'Phân tích và hỗ trợ', paths: ['/anomalies', '/forecasting', '/replenishment', '/gis', '/assistant'] },
  { label: 'Danh mục và quản trị', paths: ['/categories', '/suppliers', '/users', '/transactions', '/audit'] },
]

export function Sidebar({ panelRef, user, onLogout, open, onNavigate }: { panelRef: Ref<HTMLElement>; user: User; onLogout: () => void; open: boolean; onNavigate: () => void }) {
  return <aside ref={panelRef} className={open ? 'app-sidebar app-sidebar--open' : 'app-sidebar'} id="app-navigation-panel">
    <div className="brand"><span className="brand__mark"><img alt="" src={warehouseIcon} /></span><span><strong>Kho thông minh</strong><small>Nền tảng vận hành kho</small></span></div>
    <nav className="sidebar-nav" aria-label="Điều hướng chính">
      {groups.map(group => {
        const allowed = group.paths.flatMap(path => items.filter(item => item.to === path && can(user.role, item.permission)))
        if (!allowed.length) return null
        return <div className="sidebar-group" key={group.label}>
          <p className="sidebar-label">{group.label}</p>
          <ul aria-label={group.label}>{allowed.map(item => <li key={item.to}>
            <NavLink onClick={event => { if (!event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) onNavigate() }} className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link--active' : ''}`} to={item.to}>
              {({ isActive }) => <><img alt="" src={isActive ? item.activeIcon ?? item.icon : item.icon} /><span>{item.label}</span></>}
            </NavLink>
          </li>)}</ul>
        </div>
      })}
    </nav>
    <div className="sidebar-footer"><UserMenu onLogout={onLogout} user={user} /></div>
  </aside>
}
