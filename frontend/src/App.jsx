/**
 * EPC Intelligence Platform - Main App Component
 * 
 * Full app shell with React Router, dark theme, and responsive layout.
 * Routes all six agent modules: RFI, Compliance, Schedule, Supply Chain, Commissioning, Dashboard
 * 
 * Theme: Dark mode (Tailwind) with gray-950 base, gray-900 sidebar
 * Layout: Persistent sidebar (desktop), hamburger (mobile)
 */

import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import RFIAgent from './pages/RFIAgent';
import ComplianceAgent from './pages/ComplianceAgent';
import ScheduleAgent from './pages/ScheduleAgent';
import SupplyChainMap from './pages/SupplyChainMap';
import CommissioningAgent from './pages/CommissioningAgent';

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <Router>
      <div className="flex h-screen bg-gray-950 text-gray-100">
        {/* Sidebar */}
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

        {/* Main Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Header Bar */}
          <header className="bg-gray-900 border-b border-gray-800 px-6 py-4 flex items-center justify-between">
            {/* Mobile Menu Button */}
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="md:hidden p-2 hover:bg-gray-800 rounded-lg transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>

            {/* Logo & Title */}
            <div className="flex items-center gap-3">
              <span className="text-2xl font-bold text-white">⚡ EPC Intelligence</span>
            </div>

            {/* Project Name & Status */}
            <div className="flex items-center gap-4">
              <div className="text-sm text-gray-400">
                Hyperscale DC — Phase 1
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="inline-block w-3 h-3 bg-green-500 rounded-full animate-pulse"></span>
                <span className="text-green-400 font-medium">LIVE</span>
              </div>
            </div>
          </header>

          {/* Page Content */}
          <main className="flex-1 overflow-auto bg-gray-950">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/rfi" element={<RFIAgent />} />
              <Route path="/compliance" element={<ComplianceAgent />} />
              <Route path="/schedule" element={<ScheduleAgent />} />
              <Route path="/supply-chain" element={<SupplyChainMap />} />
              <Route path="/commissioning" element={<CommissioningAgent />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </Router>
  );
}
