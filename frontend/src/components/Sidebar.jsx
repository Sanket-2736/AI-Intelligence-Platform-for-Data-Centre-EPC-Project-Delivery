/**
 * Navigation Sidebar Component
 * 
 * Dark sidebar with nav items, icons, and active state highlighting.
 * Responsive: hidden on mobile by default, hamburger toggles visibility.
 */

import { useLocation, useNavigate } from 'react-router-dom';
import {
  BarChart3,
  MessageSquare,
  CheckCircle,
  Calendar,
  Ship,
  Zap,
} from 'lucide-react';

export default function Sidebar({ open, onClose }) {
  const location = useLocation();
  const navigate = useNavigate();

  const navItems = [
    { path: '/', label: 'Dashboard', icon: BarChart3, emoji: '📊' },
    { path: '/rfi', label: 'RFI Intelligence', icon: MessageSquare, emoji: '💬' },
    { path: '/compliance', label: 'Spec Compliance', icon: CheckCircle, emoji: '✅' },
    { path: '/schedule', label: 'Schedule Risk', icon: Calendar, emoji: '📅' },
    { path: '/supply-chain', label: 'Supply Chain', icon: Ship, emoji: '🚢' },
    { path: '/commissioning', label: 'Commissioning', icon: Zap, emoji: '⚡' },
  ];

  const handleNavigate = (path) => {
    navigate(path);
    onClose();
  };

  const isActive = (path) => location.pathname === path;

  return (
    <>
      {/* Mobile Overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 md:hidden z-30"
          onClick={onClose}
        ></div>
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed md:static inset-y-0 left-0 w-64 bg-gray-900 border-r border-gray-800
          transition-transform duration-300 transform z-40
          ${open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
          flex flex-col
        `}
      >
        {/* Logo Section */}
        <div className="px-6 py-6 border-b border-gray-800">
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            ⚡ <span>EPC Intel</span>
          </h1>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.path);

            return (
              <button
                key={item.path}
                onClick={() => handleNavigate(item.path)}
                className={`
                  w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all
                  ${
                    active
                      ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                      : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                  }
                `}
              >
                <Icon size={20} />
                <span className="font-medium text-sm">{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="border-t border-gray-800 px-6 py-4 space-y-3">
          <div className="text-xs text-gray-500">
            <div className="bg-gray-800 px-3 py-2 rounded text-center font-mono">
              v1.0 MVP
            </div>
          </div>
          <div className="text-xs text-gray-600 text-center">
            Powered by <span className="text-purple-400 font-semibold">Cerebras</span>
          </div>
        </div>
      </aside>
    </>
  );
}
