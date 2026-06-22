/**
 * Supply Chain Visibility Map Page
 * 
 * Split view:
 * - LEFT (2/3): Leaflet map with shipment markers
 * - RIGHT (1/3): Alerts panel with recommended actions
 */

import { useState, useEffect } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { AlertCircle, Upload } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import FileUpload from '../components/FileUpload';
import LoadingSpinner from '../components/LoadingSpinner';
import { supplyChainApi } from '../api/client';

export default function SupplyChainMap() {
  const [shipments, setShipments] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [selectedAlternative, setSelectedAlternative] = useState(null);

  useEffect(() => {
    loadMapData();
    loadAlerts();
    loadSummary();
  }, []);

  const loadMapData = async () => {
    try {
      const response = await supplyChainApi.getMapData();
      setShipments(response.data?.features || []);
    } catch (error) {
      console.error('Error loading map data:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadAlerts = async () => {
    try {
      const response = await supplyChainApi.getAlerts();
      setAlerts(response.data || []);
    } catch (error) {
      console.error('Error loading alerts:', error);
    }
  };

  const loadSummary = async () => {
    try {
      const response = await supplyChainApi.getSummary();
      setSummary(response.data);
    } catch (error) {
      console.error('Error loading summary:', error);
    }
  };

  const handleUploadCSV = async (files) => {
    if (!files.length) return;

    try {
      await supplyChainApi.uploadCSV(files[0]);
      setShowUploadModal(false);
      loadMapData();
      loadAlerts();
      loadSummary();
    } catch (error) {
      console.error('Error uploading CSV:', error);
      alert('Error uploading CSV');
    }
  };

  const handleGetAlternatives = async (equipment, supplier) => {
    try {
      const response = await supplyChainApi.getAlternatives(equipment, supplier);
      setSelectedAlternative(response.data);
    } catch (error) {
      console.error('Error getting alternatives:', error);
    }
  };

  const getMarkerColor = (status) => {
    if (status === 'delayed' || status === 'critical') return '#ef4444';
    if (status === 'at_risk') return '#f97316';
    return '#22c55e';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex h-full gap-6 p-6">
      {/* LEFT - Leaflet Map */}
      <div className="flex-1 relative bg-gray-800 border border-gray-700 rounded-xl overflow-hidden">
        <MapContainer
          center={[51.505, -0.09]}
          zoom={4}
          scrollWheelZoom={true}
          style={{ width: '100%', height: '100%' }}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; OpenStreetMap contributors'
          />
          {shipments.map((shipment, idx) => {
            const { coordinates } = shipment.geometry;
            const { properties } = shipment;
            return (
              <CircleMarker
                key={idx}
                center={[coordinates[1], coordinates[0]]}
                radius={8}
                fillColor={getMarkerColor(properties.status)}
                color={getMarkerColor(properties.status)}
                weight={2}
                opacity={0.8}
                fillOpacity={0.7}
              >
                <Popup>
                  <div className="text-sm">
                    <p className="font-bold">{properties.equipment_name}</p>
                    <p className="text-xs text-gray-600">
                      {properties.supplier}
                    </p>
                    <div className="mt-1">
                      <StatusBadge status={properties.status} />
                    </div>
                    <p className="text-xs mt-1">
                      ETA: {properties.eta}
                    </p>
                    <p className="text-xs">
                      Required: {properties.required_on_site}
                    </p>
                    <p className="text-xs font-semibold mt-1">
                      Buffer: {properties.days_buffer}d
                    </p>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>

        {/* Upload Button Overlay */}
        <button
          onClick={() => setShowUploadModal(true)}
          className="absolute top-4 right-4 z-10 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-semibold flex items-center gap-2"
        >
          <Upload size={18} />
          Upload CSV
        </button>

        {/* Upload Modal */}
        {showUploadModal && (
          <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-20 rounded-xl">
            <div className="bg-gray-800 p-6 rounded-xl max-w-md">
              <h3 className="text-lg font-bold mb-4">Upload Shipments CSV</h3>
              <FileUpload
                accept=".csv"
                label="Drop CSV file here"
                onFileSelect={handleUploadCSV}
              />
              <button
                onClick={() => setShowUploadModal(false)}
                className="mt-4 w-full px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white"
              >
                Close
              </button>
            </div>
          </div>
        )}
      </div>

      {/* RIGHT - Alerts Panel */}
      <div className="w-1/3 bg-gray-800 border border-gray-700 rounded-xl p-6 flex flex-col">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
          <AlertCircle size={20} className="text-red-400" />
          At-Risk Deliveries
        </h2>

        {/* Stats Bar */}
        {summary && (
          <div className="grid grid-cols-2 gap-2 mb-4 text-xs">
            <div className="bg-gray-700/50 p-2 rounded">
              <p className="text-gray-400">Total</p>
              <p className="font-bold">{summary.total_shipments}</p>
            </div>
            <div className="bg-green-500/10 p-2 rounded">
              <p className="text-gray-400">On Track</p>
              <p className="font-bold text-green-400">{summary.on_track}</p>
            </div>
            <div className="bg-orange-500/10 p-2 rounded">
              <p className="text-gray-400">At Risk</p>
              <p className="font-bold text-orange-400">{summary.at_risk}</p>
            </div>
            <div className="bg-red-500/10 p-2 rounded">
              <p className="text-gray-400">Delayed</p>
              <p className="font-bold text-red-400">{summary.critical}</p>
            </div>
          </div>
        )}

        {/* Alerts List */}
        <div className="flex-1 overflow-y-auto space-y-2">
          {alerts.length > 0 ? (
            alerts.map((alert, idx) => (
              <div
                key={idx}
                className="bg-gray-700/50 border border-gray-600 rounded-lg p-3"
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="font-semibold text-white">
                      {alert.equipment}
                    </p>
                    <p className="text-xs text-gray-400">{alert.supplier}</p>
                  </div>
                  <div className="text-right">
                    <p
                      className={`text-lg font-bold ${
                        alert.days_buffer < 0
                          ? 'text-red-400'
                          : alert.days_buffer < 7
                          ? 'text-red-400'
                          : 'text-orange-400'
                      }`}
                    >
                      {alert.days_buffer}d
                    </p>
                    <p className="text-xs text-gray-400">buffer</p>
                  </div>
                </div>

                <StatusBadge status={alert.urgency_level} />

                <p className="text-xs text-gray-300 mt-2">
                  {alert.recommended_action}
                </p>

                <button
                  onClick={() =>
                    handleGetAlternatives(alert.equipment, alert.supplier)
                  }
                  className="mt-2 w-full px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-xs text-white font-semibold"
                >
                  Get Alternatives
                </button>
              </div>
            ))
          ) : (
            <p className="text-gray-500 text-center py-6">
              No at-risk shipments 🎉
            </p>
          )}
        </div>

        {/* Alternatives Modal */}
        {selectedAlternative && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-gray-800 p-6 rounded-xl max-w-md max-h-96 overflow-y-auto">
              <h3 className="text-lg font-bold mb-4">Procurement Alternatives</h3>

              {selectedAlternative.alternatives && (
                <div className="space-y-3">
                  {selectedAlternative.alternatives.map((alt, idx) => (
                    <div key={idx} className="bg-gray-700/50 p-3 rounded">
                      <p className="font-semibold text-sm">{alt.option}</p>
                      <div className="flex gap-4 mt-2 text-xs">
                        <div>
                          <p className="text-gray-400">Lead Time</p>
                          <p className="font-bold">
                            {alt.estimated_lead_time_weeks}w
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-400">Risk</p>
                          <StatusBadge status={alt.risk_level} />
                        </div>
                      </div>
                      <p className="text-xs text-gray-300 mt-2">
                        {alt.notes}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              <button
                onClick={() => setSelectedAlternative(null)}
                className="mt-4 w-full px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white"
              >
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
