/**
 * API Client Configuration
 * 
 * Axios instance with interceptors for:
 * - Request: Add loading state
 * - Response: Global error handling
 * 
 * Exports named API groups for each agent module
 */

import axios from 'axios';

const baseURL = import.meta.env.REACT_APP_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor
client.interceptors.request.use(
  (config) => {
    // Can add loading state here if needed
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor
client.interceptors.response.use(
  (response) => response,
  (error) => {
    // Global error handling
    if (error.response?.status === 422) {
      console.error('Validation Error:', error.response.data);
    } else if (error.response?.status === 500) {
      console.error('Server Error:', error.response.data);
    } else if (error.code === 'ECONNABORTED') {
      console.error('Request Timeout');
    }
    return Promise.reject(error);
  }
);

// ============================================================================
// RFI API
// ============================================================================
export const rfiApi = {
  ingestSingle: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/rfi/ingest/single', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  
  ingestBatch: (files) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    return client.post('/api/rfi/ingest/batch', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  
  query: (question) => client.post('/api/rfi/query', { question }),
  
  getDocuments: () => client.get('/api/rfi/documents'),
  
  getHistory: (limit = 10) => client.get(`/api/rfi/history?limit=${limit}`),
};

// ============================================================================
// COMPLIANCE API
// ============================================================================
export const complianceApi = {
  check: (submittal, spec) => 
    client.post('/api/compliance/check', { submittal, spec }),
  
  ingestSpec: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/compliance/ingest-spec', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  
  getDashboard: () => client.get('/api/compliance/dashboard'),
  
  getNCs: (status = null) => {
    const url = status ? `/api/compliance/ncs?status=${status}` : '/api/compliance/ncs';
    return client.get(url);
  },
  
  closeNC: (ncId, resolution) =>
    client.put(`/api/compliance/nc/${ncId}`, { status: 'closed', resolution }),
};

// ============================================================================
// SCHEDULE API
// ============================================================================
export const scheduleApi = {
  analyse: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_name', 'Hyperscale DC');
    return client.post('/api/schedule/analyse', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  
  compare: (currentFile, baselineFile) => {
    const formData = new FormData();
    formData.append('current', currentFile);
    formData.append('baseline', baselineFile);
    return client.post('/api/schedule/compare', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  
  getTrend: () => client.get('/api/schedule/trend'),
  
  getReport: (projectName = 'Hyperscale DC') =>
    client.get(`/api/schedule/report?project_name=${projectName}`),
};

// ============================================================================
// SUPPLY CHAIN API
// ============================================================================
export const supplyChainApi = {
  uploadCSV: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/supply-chain/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  
  addShipment: (shipmentData) =>
    client.post('/api/supply-chain/shipment', shipmentData),
  
  getMapData: () => client.get('/api/supply-chain/map'),
  
  getAlerts: () => client.get('/api/supply-chain/alerts'),
  
  getSummary: () => client.get('/api/supply-chain/summary'),
  
  getAlternatives: (equipmentName, currentSupplier) =>
    client.post('/api/supply-chain/alternatives', {
      equipment_name: equipmentName,
      current_supplier: currentSupplier,
    }),
};

// ============================================================================
// COMMISSIONING API
// ============================================================================
export const commissioningApi = {
  ingestStandards: (files, standardNames = null) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    if (standardNames) {
      formData.append('standard_names', standardNames);
    }
    return client.post('/api/commissioning/standards/ingest', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  
  generateProcedure: (system, testName, tier = 'Tier III') =>
    client.post('/api/commissioning/procedure/generate', {
      system,
      test_name: testName,
      tier,
    }),
  
  getLibrary: () => client.get('/api/commissioning/tests/library'),
  
  logResult: (result) =>
    client.post('/api/commissioning/results/log', result),
  
  downloadITP: (projectName, company, person = null) => {
    const params = new URLSearchParams({
      project_name: projectName,
      company,
      ...(person && { person }),
    });
    return client.get(`/api/commissioning/itp/download?${params}`, {
      responseType: 'blob',
    });
  },
  
  getDashboard: () => client.get('/api/commissioning/dashboard'),
};

// ============================================================================
// DASHBOARD API
// ============================================================================
export const dashboardApi = {
  getSummary: () => client.get('/api/dashboard/summary'),
};

export default client;
