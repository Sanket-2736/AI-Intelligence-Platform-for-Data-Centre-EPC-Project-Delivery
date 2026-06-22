/**
 * Navigation Sidebar Component (Premium Design)
 * 
 * Modern sidebar with premium styling, smooth interactions, and indigo accent color.
 * Responsive: hidden on mobile by default, hamburger toggles visibility.
 */

import { useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  MessageSquare,
  CheckSquare,
  Calendar,
  Truck,
  Zap,
} from 'lucide-react';

export default function Sidebar({ open, onClose }) {
  const location = useLocation();
  const navigate = useNavigate();

  const navItems = [
    { path: '/', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/rfi', label: 'RFI Intelligence', icon: MessageSquare },
    { path: '/compliance', label: 'Spec Compliance', icon: CheckSquare },
    { path: '/schedule', label: 'Schedule Risk', icon: Calendar },
    { path: '/supply-chain', label: 'Supply Chain', icon: Truck },
    { path: '/commissioning', label: 'Commissioning', icon: Zap },
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
          fixed md:static inset-y-0 left-0 w-60 bg-[#0D0D14] border-r border-white/5
          transition-transform duration-300 transform z-40
          ${open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
          flex flex-col
        `}
      >
        {/* Logo Section */}
        <div className="px-5 py-6 border-b border-white/5">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-indigo-500/20 flex items-center justify-center">
              <Zap size={18} className="text-indigo-400" />
            </div>
            <h1 className="text-lg font-bold text-white tracking-tight">
              EPC Intel
            </h1>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 px-3 py-5 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.path);

            return (
              <button
                key={item.path}
                onClick={() => handleNavigate(item.path)}
                className={`
                  w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-150 text-sm font-medium
                  ${
                    active
                      ? 'bg-indigo-500/15 text-indigo-400 border border-indigo-500/20'
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                  }
                `}
              >
                <Icon size={16} className="flex-shrink-0" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Divider */}
        <div className="border-t border-white/5 mx-3 my-2"></div>

        {/* Footer */}
        <div className="px-3 py-4 space-y-3">
          <div className="text-xs text-slate-600 px-3">
            v1.0 MVP
          </div>
          <div className="flex items-center justify-center gap-1.5 text-xs text-slate-600 px-3">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-500/40"></span>
            <span>Powered by Cerebras</span>
          </div>
        </div>
      </aside>
    </>
  );
}
