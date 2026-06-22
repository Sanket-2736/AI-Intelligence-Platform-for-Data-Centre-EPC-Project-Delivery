/**
 * Commissioning QA Copilot Page
 * 
 * Three-tab layout:
 * - Tab 1: Test Procedures (generate from standards)
 * - Tab 2: Log Results (test library + result logging)
 * - Tab 3: ITP Report (dashboard + PDF download)
 */

import { useState, useEffect } from 'react';
import { Zap, Download, Plus } from 'lucide-react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import { commissioningApi } from '../api/client';

export default function CommissioningAgent() {
  const [activeTab, setActiveTab] = useState('procedures');
  const [system, setSystem] = useState('POWER');
  const [testName, setTestName] = useState('');
  const [tier, setTier] = useState('Tier III');
  const [procedure, setProcedure] = useState(null);
  const [loading, setLoading] = useState(false);
  const [testLibrary, setTestLibrary] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [loggedTests, setLoggedTests] = useState({});
  const [generatingPDF, setGeneratingPDF] = useState(false);
  const [lastGenerated, setLastGenerated] = useState(null);

  useEffect(() => {
    loadTestLibrary();
    loadDashboard();
  }, []);

  const loadTestLibrary = async () => {
    try {
      const response = await commissioningApi.getLibrary();
      setTestLibrary(response.data || []);
    } catch (error) {
      console.error('Error loading test library:', error);
    }
  };

  const loadDashboard = async () => {
    try {
      const response = await commissioningApi.getDashboard();
      setDashboard(response.data);
    } catch (error) {
      console.error('Error loading dashboard:', error);
    }
  };

  const handleGenerateProcedure = async () => {
    if (!testName) {
      alert('Enter a test name');
      return;
    }

    setLoading(true);
    try {
      const response = await commissioningApi.generateProcedure(system, testName, tier);
      setProcedure(response.data);
    } catch (error) {
      console.error('Error generating procedure:', error);
      alert('Error generating procedure');
    } finally {
      setLoading(false);
    }
  };

  const handleLogResult = async (testId, result) => {
    try {
      const record = {
        test_id: testId,
        test_name: testLibrary.find((t) => t.test_id === testId)?.test_name || '',
        system: testLibrary.find((t) => t.test_id === testId)?.system || '',
        result,
        tested_by: 'QA Team',
        test_date: new Date().toISOString().split('T')[0],
        notes: '',
      };

      await commissioningApi.logResult(record);

      setLoggedTests((prev) => ({
        ...prev,
        [testId]: result,
      }));

      loadDashboard();
    } catch (error) {
      console.error('Error logging result:', error);
    }
  };

  const handleDownloadITP = async () => {
    setGeneratingPDF(true);
    try {
      const blob = await commissioningApi.downloadITP('Hyperscale DC', 'QA Team');
      const url = window.URL.createObjectURL(blob.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ITP_${new Date().toISOString().split('T')[0]}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      setLastGenerated(new Date().toLocaleString());
    } catch (error) {
      console.error('Error downloading ITP:', error);
      alert('Error generating PDF');
    } finally {
      setGeneratingPDF(false);
    }
  };

  return (
    <div className="p-6 space-y-6 overflow-y-auto">
      {/* Tabs */}
      <div className="bg-[#111118] border border-white/[0.06] rounded-xl overflow-hidden">
        <div className="flex border-b border-white/[0.06]">
          <button
            onClick={() => setActiveTab('procedures')}
            className={`flex-1 px-6 py-3 font-semibold transition-colors ${
              activeTab === 'procedures'
                ? 'bg-yellow-600 text-white'
                : 'text-slate-600 hover:text-white'
            }`}
          >
            Test Procedures
          </button>
          <button
            onClick={() => setActiveTab('results')}
            className={`flex-1 px-6 py-3 font-semibold transition-colors ${
              activeTab === 'results'
                ? 'bg-yellow-600 text-white'
                : 'text-slate-600 hover:text-white'
            }`}
          >
            Log Results
          </button>
          <button
            onClick={() => setActiveTab('itp')}
            className={`flex-1 px-6 py-3 font-semibold transition-colors ${
              activeTab === 'itp'
                ? 'bg-yellow-600 text-white'
                : 'text-slate-600 hover:text-white'
            }`}
          >
            ITP Report
          </button>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {/* Tab 1: Test Procedures */}
          {activeTab === 'procedures' && (
            <div className="space-y-6">
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="text-sm font-semibold text-slate-300 mb-2 block">
                    System
                  </label>
                  <select
                    value={system}
                    onChange={(e) => setSystem(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-700 border border-white/10 rounded-xl text-white"
                  >
                    <option>POWER</option>
                    <option>COOLING</option>
                    <option>IT</option>
                    <option>FIRE</option>
                    <option>SECURITY</option>
                  </select>
                </div>

                <div>
                  <label className="text-sm font-semibold text-slate-300 mb-2 block">
                    Tier
                  </label>
                  <select
                    value={tier}
                    onChange={(e) => setTier(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-700 border border-white/10 rounded-xl text-white"
                  >
                    <option>Tier III</option>
                    <option>Tier IV</option>
                  </select>
                </div>

                <div>
                  <label className="text-sm font-semibold text-slate-300 mb-2 block">
                    Test Name
                  </label>
                  <input
                    type="text"
                    value={testName}
                    onChange={(e) => setTestName(e.target.value)}
                    placeholder="e.g., UPS Load Test"
                    className="w-full px-3 py-2 bg-gray-700 border border-white/10 rounded-xl text-white placeholder-gray-400"
                  />
                </div>
              </div>

              <button
                onClick={handleGenerateProcedure}
                disabled={loading || !testName}
                className="w-full px-6 py-3 bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-600 rounded-xl text-white font-semibold flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <LoadingSpinner size="sm" message="" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Zap size={20} />
                    Generate Procedure
                  </>
                )}
              </button>

              {procedure && (
                <div className="bg-gray-700/50 rounded-xl p-6 space-y-6">
                  {/* Header */}
                  <div>
                    <h3 className="text-lg font-bold">{procedure.test_name}</h3>
                    <div className="flex gap-2 mt-2">
                      <StatusBadge status={system} />
                      <span className="text-xs text-slate-600">
                        {procedure.estimated_duration_hours}h
                      </span>
                    </div>
                  </div>

                  {/* Safety Warnings */}
                  {procedure.safety_warnings && procedure.safety_warnings.length > 0 && (
                    <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
                      <p className="font-semibold text-red-400 mb-2">⚠️ Safety Warnings</p>
                      <ul className="text-sm text-red-300 space-y-1">
                        {procedure.safety_warnings.map((warning, idx) => (
                          <li key={idx}>• {warning}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Test Steps */}
                  {procedure.test_steps && (
                    <div>
                      <h4 className="font-semibold mb-3">Test Steps</h4>
                      <div className="space-y-3 max-h-96 overflow-y-auto">
                        {procedure.test_steps.map((step, idx) => (
                          <div
                            key={idx}
                            className="bg-[#111118] border border-white/10 rounded-xl p-3"
                          >
                            <p className="font-semibold text-sm mb-2">
                              Step {step.step_num}: {step.action}
                            </p>
                            <div className="text-xs text-slate-600 space-y-1">
                              <p>
                                <span className="font-semibold">Acceptance:</span>{' '}
                                {step.acceptance_criteria}
                              </p>
                              {step.safety_note && (
                                <p className="text-yellow-400">
                                  ⚠️ {step.safety_note}
                                </p>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Acceptance Summary */}
                  {procedure.acceptance_summary && (
                    <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
                      <p className="text-sm text-green-300">
                        <span className="font-semibold">Pass Criteria:</span>{' '}
                        {procedure.acceptance_summary}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Tab 2: Log Results */}
          {activeTab === 'results' && (
            <div>
              <h3 className="font-semibold mb-4">Standard Test Library</h3>
              <div className="grid grid-cols-2 gap-4 max-h-96 overflow-y-auto">
                {testLibrary.map((test) => (
                  <div
                    key={test.test_id}
                    className="bg-gray-700/50 border border-white/10 rounded-xl p-4"
                  >
                    <p className="font-semibold text-sm mb-1">{test.test_name}</p>
                    <div className="flex items-center justify-between mb-3">
                      <StatusBadge status={test.system} />
                      <span className="text-xs text-slate-600">
                        {test.estimated_hours}h
                      </span>
                    </div>

                    {loggedTests[test.test_id] ? (
                      <div className="text-center py-2">
                        <StatusBadge status={loggedTests[test.test_id]} />
                      </div>
                    ) : (
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          onClick={() => handleLogResult(test.test_id, 'PASS')}
                          className="px-2 py-1 bg-green-600 hover:bg-green-700 rounded text-xs font-semibold text-white"
                        >
                          Pass
                        </button>
                        <button
                          onClick={() => handleLogResult(test.test_id, 'FAIL')}
                          className="px-2 py-1 bg-red-600 hover:bg-red-700 rounded text-xs font-semibold text-white"
                        >
                          Fail
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tab 3: ITP Report */}
          {activeTab === 'itp' && (
            <div className="space-y-6">
              {dashboard && (
                <>
                  {/* Pass Rate Donut */}
                  <div className="grid grid-cols-2 gap-6">
                    <div className="bg-gray-700/50 rounded-xl p-6 flex items-center justify-center">
                      <ResponsiveContainer width="100%" height={250}>
                        <PieChart>
                          <Pie
                            data={[
                              {
                                name: 'Pass',
                                value: dashboard.pass_count,
                              },
                              {
                                name: 'Fail',
                                value: dashboard.fail_count,
                              },
                            ]}
                            cx="50%"
                            cy="50%"
                            innerRadius={60}
                            outerRadius={80}
                            dataKey="value"
                          >
                            <Cell fill="#22c55e" />
                            <Cell fill="#ef4444" />
                          </Pie>
                          <Tooltip />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>

                    {/* Stats */}
                    <div className="space-y-2">
                      <div className="bg-green-500/10 rounded-xl p-4">
                        <p className="text-sm text-slate-600">Pass Rate</p>
                        <p className="text-3xl font-bold text-green-400">
                          {dashboard.overall_pass_rate.toFixed(1)}%
                        </p>
                      </div>
                      <div className="bg-gray-700/50 rounded-xl p-4 grid grid-cols-3 gap-2 text-center">
                        <div>
                          <p className="text-xs text-slate-600">Pass</p>
                          <p className="text-xl font-bold text-green-400">
                            {dashboard.pass_count}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-600">Fail</p>
                          <p className="text-xl font-bold text-red-400">
                            {dashboard.fail_count}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-600">Cond</p>
                          <p className="text-xl font-bold text-yellow-400">
                            {dashboard.conditional_count}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* System Breakdown */}
                  <div className="bg-gray-700/50 rounded-xl p-6">
                    <h4 className="font-semibold mb-4">Results by System</h4>
                    <ResponsiveContainer width="100%" height={200}>
                      <BarChart
                        data={Object.entries(dashboard.by_system || {}).map(
                          ([system, counts]) => ({
                            name: system.toUpperCase(),
                            Pass: counts.pass,
                            Fail: counts.fail,
                          })
                        )}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                        <XAxis dataKey="name" stroke="#9ca3af" />
                        <YAxis stroke="#9ca3af" />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
                        />
                        <Legend />
                        <Bar dataKey="Pass" fill="#22c55e" />
                        <Bar dataKey="Fail" fill="#ef4444" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </>
              )}

              {/* PDF Download */}
              <button
                onClick={handleDownloadITP}
                disabled={generatingPDF}
                className="w-full px-6 py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-600 rounded-xl text-white font-semibold flex items-center justify-center gap-2"
              >
                {generatingPDF ? (
                  <>
                    <LoadingSpinner size="sm" message="" />
                    Generating PDF...
                  </>
                ) : (
                  <>
                    <Download size={20} />
                    Generate ITP PDF
                  </>
                )}
              </button>

              {lastGenerated && (
                <p className="text-xs text-slate-600 text-center">
                  Last generated: {lastGenerated}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

