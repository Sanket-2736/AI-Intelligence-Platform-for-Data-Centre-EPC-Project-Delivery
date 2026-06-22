/**
 * Spec Compliance Agent Page (Premium Design)
 * 
 * Three sections:
 * - TOP: Upload & compliance check
 * - MIDDLE: Results and findings
 * - BOTTOM: NC dashboard
 */

import { useState, useEffect } from 'react';
import { CheckCircle, AlertTriangle, FileText } from 'lucide-react';
import FileUpload from '../components/FileUpload';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import { complianceApi } from '../api/client';

export default function ComplianceAgent() {
  const [specFile, setSpecFile] = useState(null);
  const [submittalFile, setSubmittalFile] = useState(null);
  const [equipmentType, setEquipmentType] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [dashboard, setDashboard] = useState(null);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const response = await complianceApi.getDashboard();
      setDashboard(response.data);
    } catch (error) {
      console.error('Error loading dashboard:', error);
    }
  };

  const handleRunCheck = async () => {
    if (!specFile || !submittalFile) {
      alert('Please upload both specification and submittal');
      return;
    }

    setLoading(true);
    try {
      const response = await complianceApi.check(submittalFile, specFile);
      setResults(response.data);
      loadDashboard();
    } catch (error) {
      console.error('Error running compliance check:', error);
      alert('Error running compliance check');
    } finally {
      setLoading(false);
    }
  };

  const handleCloseNC = async (ncId) => {
    try {
      await complianceApi.closeNC(ncId, 'Resolved');
      setResults((prev) => ({
        ...prev,
        findings: prev.findings.filter((f) => f.nc_id !== ncId),
      }));
      loadDashboard();
    } catch (error) {
      console.error('Error closing NC:', error);
    }
  };

  return (
    <div className="p-6 space-y-6 overflow-y-auto bg-[#0A0A0F] min-h-screen">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <CheckCircle size={24} className="text-indigo-400" />
          Spec Compliance Checker
        </h1>
        <p className="text-slate-500 text-sm mt-1">Analyze vendor submittals against specifications</p>
      </div>

      {/* TOP SECTION - Upload & Check */}
      <div className="bg-[#111118] border border-white/[0.06] rounded-2xl shadow-xl shadow-black/20 p-6">
        <h2 className="text-sm font-semibold text-white mb-5">Upload Documents</h2>

        <div className="grid grid-cols-2 gap-6 mb-6">
          <div>
            <label className="section-title">Master Specification</label>
            <FileUpload
              accept=".pdf"
              label="Upload Specification (PDF)"
              onUpload={(file) => setSpecFile(file)}
            />
            {specFile && (
              <div className="flex items-center gap-2 mt-2 p-2 bg-emerald-500/10 rounded-lg">
                <FileText size={16} className="text-emerald-400 flex-shrink-0" />
                <span className="text-xs text-emerald-400">{specFile.name}</span>
              </div>
            )}
          </div>

          <div>
            <label className="section-title">Vendor Submittal</label>
            <FileUpload
              accept=".pdf"
              label="Upload Submittal (PDF)"
              onUpload={(file) => setSubmittalFile(file)}
            />
            {submittalFile && (
              <div className="flex items-center gap-2 mt-2 p-2 bg-emerald-500/10 rounded-lg">
                <FileText size={16} className="text-emerald-400 flex-shrink-0" />
                <span className="text-xs text-emerald-400">{submittalFile.name}</span>
              </div>
            )}
          </div>
        </div>

        <div className="mb-6">
          <label className="section-title">Equipment Type</label>
          <input
            type="text"
            value={equipmentType}
            onChange={(e) => setEquipmentType(e.target.value)}
            placeholder="e.g., UPS System, Chiller, Switchgear"
            className="input-field w-full"
          />
        </div>

        <button
          onClick={handleRunCheck}
          disabled={loading || !specFile || !submittalFile}
          className="w-full px-6 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:opacity-50 rounded-xl text-white font-medium transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <LoadingSpinner size="sm" message="" />
              Analyzing...
            </>
          ) : (
            <>
              <CheckCircle size={18} />
              Run Compliance Check
            </>
          )}
        </button>
      </div>

      {/* MIDDLE SECTION - Results */}
      {results && (
        <div className="bg-[#111118] border border-white/[0.06] rounded-2xl shadow-xl shadow-black/20 p-6">
          {/* Status Banner */}
          <div
            className={`mb-6 p-6 rounded-2xl border ${
              results.overall_status === 'COMPLIANT'
                ? 'bg-emerald-500/10 border-emerald-500/30'
                : results.overall_status === 'MINOR_DEVIATIONS'
                ? 'bg-amber-500/10 border-amber-500/30'
                : 'bg-red-500/10 border-red-500/30'
            }`}
          >
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold mb-2 text-white">
                  {results.overall_status?.replace(/_/g, ' ')}
                </h3>
                <p className="text-sm text-slate-400">{results.summary}</p>
              </div>
              <div className="text-right">
                <p className="text-4xl font-bold text-white">
                  {results.compliance_score}%
                </p>
                <p className="text-xs text-slate-600">Compliance Score</p>
              </div>
            </div>
          </div>

          {/* Findings Table */}
          {results.findings && results.findings.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-white mb-4">Findings ({results.findings.length})</h4>
              <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                {results.findings.map((finding) => (
                  <div
                    key={finding.id}
                    className="border-l-4 border-red-500 bg-red-500/5 p-4 rounded-lg"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <p className="text-sm font-bold text-white">
                          {finding.id}
                        </p>
                        <div className="flex gap-2 mt-1">
                          <StatusBadge status={finding.severity} />
                          <span className="text-xs text-slate-600">
                            {finding.clause_reference}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={() => handleCloseNC(finding.id)}
                        className="text-xs px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-white transition-colors flex-shrink-0"
                      >
                        Close
                      </button>
                    </div>

                    <p className="text-xs text-slate-300 mb-2">
                      <span className="font-semibold">Spec:</span> {finding.spec_requirement}
                    </p>
                    <p className="text-xs text-slate-300 mb-2">
                      <span className="font-semibold">Submittal:</span> {finding.submittal_value}
                    </p>
                    <p className="text-xs text-slate-500">
                      <span className="font-semibold">Action:</span> {finding.recommended_action}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* BOTTOM SECTION - NC Dashboard */}
      {dashboard && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-[#111118] border border-white/[0.06] rounded-2xl shadow-xl shadow-black/20 p-6 hover:border-white/10 transition-all">
            <p className="text-sm text-slate-600 mb-2">Open Critical</p>
            <p className="text-3xl font-bold text-red-400">
              {dashboard.critical || 0}
            </p>
          </div>

          <div className="bg-[#111118] border border-white/[0.06] rounded-2xl shadow-xl shadow-black/20 p-6 hover:border-white/10 transition-all">
            <p className="text-sm text-slate-600 mb-2">Open Major</p>
            <p className="text-3xl font-bold text-amber-400">
              {dashboard.major || 0}
            </p>
          </div>

          <div className="bg-[#111118] border border-white/[0.06] rounded-2xl shadow-xl shadow-black/20 p-6 hover:border-white/10 transition-all">
            <p className="text-sm text-slate-600 mb-2">Closed This Week</p>
            <p className="text-3xl font-bold text-emerald-400">
              {dashboard.closed_this_week || 0}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
