import { useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import {
  HomeIcon,
  MoonIcon,
  LightBulbIcon,
  Cog6ToothIcon,
  Bars3Icon,
  XMarkIcon,
  ArrowRightOnRectangleIcon,
  PresentationChartLineIcon,
} from '@heroicons/react/24/outline'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: HomeIcon },
  { name: 'Sleep Log', href: '/sleep-log', icon: MoonIcon },
  { name: 'Trends', href: '/trends', icon: PresentationChartLineIcon },
  { name: 'Insights', href: '/insights', icon: LightBulbIcon },
  { name: 'Settings', href: '/settings', icon: Cog6ToothIcon },
]

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()
  const { user, logout } = useAuthStore()

  const handleLogout = async () => {
    try {
      await logout()
    } catch (error) {
      console.error('Logout failed:', error)
    }
  }

  return (
    <div className="min-h-screen bg-slate-900">
      {/* Mobile sidebar */}
      <div
        className={`fixed inset-0 z-50 lg:hidden ${sidebarOpen ? 'block' : 'hidden'}`}
      >
        <div
          className="fixed inset-0 bg-slate-900/80"
          onClick={() => setSidebarOpen(false)}
        />
        <div className="fixed inset-y-0 left-0 w-64 bg-slate-800 p-4">
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center space-x-2">
              <MoonIcon className="h-8 w-8 text-blue-500" />
              <span className="text-xl font-bold text-white">Sleep Tracker</span>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              className="text-slate-400 hover:text-white"
            >
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>
          <nav className="space-y-1">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={`flex items-center space-x-3 px-3 py-2 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                  }`}
                >
                  <item.icon className="h-5 w-5" />
                  <span>{item.name}</span>
                </Link>
              )
            })}
          </nav>
        </div>
      </div>

      {/* Desktop sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col">
        <div className="flex flex-col flex-grow bg-slate-800 pt-5 pb-4 overflow-y-auto">
          <div className="flex items-center flex-shrink-0 px-4 mb-8">
            <MoonIcon className="h-8 w-8 text-blue-500" />
            <span className="ml-2 text-xl font-bold text-white">Sleep Tracker</span>
          </div>
          <nav className="mt-5 flex-1 px-2 space-y-1">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`flex items-center space-x-3 px-3 py-2 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                  }`}
                >
                  <item.icon className="h-5 w-5" />
                  <span>{item.name}</span>
                </Link>
              )
            })}
          </nav>
          <div className="flex-shrink-0 px-4 py-4 border-t border-slate-700">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                {user?.photoURL ? (
                  <img
                    className="h-10 w-10 rounded-full"
                    src={user.photoURL}
                    alt=""
                  />
                ) : (
                  <div className="h-10 w-10 rounded-full bg-blue-600 flex items-center justify-center text-white font-medium">
                    {user?.displayName?.[0] || user?.email?.[0] || '?'}
                  </div>
                )}
              </div>
              <div className="ml-3 flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">
                  {user?.displayName || 'User'}
                </p>
                <p className="text-xs text-slate-400 truncate">{user?.email}</p>
              </div>
              <button
                onClick={handleLogout}
                className="ml-2 p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-700"
                title="Sign out"
              >
                <ArrowRightOnRectangleIcon className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Mobile header */}
        <div className="sticky top-0 z-40 lg:hidden bg-slate-800 px-4 py-3 flex items-center">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-slate-400 hover:text-white"
          >
            <Bars3Icon className="h-6 w-6" />
          </button>
          <div className="ml-4 flex items-center">
            <MoonIcon className="h-6 w-6 text-blue-500" />
            <span className="ml-2 text-lg font-bold text-white">Sleep Tracker</span>
          </div>
        </div>

        {/* Page content */}
        <main className="py-6 px-4 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
