/**
 * Schedule Risk Engine Page
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

  const getHealthColor = (health) => {
    if (health === 'GREEN') return 'green';
    if (health === 'AMBER') return 'orange';
    return 'red';
  };

  return (
    <div className="p-6 space-y-6 overflow-y-auto">
      {/* Upload Section */}
      <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
        <h2 className="text-xl font-bold mb-4">Upload Schedule</h2>

        <div className="grid grid-cols-2 gap-6 mb-6">
          <div>
            <label className="text-sm font-semibold text-gray-300 mb-2 block">
              Current Schedule
            </label>
            <FileUpload
              accept=".xlsx"
              label="Upload Current Schedule (.xlsx)"
              onFileSelect={(files) => setScheduleFile(files[0])}
            />
            {scheduleFile && (
              <p className="text-xs text-green-400 mt-2">✓ {scheduleFile.name}</p>
            )}
          </div>

          <div>
            <label className="text-sm font-semibold text-gray-300 mb-2 block">
              Baseline Schedule (Optional)
            </label>
            <FileUpload
              accept=".xlsx"
              label="Upload Baseline Schedule (.xlsx)"
              onFileSelect={(files) => setBaselineFile(files[0])}
            />
            {baselineFile && (
              <p className="text-xs text-green-400 mt-2">✓ {baselineFile.name}</p>
            )}
          </div>
        </div>

        <button
          onClick={handleAnalyse}
          disabled={loading || !scheduleFile}
          className="w-full px-6 py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 rounded-lg text-white font-semibold transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <LoadingSpinner size="sm" message="" />
              Analyzing...
            </>
          ) : (
            <>
              <Calendar size={20} />
              Analyse Schedule
            </>
          )}
        </button>
      </div>

      {/* Tabs */}
      <div className="bg-gray-800 border border-gray-700 rounded-xl overflow-hidden">
        <div className="flex border-b border-gray-700">
          <button
            onClick={() => setActiveTab('report')}
            className={`flex-1 px-6 py-3 font-semibold transition-colors ${
              activeTab === 'report'
                ? 'bg-blue-600 text-white'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Risk Report
          </button>
          <button
            onClick={() => setActiveTab('trend')}
            className={`flex-1 px-6 py-3 font-semibold transition-colors ${
              activeTab === 'trend'
                ? 'bg-blue-600 text-white'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Risk Trend
          </button>
          <button
            onClick={() => {
              setActiveTab('weekly');
              handleGenerateReport();
            }}
            className={`flex-1 px-6 py-3 font-semibold transition-colors ${
              activeTab === 'weekly'
                ? 'bg-blue-600 text-white'
                : 'text-gray-400 hover:text-white'
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
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-400 mb-1">Project Health</p>
                      <StatusBadge status={results.project_health} />
                    </div>
                    <div className="text-right">
                      <p className="text-3xl font-bold">
                        {results.overall_risk_score}
                      </p>
                      <p className="text-xs text-gray-400">Risk Score</p>
                    </div>
                  </div>

                  {/* Executive Summary */}
                  <div className="bg-gray-700/50 rounded-lg p-4">
                    <p className="text-sm text-gray-300">
                      {results.executive_summary}
                    </p>
                  </div>

                  {/* Critical Risks */}
                  {results.critical_risks && results.critical_risks.length > 0 && (
                    <div>
                      <h4 className="font-semibold mb-3">
                        Critical Risks ({results.critical_risks.length})
                      </h4>
                      <div className="space-y-3 max-h-96 overflow-y-auto">
                        {results.critical_risks.map((risk) => (
                          <div
                            key={risk.risk_id}
                            className="bg-gray-700/50 border border-red-500/30 rounded-lg p-4"
                          >
                            <div className="flex items-start justify-between mb-2">
                              <div>
                                <p className="font-semibold">{risk.task_name}</p>
                                <StatusBadge status={risk.severity} />
                              </div>
                              <div className="text-right">
                                <p className="text-lg font-bold text-red-400">
                                  {risk.potential_delay_days}d
                                </p>
                                <p className="text-xs text-gray-400">delay</p>
                              </div>
                            </div>

                            <p className="text-sm text-gray-300 mb-3">
                              {risk.description}
                            </p>

                            {risk.mitigation_options && (
                              <div>
                                <p className="text-xs font-semibold text-gray-400 mb-2">
                                  Mitigation:
                                </p>
                                <ul className="text-xs text-gray-300 space-y-1">
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
                      <h4 className="font-semibold mb-3">
                        Recommended Immediate Actions
                      </h4>
                      <ol className="text-sm text-gray-300 space-y-2">
                        {results.recommended_immediate_actions.map(
                          (action, idx) => (
                            <li key={idx} className="flex gap-3">
                              <span className="font-semibold">
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
                <p className="text-gray-400 text-center py-12">
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
                      dataKey="risk_score_trend"
                      stroke="#ef4444"
                      fillOpacity={1}
                      fill="url(#colorRisk)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-gray-400 text-center py-12">
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
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white text-sm font-semibold flex items-center gap-2"
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
                  <div className="bg-gray-700/50 rounded-lg p-4 text-sm text-gray-300 whitespace-pre-wrap max-h-96 overflow-y-auto font-mono">
                    {reportData}
                  </div>
                </div>
              ) : (
                <p className="text-gray-400 text-center py-12">
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
