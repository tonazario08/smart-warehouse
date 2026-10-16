import { Navigate, Outlet, createBrowserRouter } from 'react-router-dom'
import { ManagementProvider } from './ManagementProvider'
import { UsersPage } from '../features/users/UsersPage'
import { CategoriesPage } from '../features/categories/CategoriesPage'
import { SuppliersPage } from '../features/suppliers/SuppliersPage'
import { TransactionsPage } from '../features/transactions/TransactionsPage'
import { AuditPage } from '../features/audit/AuditPage'
import { LoginPage } from '../pages/LoginPage'
import { ForgotPasswordPage, ResetPasswordPage } from '../pages/AuthPages'
import { DashboardPage } from '../pages/DashboardPage'
import { ProductFormPage } from '../pages/ProductFormPage'
import { ProductsPage } from '../pages/ProductsPage'
import { InventoryPage } from '../pages/InventoryPage'
import { StockDetailPage } from '../pages/StockDetailPage'
import { WarehousesPage } from '../pages/WarehousesPage'
import { WarehouseDetailPage } from '../pages/WarehouseDetailPage'
import { WarehouseFormPage } from '../pages/WarehouseFormPage'
import { MovementFormPage, MovementListPage } from '../pages/MovementPages'
import { AppShell } from '../shared/layout/AppShell'
import { RouteGuard } from './RouteGuard'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/forgot-password', element: <ForgotPasswordPage /> },
  { path: '/reset-password', element: <ResetPasswordPage /> },
  { element: <RouteGuard />, children: [{ element: <AppShell />, children: [
    { element: <ManagementProvider><Outlet /></ManagementProvider>, children: [
      { path: '/users', element: <RouteGuard permission="user:manage" />, children: [{ index: true, element: <UsersPage /> }] },
      { path: '/categories', element: <RouteGuard permission="catalog:read" />, children: [{ index: true, element: <CategoriesPage /> }] },
      { path: '/suppliers', element: <RouteGuard permission="supplier:read" />, children: [{ index: true, element: <SuppliersPage /> }] },
      { path: '/transactions', element: <RouteGuard permission="inventory:history:read" />, children: [{ index: true, element: <TransactionsPage /> }] },
      { path: '/audit', element: <RouteGuard permission="audit:read" />, children: [{ index: true, element: <AuditPage /> }] },
    ] },
    { index: true, element: <Navigate replace to="/dashboard" /> },
    { path: '/dashboard', element: <RouteGuard permission="dashboard:read" />, children: [{ index: true, element: <DashboardPage /> }] },
    { path: '/products', element: <ProductsPage /> }, { path: '/products/new', element: <RouteGuard permission="product:write" />, children: [{ index: true, element: <ProductFormPage mode="create" /> }] }, { path: '/products/:id/edit', element: <RouteGuard permission="product:write" />, children: [{ index: true, element: <ProductFormPage mode="edit" /> }] },
    { path: '/inventory', element: <InventoryPage /> }, { path: '/inventory/:warehouseId/:productId', element: <StockDetailPage /> },
    { path: '/warehouses', element: <WarehousesPage /> }, { path: '/warehouses/new', element: <RouteGuard permission="warehouse:write" />, children: [{ index: true, element: <WarehouseFormPage mode="create" /> }] }, { path: '/warehouses/:id', element: <WarehouseDetailPage /> }, { path: '/warehouses/:id/edit', element: <RouteGuard permission="warehouse:write" />, children: [{ index: true, element: <WarehouseFormPage mode="edit" /> }] },
    { path: '/inbound', element: <RouteGuard permission="inventory:write" />, children: [{ index: true, element: <MovementListPage type="inbound" /> }, { path: 'new', element: <MovementFormPage type="inbound" /> }] },
    { path: '/outbound', element: <RouteGuard permission="inventory:write" />, children: [{ index: true, element: <MovementListPage type="outbound" /> }, { path: 'new', element: <MovementFormPage type="outbound" /> }] },
  ] }] },
  { path: '*', element: <Navigate replace to="/" /> },
])
