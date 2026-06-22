-- EPC Intelligence Platform Database Schema
-- PostgreSQL schema for Supabase

-- Non-Conformances Table
CREATE TABLE IF NOT EXISTS non_conformances (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nc_id VARCHAR(50) NOT NULL UNIQUE,
  severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'major', 'minor', 'informational')),
  clause_ref VARCHAR(100) NOT NULL,
  description TEXT NOT NULL,
  submittal_file VARCHAR(255),
  spec_file VARCHAR(255),
  recommended_action TEXT,
  status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Schedule Risks Table
CREATE TABLE IF NOT EXISTS schedule_risks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_name VARCHAR(255) NOT NULL,
  risk_level VARCHAR(20) NOT NULL CHECK (risk_level IN ('high', 'medium', 'low')),
  risk_description TEXT NOT NULL,
  mitigation TEXT,
  snapshot_date DATE NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Shipments Table
CREATE TABLE IF NOT EXISTS shipments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  equipment_name VARCHAR(255) NOT NULL,
  supplier VARCHAR(255) NOT NULL,
  origin_country VARCHAR(100),
  current_location VARCHAR(255),
  eta DATE,
  required_on_site DATE,
  status VARCHAR(20) NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'in_transit', 'delayed', 'delivered', 'received')),
  lat DECIMAL(10, 8),
  lng DECIMAL(11, 8),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Commissioning Records Table
CREATE TABLE IF NOT EXISTS commissioning_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  test_id VARCHAR(50) NOT NULL UNIQUE,
  system VARCHAR(255) NOT NULL,
  test_name VARCHAR(255) NOT NULL,
  acceptance_criteria TEXT NOT NULL,
  result VARCHAR(20) NOT NULL CHECK (result IN ('pass', 'fail', 'conditional_pass', 'not_tested')),
  tested_by VARCHAR(255),
  test_date DATE NOT NULL,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RFI Log Table
CREATE TABLE IF NOT EXISTS rfi_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  question TEXT NOT NULL,
  answer TEXT,
  citations_json JSONB,
  resolved_by VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Document Metadata Table (for tracking ingested documents)
CREATE TABLE IF NOT EXISTS documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  file_name VARCHAR(255) NOT NULL,
  file_type VARCHAR(50),
  file_path VARCHAR(255),
  file_size INTEGER,
  document_type VARCHAR(50),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_non_conformances_severity ON non_conformances(severity);
CREATE INDEX idx_non_conformances_status ON non_conformances(status);
CREATE INDEX idx_schedule_risks_risk_level ON schedule_risks(risk_level);
CREATE INDEX idx_shipments_status ON shipments(status);
CREATE INDEX idx_shipments_eta ON shipments(eta);
CREATE INDEX idx_commissioning_records_system ON commissioning_records(system);
CREATE INDEX idx_commissioning_records_result ON commissioning_records(result);
CREATE INDEX idx_documents_file_type ON documents(file_type);
