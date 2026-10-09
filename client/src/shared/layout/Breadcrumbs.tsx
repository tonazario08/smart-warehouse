import { useLocation } from 'react-router-dom'

const labels: Record<string, string> = { dashboard: 'Bảng điều khiển', products: 'Sản phẩm', inventory: 'Tồn kho', warehouses: 'Kho hàng', inbound: 'Nhập kho', outbound: 'Xuất kho', new: 'Tạo mới', edit: 'Chỉnh sửa' }
export function Breadcrumbs() { const parts = useLocation().pathname.split('/').filter(Boolean); const label = labels[parts.at(-1) ?? 'dashboard'] ?? 'Chi tiết'; return <nav className="breadcrumbs" aria-label="Điều hướng vị trí"><span>Không gian làm việc</span><span>/</span><strong>{label}</strong></nav> }
