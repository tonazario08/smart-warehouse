import { Outlet } from 'react-router-dom'
import { useAuth } from '../../app/AuthProvider'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
export function AppShell() { const { user, logout } = useAuth(); if (!user) return null; return <div className="app-frame"><Sidebar onLogout={logout} user={user} /><div className="app-main"><Topbar /><main className="app-content"><Outlet /></main></div></div> }
