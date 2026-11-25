import { RouterProvider } from 'react-router-dom'
import { AuthProvider } from './app/AuthProvider'
import { router } from './app/router'
export function App() { return <AuthProvider><RouterProvider router={router} /></AuthProvider> }
