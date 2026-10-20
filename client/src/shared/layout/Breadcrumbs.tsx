import { useLocation } from 'react-router-dom'

const labels: Record<string, string> = { dashboard: 'Bảng điều khiển', products: 'Sản phẩm', inventory: 'Tồn kho', warehouses: 'Kho hàng', inbound: 'Nhập kho', outbound: 'Xuất kho', users: 'Người dùng', categories: 'Danh mục', suppliers: 'Nhà cung cấp', transactions: 'Giao dịch', audit: 'Nhật ký quản trị', transfers: 'Chuyển kho', 'purchase-requests': 'Yêu cầu mua hàng' }
export function Breadcrumbs() { const area = useLocation().pathname.split('/').filter(Boolean)[0] ?? 'dashboard'; const label = labels[area] ?? 'Chi tiết'; return <nav className="breadcrumbs" aria-label="Điều hướng vị trí"><span>Không gian làm việc</span><span>/</span><strong>{label}</strong></nav> }
