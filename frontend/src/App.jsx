/**
 * EPC Intelligence Platform - Main App Component (Premium Design)
 * 
 * Full app shell with React Router, premium dark theme, and responsive layout.
 * Routes all six agent modules: RFI, Compliance, Schedule, Supply Chain, Commissioning, Dashboard
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
      <div className="flex h-screen bg-[#0A0A0F] text-white">
        {/* Sidebar */}
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

        {/* Main Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Header Bar */}
          <header className="bg-[#0A0A0F]/80 backdrop-blur-md border-b border-white/5 sticky top-0 z-50 px-6 py-3.5 flex items-center justify-between h-14">
            {/* Mobile Menu Button */}
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="md:hidden p-2 hover:bg-white/5 rounded-lg transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>

            {/* Page Title */}
            <div>
              <span className="text-white font-semibold text-base">EPC Intelligence Platform</span>
            </div>

            {/* Project Name & Status */}
            <div className="flex items-center gap-3">
              <div className="text-slate-400 text-sm">
                Hyperscale DC — Phase 1
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></span>
                <span className="text-emerald-400 text-xs font-medium">LIVE</span>
              </div>
            </div>
          </header>

          {/* Page Content */}
          <main className="flex-1 overflow-auto bg-[#0A0A0F]">
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
