import { Breadcrumbs } from './Breadcrumbs'
import searchIcon from '../assets/figma/search.svg'
import notificationIcon from '../assets/figma/notification.svg'
export function Topbar() { return <header className="app-topbar"><Breadcrumbs /><div className="topbar-actions"><div className="topbar-search" title="Tìm kiếm toàn hệ thống chưa khả dụng"><img alt="" src={searchIcon} /><input aria-label="Tìm kiếm toàn hệ thống chưa khả dụng" disabled placeholder="Tìm kiếm chưa khả dụng" type="search" /></div><button aria-label="Thông báo chưa khả dụng" className="topbar-notification" disabled title="Thông báo chưa khả dụng" type="button"><img alt="" src={notificationIcon} /></button></div></header> }
