import { Navigate, createBrowserRouter } from 'react-router-dom'
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
import { PlaceholderPage } from './PlaceholderPage'
import { RouteGuard } from './RouteGuard'

const page = (title: string) => <PlaceholderPage title={title} />
export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/forgot-password', element: <ForgotPasswordPage /> },
  { path: '/reset-password', element: <ResetPasswordPage /> },
  { element: <RouteGuard />, children: [{ element: <AppShell />, children: [
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
