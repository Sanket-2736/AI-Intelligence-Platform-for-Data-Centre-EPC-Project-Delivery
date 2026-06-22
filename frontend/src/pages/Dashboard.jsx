/**
 * Dashboard Page - Command Centre
 * 
 * KPI cards (2x3 grid) + charts (risk trend + NC breakdown) + recent activity feed
 * Fetches data from:
 * - GET /api/dashboard/summary (main dashboard stats)
 * - GET /api/schedule/trend (risk score time-series)
 * - GET /api/compliance/dashboard (NC breakdown)
 * - GET /api/rfi/history (recent RFIs)
 */

import { useState, useEffect } from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { AlertCircle, Package, TrendingUp, Check, BookOpen, MessageSquare } from 'lucide-react';
import KPICard from '../components/KPICard';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import { dashboardApi, scheduleApi, complianceApi, rfiApi } from '../api/client';

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [dashboardData, setDashboardData] = useState(null);
  const [scheduleData, setScheduleData] = useState(null);
  const [complianceData, setComplianceData] = useState(null);
  const [recentRFIs, setRecentRFIs] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        const [dashboard, schedule, compliance, rfis] = await Promise.all([
          dashboardApi.getSummary(),
          scheduleApi.getTrend(),
          complianceApi.getDashboard(),
          rfiApi.getHistory(5),
        ]);

        setDashboardData(dashboard.data);
        setScheduleData(schedule.data);
        setComplianceData(compliance.data);
        setRecentRFIs(rfis.data?.rfis || []);
      } catch (err) {
        console.error('Error fetching dashboard data:', err);
        setError('Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6 text-red-400">
          {error}
        </div>
      </div>
    );
  }

  const data = dashboardData || {};
  const scheduleChartData = scheduleData?.data || [];
  const ncData = [
    { name: 'CRITICAL', value: complianceData?.critical || 0, fill: '#ef4444' },
    { name: 'MAJOR', value: complianceData?.major || 0, fill: '#f97316' },
    { name: 'MINOR', value: complianceData?.minor || 0, fill: '#eab308' },
    { name: 'OBS', value: complianceData?.observation || 0, fill: '#3b82f6' },
  ];

  return (
    <div className="p-6 space-y-6">
      {/* KPI Cards - 2x3 Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <KPICard
          title="Open Critical NCs"
          value={data.open_critical_ncs || 0}
          subtitle="Non-conformances requiring action"
          color="red"
          icon={AlertCircle}
          trend={data.open_critical_ncs > 0 ? 'down' : 'neutral'}
        />
        <KPICard
          title="At-Risk Shipments"
          value={data.at_risk_shipments || 0}
          subtitle="Deliveries within 14-day buffer"
          color="orange"
          icon={Package}
          trend={data.at_risk_shipments > 5 ? 'down' : 'neutral'}
        />
        <KPICard
          title="Schedule Health"
          value={data.schedule_health || 'UNKNOWN'}
          subtitle="Overall project status"
          color={
            data.schedule_health === 'GREEN'
              ? 'green'
              : data.schedule_health === 'RED'
              ? 'red'
              : 'orange'
          }
          icon={TrendingUp}
        />
        <KPICard
          title="Commissioning Pass Rate"
          value={`${data.commissioning_pass_rate || 0}%`}
          subtitle="Tests completed successfully"
          color={data.commissioning_pass_rate >= 90 ? 'green' : 'orange'}
          icon={Check}
          trend={data.commissioning_pass_rate >= 90 ? 'up' : 'neutral'}
        />
        <KPICard
          title="Documents Indexed"
          value={data.documents_indexed || 0}
          subtitle="Project docs in AI knowledge base"
          color="blue"
          icon={BookOpen}
        />
        <KPICard
          title="RFIs Resolved Today"
          value={data.rfis_resolved_today || 0}
          subtitle="Questions answered by AI"
          color="purple"
          icon={MessageSquare}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Schedule Risk Trend */}
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">Schedule Risk Trend</h3>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={scheduleChartData}>
              <defs>
                <linearGradient id="colorRisk" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="date" stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip
                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
              />
              <Area
                type="monotone"
                dataKey="risk_score"
                stroke="#ef4444"
                fillOpacity={1}
                fill="url(#colorRisk)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* NC Severity Breakdown */}
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">NC Severity Breakdown</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={ncData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="name" stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip
                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
              />
              <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                {ncData.map((entry, index) => (
                  <Bar key={index} dataKey="value" fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent Activity Feed */}
      <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
        <h3 className="text-lg font-semibold mb-4">Recent RFI Activity</h3>
        <div className="space-y-3">
          {recentRFIs.length > 0 ? (
            recentRFIs.map((rfi, idx) => (
              <div
                key={idx}
                className="flex items-start justify-between p-4 bg-gray-700/50 rounded-lg border border-gray-600"
              >
                <div className="flex-1">
                  <p className="text-sm text-gray-300 truncate">
                    {rfi.question || 'RFI Question'}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {rfi.created_at || 'Recently'}
                  </p>
                </div>
                <StatusBadge status="PASS" />
              </div>
            ))
          ) : (
            <p className="text-sm text-gray-500 text-center py-6">No recent RFIs</p>
          )}
        </div>
      </div>
    </div>
  );
}
