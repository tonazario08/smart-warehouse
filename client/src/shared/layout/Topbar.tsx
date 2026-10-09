import { Breadcrumbs } from './Breadcrumbs'
import searchIcon from '../assets/figma/search.svg'
import notificationIcon from '../assets/figma/notification.svg'
export function Topbar() { return <header className="app-topbar"><Breadcrumbs /><div className="topbar-actions"><span className="topbar-search"><img alt="" src={searchIcon} />Tìm kiếm sản phẩm, tồn kho...</span><button aria-label="Thông báo" className="topbar-notification" type="button"><img alt="" src={notificationIcon} /></button></div></header> }
