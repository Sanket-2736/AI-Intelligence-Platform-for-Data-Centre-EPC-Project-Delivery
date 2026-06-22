/**
 * Spec Compliance Agent Page
 * 
 * Three sections:
 * - TOP: Upload & compliance check
 * - MIDDLE: Results and findings
 * - BOTTOM: NC dashboard
 */

import { useState, useEffect } from 'react';
import { Upload, CheckCircle, AlertTriangle } from 'lucide-react';
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

  const getComplianceColor = (status) => {
    if (status === 'COMPLIANT') return 'green';
    if (status === 'MINOR_DEVIATIONS') return 'yellow';
    if (status === 'MAJOR_DEVIATIONS') return 'orange';
    return 'red';
  };

  return (
    <div className="p-6 space-y-6 overflow-y-auto">
      {/* TOP SECTION - Upload & Check */}
      <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
        <h2 className="text-xl font-bold mb-4">Compliance Analysis</h2>

        <div className="grid grid-cols-2 gap-6 mb-6">
          <div>
            <label className="text-sm font-semibold text-gray-300 mb-2 block">
              Master Specification
            </label>
            <FileUpload
              accept=".pdf"
              label="Upload Specification (PDF)"
              onFileSelect={(files) => setSpecFile(files[0])}
            />
            {specFile && (
              <p className="text-xs text-green-400 mt-2">✓ {specFile.name}</p>
            )}
          </div>

          <div>
            <label className="text-sm font-semibold text-gray-300 mb-2 block">
              Vendor Submittal
            </label>
            <FileUpload
              accept=".pdf"
              label="Upload Submittal (PDF)"
              onFileSelect={(files) => setSubmittalFile(files[0])}
            />
            {submittalFile && (
              <p className="text-xs text-green-400 mt-2">✓ {submittalFile.name}</p>
            )}
          </div>
        </div>

        <div className="mb-6">
          <label className="text-sm font-semibold text-gray-300 mb-2 block">
            Equipment Type
          </label>
          <input
            type="text"
            value={equipmentType}
            onChange={(e) => setEquipmentType(e.target.value)}
            placeholder="e.g., UPS System, Chiller, Switchgear"
            className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400"
          />
        </div>

        <button
          onClick={handleRunCheck}
          disabled={loading || !specFile || !submittalFile}
          className="w-full px-6 py-3 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 rounded-lg text-white font-semibold transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <LoadingSpinner size="sm" message="" />
              Analyzing...
            </>
          ) : (
            <>
              <CheckCircle size={20} />
              Run Compliance Check
            </>
          )}
        </button>
      </div>

      {/* MIDDLE SECTION - Results */}
      {results && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
          {/* Status Banner */}
          <div
            className={`mb-6 p-6 rounded-lg ${
              results.overall_status === 'COMPLIANT'
                ? 'bg-green-500/10 border border-green-500/30'
                : results.overall_status === 'MINOR_DEVIATIONS'
                ? 'bg-yellow-500/10 border border-yellow-500/30'
                : 'bg-red-500/10 border border-red-500/30'
            }`}
          >
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold mb-2">
                  {results.overall_status?.replace(/_/g, ' ')}
                </h3>
                <p className="text-sm text-gray-300">{results.summary}</p>
              </div>
              <div className="text-right">
                <p className="text-4xl font-bold">
                  {results.compliance_score}%
                </p>
                <p className="text-xs text-gray-400">Compliance Score</p>
              </div>
            </div>
          </div>

          {/* Findings Table */}
          {results.findings && results.findings.length > 0 && (
            <div>
              <h4 className="font-semibold mb-4">Findings ({results.findings.length})</h4>
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {results.findings.map((finding) => (
                  <div
                    key={finding.id}
                    className="border-l-4 border-red-500 bg-gray-700/50 p-4 rounded"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <p className="text-sm font-bold text-white">
                          {finding.id}
                        </p>
                        <div className="flex gap-2 mt-1">
                          <StatusBadge status={finding.severity} />
                          <span className="text-xs text-gray-400">
                            {finding.clause_reference}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={() => handleCloseNC(finding.id)}
                        className="text-xs px-2 py-1 bg-green-600 hover:bg-green-700 rounded text-white"
                      >
                        Close
                      </button>
                    </div>

                    <p className="text-xs text-gray-300 mb-2">
                      <span className="font-semibold">Spec:</span>{' '}
                      {finding.spec_requirement}
                    </p>
                    <p className="text-xs text-gray-300 mb-2">
                      <span className="font-semibold">Submittal:</span>{' '}
                      {finding.submittal_value}
                    </p>
                    <p className="text-xs text-gray-400">
                      <span className="font-semibold">Action:</span>{' '}
                      {finding.recommended_action}
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
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6">
            <p className="text-sm text-gray-400 mb-1">Open Critical</p>
            <p className="text-3xl font-bold text-red-400">
              {dashboard.critical || 0}
            </p>
          </div>

          <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-6">
            <p className="text-sm text-gray-400 mb-1">Open Major</p>
            <p className="text-3xl font-bold text-orange-400">
              {dashboard.major || 0}
            </p>
          </div>

          <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-6">
            <p className="text-sm text-gray-400 mb-1">Closed This Week</p>
            <p className="text-3xl font-bold text-green-400">
              {dashboard.closed_this_week || 0}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
