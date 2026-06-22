/**
 * Schedule Risk Engine Page (Premium Design)
 * 
 * Three tabs:
 * - Tab 1: Risk Report (critical risks, actions, health status)
 * - Tab 2: Risk Trend (time-series chart)
 * - Tab 3: Weekly Report (markdown report)
 */

import { useState, useEffect } from 'react';
import { Calendar, TrendingDown, Copy, Check } from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import FileUpload from '../components/FileUpload';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import { scheduleApi } from '../api/client';

export default function ScheduleAgent() {
  const [activeTab, setActiveTab] = useState('report');
  const [scheduleFile, setScheduleFile] = useState(null);
  const [baselineFile, setBaselineFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [trendData, setTrendData] = useState([]);
  const [reportData, setReportData] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    loadTrendData();
  }, []);

  const loadTrendData = async () => {
    try {
      const response = await scheduleApi.getTrend();
      setTrendData(response.data?.data || []);
    } catch (error) {
      console.error('Error loading trend data:', error);
    }
  };

  const handleAnalyse = async () => {
    if (!scheduleFile) {
      alert('Please upload a schedule file');
      return;
    }

    setLoading(true);
    try {
      const response = await scheduleApi.analyse(scheduleFile);
      setResults(response.data);
    } catch (error) {
      console.error('Error analysing schedule:', error);
      alert('Error analysing schedule');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateReport = async () => {
    try {
      const response = await scheduleApi.getReport();
      setReportData(response.data.report);
    } catch (error) {
      console.error('Error generating report:', error);
    }
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(reportData);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="p-6 space-y-6 overflow-y-auto bg-[#0A0A0F] min-h-screen">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Calendar size={24} className="text-indigo-400" />
          Schedule Risk Analysis
        </h1>
        <p className="text-slate-500 text-sm mt-1">Identify and mitigate schedule risks</p>
      </div>

      {/* Upload Section */}
      <div className="bg-[#111118] border border-white/[0.06] rounded-2xl shadow-xl shadow-black/20 p-6">
        <h2 className="text-sm font-semibold text-white mb-5">Upload Schedules</h2>

        <div className="grid grid-cols-2 gap-6 mb-6">
          <div>
            <label className="section-title">Current Schedule</label>
            <FileUpload
              accept=".xlsx"
              label="Upload Current Schedule (.xlsx)"
              onUpload={(file) => setScheduleFile(file)}
            />
            {scheduleFile && (
              <div className="flex items-center gap-2 mt-2 p-2 bg-emerald-500/10 rounded-lg">
                <Check size={14} className="text-emerald-400" />
                <span className="text-xs text-emerald-400">{scheduleFile.name}</span>
              </div>
            )}
          </div>

          <div>
            <label className="section-title">Baseline Schedule (Optional)</label>
            <FileUpload
              accept=".xlsx"
              label="Upload Baseline Schedule (.xlsx)"
              onUpload={(file) => setBaselineFile(file)}
            />
            {baselineFile && (
              <div className="flex items-center gap-2 mt-2 p-2 bg-emerald-500/10 rounded-lg">
                <Check size={14} className="text-emerald-400" />
                <span className="text-xs text-emerald-400">{baselineFile.name}</span>
              </div>
            )}
          </div>
        </div>

        <button
          onClick={handleAnalyse}
          disabled={loading || !scheduleFile}
          className="w-full px-6 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:opacity-50 rounded-xl text-white font-medium transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <LoadingSpinner size="sm" message="" />
              Analyzing...
            </>
          ) : (
            <>
              <Calendar size={18} />
              Analyse Schedule
            </>
          )}
        </button>
      </div>

      {/* Tabs */}
      <div className="bg-[#111118] border border-white/[0.06] rounded-2xl shadow-xl shadow-black/20 overflow-hidden">
        <div className="flex border-b border-white/5">
          <button
            onClick={() => setActiveTab('report')}
            className={`flex-1 px-6 py-3 font-medium text-sm transition-colors ${
              activeTab === 'report'
                ? 'bg-indigo-500/20 text-indigo-400 border-b-2 border-indigo-500'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Risk Report
          </button>
          <button
            onClick={() => setActiveTab('trend')}
            className={`flex-1 px-6 py-3 font-medium text-sm transition-colors ${
              activeTab === 'trend'
                ? 'bg-indigo-500/20 text-indigo-400 border-b-2 border-indigo-500'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Risk Trend
          </button>
          <button
            onClick={() => {
              setActiveTab('weekly');
              handleGenerateReport();
            }}
            className={`flex-1 px-6 py-3 font-medium text-sm transition-colors ${
              activeTab === 'weekly'
                ? 'bg-indigo-500/20 text-indigo-400 border-b-2 border-indigo-500'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Weekly Report
          </button>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {/* Tab 1: Risk Report */}
          {activeTab === 'report' && (
            <div className="space-y-6">
              {results ? (
                <>
                  {/* Health Status */}
                  <div className="flex items-center justify-between p-4 bg-white/[0.02] rounded-xl border border-white/5">
                    <div>
                      <p className="text-sm text-slate-600 mb-2">Project Health</p>
                      <StatusBadge status={results.project_health} />
                    </div>
                    <div className="text-right">
                      <p className="text-3xl font-bold text-white">
                        {results.overall_risk_score}
                      </p>
                      <p className="text-xs text-slate-600">Risk Score</p>
                    </div>
                  </div>

                  {/* Executive Summary */}
                  <div className="bg-white/[0.02] rounded-lg p-4 border border-white/5">
                    <p className="text-sm text-slate-300">
                      {results.executive_summary}
                    </p>
                  </div>

                  {/* Critical Risks */}
                  {results.critical_risks && results.critical_risks.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-white mb-3">
                        Critical Risks ({results.critical_risks.length})
                      </h4>
                      <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                        {results.critical_risks.map((risk) => (
                          <div
                            key={risk.risk_id}
                            className="bg-red-500/5 border border-red-500/20 rounded-lg p-4"
                          >
                            <div className="flex items-start justify-between mb-2">
                              <div>
                                <p className="font-semibold text-white">{risk.task_name}</p>
                                <StatusBadge status={risk.severity} />
                              </div>
                              <div className="text-right">
                                <p className="text-lg font-bold text-red-400">
                                  {risk.potential_delay_days}d
                                </p>
                                <p className="text-xs text-slate-600">delay</p>
                              </div>
                            </div>

                            <p className="text-sm text-slate-300 mb-3">
                              {risk.description}
                            </p>

                            {risk.mitigation_options && (
                              <div>
                                <p className="text-xs font-semibold text-slate-500 mb-2">
                                  Mitigation:
                                </p>
                                <ul className="text-xs text-slate-400 space-y-1">
                                  {risk.mitigation_options.map((action, idx) => (
                                    <li key={idx}>
                                      • {action}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Recommended Actions */}
                  {results.recommended_immediate_actions && (
                    <div>
                      <h4 className="text-sm font-semibold text-white mb-3">
                        Recommended Immediate Actions
                      </h4>
                      <ol className="text-sm text-slate-300 space-y-2">
                        {results.recommended_immediate_actions.map(
                          (action, idx) => (
                            <li key={idx} className="flex gap-3">
                              <span className="font-semibold text-indigo-400">
                                {idx + 1}.
                              </span>
                              <span>{action}</span>
                            </li>
                          )
                        )}
                      </ol>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-slate-600 text-center py-12">
                  Upload and analyze a schedule to view risk report
                </p>
              )}
            </div>
          )}

          {/* Tab 2: Risk Trend */}
          {activeTab === 'trend' && (
            <div>
              {trendData.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={trendData}>
                    <defs>
                      <linearGradient id="colorRisk" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366F1" stopOpacity={0.8} />
                        <stop offset="95%" stopColor="#6366F1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="date" stroke="#94A3B8" style={{ fontSize: '12px' }} />
                    <YAxis stroke="#94A3B8" style={{ fontSize: '12px' }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#111118', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                      labelStyle={{ color: '#F1F5F9' }}
                    />
                    <Area
                      type="monotone"
                      dataKey="risk_score_trend"
                      stroke="#6366F1"
                      fillOpacity={1}
                      fill="url(#colorRisk)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-slate-600 text-center py-12">
                  No trend data available
                </p>
              )}
            </div>
          )}

          {/* Tab 3: Weekly Report */}
          {activeTab === 'weekly' && (
            <div>
              {reportData ? (
                <div>
                  <div className="flex gap-2 mb-4">
                    <button
                      onClick={copyToClipboard}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-white text-sm font-medium flex items-center gap-2 transition-colors"
                    >
                      {copied ? (
                        <>
                          <Check size={16} />
                          Copied
                        </>
                      ) : (
                        <>
                          <Copy size={16} />
                          Copy
                        </>
                      )}
                    </button>
                  </div>
                  <div className="bg-white/[0.02] rounded-lg p-4 text-sm text-slate-300 whitespace-pre-wrap max-h-96 overflow-y-auto font-mono border border-white/5">
                    {reportData}
                  </div>
                </div>
              ) : (
                <p className="text-slate-600 text-center py-12">
                  Click on Weekly Report tab to generate
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
