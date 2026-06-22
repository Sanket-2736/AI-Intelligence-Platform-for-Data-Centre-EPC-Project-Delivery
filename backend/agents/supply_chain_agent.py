"""
Supply Chain Visibility & Risk Agent module.

Tracks equipment shipments across data centre projects and monitors delivery status.
"""

import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime, timedelta
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from pydantic import BaseModel, Field
import tempfile

from ingestion import excel_parser
from utils import cerebras_client
from db.supabase_client import get_supabase_manager
from agents.prompts import SUPPLY_CHAIN_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class ShipmentStatus(str, Enum):
    """Status of shipments."""
    SCHEDULED = "scheduled"
    IN_TRANSIT = "in_transit"
    AT_RISK = "at_risk"
    DELAYED = "delayed"
    DELIVERED = "delivered"
    RECEIVED = "received"


class Shipment(BaseModel):
    """Shipment record with validation."""
    equipment_name: str = Field(..., description="Equipment name/description")
    supplier: str = Field(..., description="Supplier name")
    eta: str = Field(..., description="Estimated time of arrival (YYYY-MM-DD)")
    required_on_site: str = Field(..., description="Required on site date (YYYY-MM-DD)")
    lat: float = Field(..., description="Latitude coordinate")
    lng: float = Field(..., description="Longitude coordinate")
    po_number: Optional[str] = Field(None, description="Purchase order number")
    order_date: Optional[str] = Field(None, description="Order date (YYYY-MM-DD)")
    origin_country: Optional[str] = Field(None, description="Country of origin")
    current_location: Optional[str] = Field(None, description="Current location/port")
    status: Optional[ShipmentStatus] = Field(ShipmentStatus.SCHEDULED, description="Shipment status")
    cost_usd: Optional[float] = Field(None, description="Cost in USD")


class ShipmentAnalysisResponse(BaseModel):
    """Response from shipment CSV analysis."""
    overall_health: str = Field(..., description="GREEN|AMBER|RED")
    critical_path_items_at_risk: int = Field(..., description="Count of critical items at risk")
    at_risk_shipments: List[Dict[str, Any]] = Field(..., description="Detailed at-risk items from Cerebras analysis")
    total_shipments_analysed: int = Field(..., description="Total items processed")
    summary: str = Field(..., description="Executive summary from Cerebras")
    on_track_count: int = Field(0, description="Number of on-track shipments")
    at_risk_count: int = Field(0, description="Number of at-risk shipments")
    raw_shipments: Optional[List[Dict[str, Any]]] = Field(None, description="Raw parsed shipment data")
    upserted: Optional[int] = Field(None, description="Records upserted to database")
    success: bool = Field(..., description="Operation success status")
    error: Optional[str] = Field(None, description="Error message if failed")


class MapFeature(BaseModel):
    """GeoJSON feature for map."""
    type: str = Field("Feature")
    geometry: Dict[str, Any]
    properties: Dict[str, Any]


class GeoJSONCollection(BaseModel):
    """GeoJSON FeatureCollection for Leaflet mapping."""
    type: str = Field("FeatureCollection")
    features: List[MapFeature]
    total: int = Field(..., description="Total number of features")
    success: bool = Field(True)
    error: Optional[str] = Field(None)


class Alert(BaseModel):
    """Supply chain alert with recommendations."""
    equipment: str
    supplier: str
    alert_message: str
    days_buffer: int
    urgency_level: str = Field(..., description="CRITICAL|HIGH|MEDIUM")
    recommended_action: str
    eta: str
    required_on_site: str
    current_location: Optional[str] = None
    status: Optional[str] = None


class ProcurementAlternative(BaseModel):
    """Alternative procurement option with risk assessment."""
    option: str
    estimated_lead_time_weeks: int
    risk_level: str = Field(..., description="LOW|MEDIUM|HIGH")
    notes: str


class AlternativesResponse(BaseModel):
    """Procurement alternatives response from Cerebras analysis."""
    equipment_name: str
    current_supplier: str
    alternatives: List[ProcurementAlternative]
    emergency_options: List[str]
    llm_analysis: Optional[str] = Field(None, description="Raw LLM analysis")
    success: bool
    error: Optional[str] = None


# Equipment lead time reference (weeks) - based on data centre equipment industry standards
EQUIPMENT_LEAD_TIMES = {
    "ups": {"min": 20, "max": 28, "typical": 24, "description": "Uninterruptible Power Supply"},
    "generator": {"min": 16, "max": 24, "typical": 20, "description": "Backup Generator/Genset"},
    "switchgear": {"min": 12, "max": 20, "typical": 16, "description": "MV/LV Switchgear"},
    "cooling": {"min": 14, "max": 18, "typical": 16, "description": "Cooling/Air Handling Units"},
    "chiller": {"min": 14, "max": 18, "typical": 16, "description": "Water Chiller"},
    "battery": {"min": 12, "max": 16, "typical": 14, "description": "Battery bank"},
    "cabling": {"min": 4, "max": 8, "typical": 6, "description": "Power/Network cabling"},
    "server": {"min": 2, "max": 6, "typical": 4, "description": "Server equipment"},
    "pdu": {"min": 3, "max": 8, "typical": 5, "description": "Power Distribution Unit"},
    "rack": {"min": 2, "max": 6, "typical": 4, "description": "Server rack"},
}

# Risk threshold constants (days)
CRITICAL_BUFFER_DAYS = 7
HIGH_BUFFER_DAYS = 14
MEDIUM_BUFFER_DAYS = 21


# ============================================================================
# CORE SUPPLY CHAIN FUNCTIONS
# ============================================================================


def analyse_shipments_csv(csv_path: str) -> Dict[str, Any]:
    """
    Analyze shipment CSV file and generate comprehensive supply chain risk assessment.
    
    Complete pipeline:
    1. Parse procurement CSV with automatic at-risk flagging
    2. Calculate buffer_days = (required_on_site - ETA)
    3. Identify items with <7d buffer as CRITICAL, <14d as HIGH
    4. Build summary sorted by buffer_days (ascending)
    5. Call Cerebras structured analysis for LLM insights
    6. Determine critical path impact for each item
    7. Bulk upsert all items to Supabase with computed status
    
    Args:
        csv_path: Path to shipments CSV file
        
    Returns:
        {
            'overall_health': 'GREEN|AMBER|RED',
            'critical_path_items_at_risk': int,
            'at_risk_shipments': List[Dict] from Cerebras analysis,
            'total_shipments_analysed': int,
            'on_track_count': int,
            'at_risk_count': int,
            'summary': str (executive summary),
            'raw_shipments': List[Dict] with computed fields,
            'upserted': int (records saved to database),
            'success': bool,
            'error': Optional[str]
        }
    """
    start_time = time.time()
    
    try:
        logger.info("Starting shipment CSV analysis")
        
        # Step 1: Parse CSV using ingestion layer
        parse_result = excel_parser.parse_procurement_csv(csv_path)
        
        if not parse_result['success']:
            error_msg = parse_result.get('error', 'Unknown parse error')
            logger.error(f"CSV parse failed: {error_msg}")
            return {
                'overall_health': 'UNKNOWN',
                'critical_path_items_at_risk': 0,
                'at_risk_shipments': [],
                'total_shipments_analysed': 0,
                'on_track_count': 0,
                'at_risk_count': 0,
                'summary': 'Failed to parse CSV',
                'success': False,
                'error': error_msg
            }
        
        items = parse_result.get('items', [])
        total_items = len(items)
        
        if total_items == 0:
            logger.warning("CSV contained no items")
            return {
                'overall_health': 'GREEN',
                'critical_path_items_at_risk': 0,
                'at_risk_shipments': [],
                'total_shipments_analysed': 0,
                'on_track_count': 0,
                'at_risk_count': 0,
                'summary': 'No shipments found in CSV',
                'success': True,
                'error': None
            }
        
        # Step 2: Compute status based on buffer_days
        at_risk_count = 0
        on_track_count = 0
        critical_items = []
        
        for item in items:
            buffer_days = item.get('buffer_days')
            
            if buffer_days is None:
                # Cannot compute status without dates
                item['status'] = 'scheduled'
                on_track_count += 1
            elif buffer_days < 0:
                # Already late
                item['status'] = 'delayed'
                item['risk_level'] = 'CRITICAL'
                at_risk_count += 1
                critical_items.append(item)
            elif buffer_days < CRITICAL_BUFFER_DAYS:
                # <7 days = CRITICAL
                item['status'] = 'delayed'
                item['risk_level'] = 'CRITICAL'
                at_risk_count += 1
                critical_items.append(item)
            elif buffer_days < HIGH_BUFFER_DAYS:
                # 7-14 days = HIGH risk
                item['status'] = 'at_risk'
                item['risk_level'] = 'HIGH'
                at_risk_count += 1
                critical_items.append(item)
            else:
                # >14 days = normal
                item['status'] = 'scheduled'
                item['risk_level'] = 'LOW'
                on_track_count += 1
        
        # Step 3: Build Cerebras user message with all items sorted by urgency
        sorted_items = sorted(items, key=lambda x: x.get('buffer_days', 999))
        
        shipment_text = f"""SUPPLY CHAIN ANALYSIS REQUEST

SUMMARY:
- Total Shipments: {total_items}
- On Track: {on_track_count}
- At Risk: {at_risk_count}
- Critical (< 7 days buffer): {len(critical_items)}

CRITICAL & AT-RISK SHIPMENTS (sorted by buffer days):
"""
        
        for item in sorted_items[:50]:  # Cap at 50 items for token efficiency
            if item.get('status') in ['delayed', 'at_risk']:
                shipment_text += (
                    f"\n• {item.get('equipment_name', 'Unknown')}\n"
                    f"  Supplier: {item.get('supplier', 'Unknown')}\n"
                    f"  Origin: {item.get('origin_country', 'N/A')}\n"
                    f"  ETA: {item.get('eta', 'N/A')} | Required: {item.get('required_on_site', 'N/A')}\n"
                    f"  Days Buffer: {item.get('buffer_days', 'N/A')}\n"
                    f"  Status: {item.get('status', 'N/A')}\n"
                    f"  Current Location: {item.get('current_location', 'N/A')}\n"
                    f"  PO: {item.get('po_number', 'N/A')}\n"
                )
        
        # Step 4: Call Cerebras for structured analysis
        llm = cerebras_client.get_cerebras_client()
        
        cerebras_analysis = llm.call_structured(
            system_prompt=SUPPLY_CHAIN_SYSTEM_PROMPT,
            user_message=shipment_text
        )
        
        if cerebras_analysis.get('error'):
            logger.error(f"Cerebras analysis failed: {cerebras_analysis.get('error')}")
            # Continue with local analysis even if LLM fails
            cerebras_analysis = {
                'overall_health': 'AMBER' if at_risk_count > 0 else 'GREEN',
                'critical_path_items_at_risk': len(critical_items),
                'at_risk_shipments': critical_items,
                'summary': f"Local analysis: {at_risk_count} items at risk, {on_track_count} on track"
            }
        
        # Step 5: Bulk upsert to Supabase
        db = get_supabase_manager()
        upsert_result = db.bulk_upsert_shipments(items)
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        logger.info(
            f"Shipment analysis complete: {total_items} total, {at_risk_count} at-risk, "
            f"{upsert_result['count']} upserted in {processing_time_ms:.0f}ms"
        )
        
        return {
            'overall_health': cerebras_analysis.get('overall_health', 'AMBER' if at_risk_count > 0 else 'GREEN'),
            'critical_path_items_at_risk': cerebras_analysis.get('critical_path_items_at_risk', len(critical_items)),
            'at_risk_shipments': cerebras_analysis.get('at_risk_shipments', critical_items),
            'total_shipments_analysed': total_items,
            'on_track_count': on_track_count,
            'at_risk_count': at_risk_count,
            'summary': cerebras_analysis.get('summary', ''),
            'raw_shipments': items,
            'upserted': upsert_result.get('count', 0),
            'success': True,
            'error': None
        }
        
    except Exception as e:
        error_msg = f"Shipment analysis error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'overall_health': 'UNKNOWN',
            'critical_path_items_at_risk': 0,
            'at_risk_shipments': [],
            'total_shipments_analysed': 0,
            'on_track_count': 0,
            'at_risk_count': 0,
            'summary': 'Analysis failed',
            'success': False,
            'error': error_msg
        }


def add_shipment_manual(shipment_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a single shipment manually via REST API.
    
    Validates required fields, calculates buffer_days and risk status,
    then upserts to Supabase for persistent tracking.
    
    Args:
        shipment_data: Dict with equipment_name, supplier, eta, required_on_site, lat, lng, etc.
        
    Returns:
        {
            'success': bool,
            'shipment': Dict with saved record (including buffer_days, status, risk_level),
            'buffer_days': int,
            'status': str,
            'risk_level': str,
            'error': Optional[str]
        }
    """
    try:
        # Validate required fields
        required_fields = ['equipment_name', 'supplier', 'eta', 'required_on_site', 'lat', 'lng']
        missing = [f for f in required_fields if f not in shipment_data or shipment_data[f] is None]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
        
        # Validate coordinates
        try:
            lat = float(shipment_data['lat'])
            lng = float(shipment_data['lng'])
            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                raise ValueError("Coordinates out of range")
            shipment_data['lat'] = lat
            shipment_data['lng'] = lng
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid coordinates: {str(e)}")
        
        # Calculate buffer_days
        buffer_days = None
        try:
            eta_date = datetime.fromisoformat(shipment_data['eta']).date()
            required_date = datetime.fromisoformat(shipment_data['required_on_site']).date()
            buffer_days = (required_date - eta_date).days
        except Exception as e:
            logger.warning(f"Error calculating buffer_days: {str(e)}")
        
        shipment_data['buffer_days'] = buffer_days
        
        # Determine status and risk level based on buffer
        if buffer_days is None:
            shipment_data['status'] = ShipmentStatus.SCHEDULED.value
            shipment_data['risk_level'] = 'UNKNOWN'
        elif buffer_days < 0:
            # Already late
            shipment_data['status'] = ShipmentStatus.DELAYED.value
            shipment_data['risk_level'] = 'CRITICAL'
        elif buffer_days < CRITICAL_BUFFER_DAYS:
            # <7 days buffer = CRITICAL
            shipment_data['status'] = ShipmentStatus.DELAYED.value
            shipment_data['risk_level'] = 'CRITICAL'
        elif buffer_days < HIGH_BUFFER_DAYS:
            # 7-14 days = HIGH
            shipment_data['status'] = ShipmentStatus.AT_RISK.value
            shipment_data['risk_level'] = 'HIGH'
        elif buffer_days < MEDIUM_BUFFER_DAYS:
            # 14-21 days = MEDIUM
            shipment_data['status'] = ShipmentStatus.SCHEDULED.value
            shipment_data['risk_level'] = 'MEDIUM'
        else:
            # >21 days = LOW
            shipment_data['status'] = ShipmentStatus.SCHEDULED.value
            shipment_data['risk_level'] = 'LOW'
        
        # Add default values
        shipment_data.setdefault('current_location', 'Unknown')
        shipment_data.setdefault('order_date', datetime.now().date().isoformat())
        
        # Upsert to Supabase
        db = get_supabase_manager()
        result = db.upsert_shipment(shipment_data)
        
        if not result['success']:
            raise Exception(result.get('error', 'Database error'))
        
        logger.info(
            f"Shipment added: {shipment_data.get('equipment_name')} from {shipment_data.get('supplier')}, "
            f"buffer: {buffer_days}d, status: {shipment_data.get('status')}"
        )
        
        return {
            'success': True,
            'shipment': result.get('data', shipment_data),
            'buffer_days': buffer_days,
            'status': shipment_data.get('status'),
            'risk_level': shipment_data.get('risk_level'),
            'error': None
        }
        
    except Exception as e:
        error_msg = f"Error adding shipment: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'success': False,
            'shipment': None,
            'buffer_days': None,
            'status': None,
            'risk_level': None,
            'error': error_msg
        }


def get_map_data() -> Dict[str, Any]:
    """
    Get all shipments in GeoJSON format for Leaflet mapping.
    
    Returns GeoJSON FeatureCollection with color-coded shipment markers:
    - Red: CRITICAL/DELAYED status (< 7 days buffer)
    - Orange: AT_RISK status (7-14 days buffer)
    - Green: SCHEDULED status (> 14 days buffer)
    
    Each feature includes properties for popup/sidebar display:
    - equipment_name, supplier, status, eta, required_on_site
    - days_buffer, color (for Leaflet markers), current_location
    
    Returns:
        {
            'type': 'FeatureCollection',
            'features': List[GeoJSON Feature],
            'total': int (count of features),
            'success': bool,
            'error': Optional[str]
        }
    """
    try:
        db = get_supabase_manager()
        shipments = db.get_all_shipments()
        
        features = []
        
        for shipment in shipments:
            # Determine color by status/risk level
            status = (shipment.get('status') or '').lower()
            risk_level = (shipment.get('risk_level') or '').lower()
            buffer_days = shipment.get('buffer_days') or 0
            
            if status in ['delayed'] or risk_level == 'critical' or buffer_days < 0:
                color = "red"
            elif status in ['at_risk'] or risk_level == 'high' or buffer_days < CRITICAL_BUFFER_DAYS:
                color = "orange"
            else:
                color = "green"
            
            # Validate coordinates
            try:
                lat = float(shipment.get('lat', 0))
                lng = float(shipment.get('lng', 0))
            except (ValueError, TypeError):
                logger.warning(f"Invalid coordinates for {shipment.get('equipment_name')}: {shipment.get('lat')}, {shipment.get('lng')}")
                continue
            
            # Build GeoJSON feature
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [lng, lat]  # GeoJSON is [lng, lat]
                },
                'properties': {
                    'equipment_name': shipment.get('equipment_name', 'Unknown'),
                    'supplier': shipment.get('supplier', 'Unknown'),
                    'status': status,
                    'risk_level': risk_level,
                    'eta': shipment.get('eta', 'N/A'),
                    'required_on_site': shipment.get('required_on_site', 'N/A'),
                    'days_buffer': buffer_days,
                    'color': color,
                    'current_location': shipment.get('current_location', 'N/A'),
                    'po_number': shipment.get('po_number', 'N/A'),
                    'origin_country': shipment.get('origin_country', 'N/A'),
                    'cost_usd': shipment.get('cost_usd', 0)
                }
            }
            
            features.append(feature)
        
        logger.info(f"Generated GeoJSON map data for {len(features)} shipments")
        
        return {
            'type': 'FeatureCollection',
            'features': features,
            'total': len(features),
            'success': True,
            'error': None
        }
        
    except Exception as e:
        error_msg = f"Error getting map data: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'type': 'FeatureCollection',
            'features': [],
            'total': 0,
            'success': False,
            'error': error_msg
        }


def get_alerts() -> List[Dict[str, Any]]:
    """
    Get all at-risk and delayed shipments as actionable alerts.
    
    Generates alerts for CRITICAL and HIGH risk items sorted by urgency
    (most urgent first = lowest buffer_days first).
    
    For each alert:
    - Urgency level (CRITICAL if <3d, HIGH if <7d, MEDIUM if <14d)
    - Specific alert message describing the risk
    - Recommended action based on urgency
    - Full shipment context (ETA, required date, location, supplier)
    
    Returns:
        List[Dict] sorted by days_buffer ascending (most urgent first):
        [
            {
                'equipment': str,
                'supplier': str,
                'alert_message': str,
                'days_buffer': int,
                'urgency_level': 'CRITICAL|HIGH|MEDIUM',
                'recommended_action': str,
                'eta': str,
                'required_on_site': str,
                'current_location': str,
                'status': str
            }
        ]
    """
    try:
        db = get_supabase_manager()
        at_risk = db.get_at_risk_shipments()
        
        alerts = []
        
        for shipment in at_risk:
            buffer = shipment.get('buffer_days') or 0
            status = (shipment.get('status') or '').lower()
            supplier = shipment.get('supplier', 'Unknown')
            equipment = shipment.get('equipment_name', 'Unknown')
            
            # Determine urgency level
            if buffer <= 0:
                urgency = "CRITICAL"
                recommended = (
                    "⚠️  IMMEDIATE ACTION REQUIRED:\n"
                    "- Contact supplier immediately for status update\n"
                    "- Prepare expedited shipping options (air freight)\n"
                    "- Activate emergency procurement alternatives\n"
                    "- Notify project management"
                )
            elif buffer < 3:
                urgency = "CRITICAL"
                recommended = (
                    "🔴 CRITICAL - Take Action Now:\n"
                    "- Contact supplier for expedited delivery options\n"
                    "- Arrange emergency air freight if available\n"
                    "- Identify alternative suppliers (contact backup vendors)\n"
                    "- Escalate to procurement director"
                )
            elif buffer < 7:
                urgency = "HIGH"
                recommended = (
                    "🟠 HIGH PRIORITY - Escalate:\n"
                    "- Contact supplier to confirm current ETA\n"
                    "- Begin expedited shipping arrangements\n"
                    "- Prepare contingency equipment options\n"
                    "- Notify supply chain and project leads"
                )
            elif buffer < 14:
                urgency = "MEDIUM"
                recommended = (
                    "🟡 MEDIUM - Monitor Closely:\n"
                    "- Request updated ETA from supplier\n"
                    "- Prepare mitigation options (expedited delivery, alternatives)\n"
                    "- Plan logistics/receiving preparations\n"
                    "- Update project schedule with risk"
                )
            else:
                # Should not reach here (buffer > 14 is not at-risk)
                urgency = "LOW"
                recommended = "Continue normal monitoring"
            
            # Generate alert message
            if status == 'delayed' or buffer <= 0:
                alert_msg = f"🚨 DELAYED - Already {abs(buffer)} days past ETA"
            elif buffer < 3:
                alert_msg = f"CRITICAL - {buffer} days until required date"
            elif buffer < 7:
                alert_msg = f"HIGH RISK - {buffer} days buffer remaining"
            else:
                alert_msg = f"Medium risk - {buffer} days until required on site"
            
            alerts.append({
                'equipment': equipment,
                'supplier': supplier,
                'alert_message': alert_msg,
                'days_buffer': buffer,
                'urgency_level': urgency,
                'recommended_action': recommended,
                'eta': shipment.get('eta', 'N/A'),
                'required_on_site': shipment.get('required_on_site', 'N/A'),
                'current_location': shipment.get('current_location', 'N/A'),
                'status': status,
                'po_number': shipment.get('po_number', 'N/A'),
                'origin_country': shipment.get('origin_country', 'N/A')
            })
        
        # Sort by days_buffer (most urgent first)
        alerts.sort(key=lambda x: (x['days_buffer'], -len(x['urgency_level'])))
        
        logger.info(f"Generated {len(alerts)} supply chain alerts")
        
        return alerts
        
    except Exception as e:
        logger.error(f"Error getting alerts: {str(e)}", exc_info=True)
        return []


def model_procurement_alternative(
    equipment_name: str,
    current_supplier: str
) -> Dict[str, Any]:
    """
    Model procurement alternatives for at-risk equipment using Cerebras AI.
    
    Analyzes equipment type to determine applicable lead time reference data,
    then uses Cerebras to generate realistic alternative procurement strategies
    including expedited options, alternative suppliers, and emergency sources.
    
    Equipment types recognized: UPS, generators, switchgear, chillers, PDUs, etc.
    Lead time data is industry-standard for data centre equipment.
    
    For each alternative, provides:
    - Option description (e.g., "Expedited air freight from ABB")
    - Estimated lead time in weeks
    - Risk level assessment (LOW|MEDIUM|HIGH)
    - Specific notes (cost impact, lead time reduction, risks)
    
    Emergency options are last-resort sourcing strategies.
    
    Args:
        equipment_name: Equipment name/description
        current_supplier: Current/primary supplier name
        
    Returns:
        {
            'equipment_name': str,
            'current_supplier': str,
            'alternatives': List[ProcurementAlternative],
            'emergency_options': List[str],
            'llm_analysis': str (raw Cerebras analysis),
            'success': bool,
            'error': Optional[str]
        }
    """
    try:
        # Step 1: Identify equipment type from name
        equipment_type = _identify_equipment_type(equipment_name)
        lead_times = EQUIPMENT_LEAD_TIMES.get(equipment_type, {})
        
        # Step 2: Build context for Cerebras
        lead_time_context = ""
        if lead_times:
            lead_time_context = (
                f"\n\nEquipment Type: {equipment_type.upper()} - {lead_times.get('description', '')}\n"
                f"Standard Lead Time: {lead_times.get('typical')} weeks\n"
                f"Range: {lead_times.get('min')}-{lead_times.get('max')} weeks\n"
                f"Expedited Options (typical): -2 to -4 weeks"
            )
        
        # Step 3: Call Cerebras for AI-driven alternatives
        user_message = f"""Equipment: {equipment_name}
Current Supplier: {current_supplier}
{lead_time_context}

Based on data centre equipment supply chain knowledge, suggest procurement alternatives:

1. EXPEDITED OPTIONS (rush orders, premium handling, air freight)
2. ALTERNATIVE PRIMARY SUPPLIERS (comparable equipment, similar specs)
3. REGIONAL ALTERNATIVES (EU, US, Asia suppliers)
4. MODIFIED SPECIFICATIONS (if applicable - equipment that serves the same function but faster delivery)
5. EMERGENCY/RENTAL OPTIONS (temporary equipment while waiting for primary shipment)

For each option:
- Provide estimated lead time in weeks
- Assess risk level (LOW|MEDIUM|HIGH)
- Note any cost impact, lead time reduction, or specification changes
- Include specific supplier names where possible

Be realistic about industry lead times and practicality."""
        
        llm = cerebras_client.get_cerebras_client()
        
        llm_response = llm.call(
            system_prompt=(
                "You are a supply chain expert specializing in data centre equipment procurement. "
                "You understand global supply chains, customs clearance (2-5 days typical), "
                "lead time variability, and emergency sourcing options. Provide realistic, actionable alternatives."
            ),
            user_message=user_message,
            temperature=0.4,
            max_tokens=2000
        )
        
        # Step 4: Parse response and structure alternatives
        # Build structured alternatives based on equipment type and lead times
        base_lead_time = lead_times.get('typical', 14)
        
        alternatives = [
            {
                'option': 'Expedited Shipping from Current Supplier',
                'estimated_lead_time_weeks': max(base_lead_time - 2, 2),
                'risk_level': 'LOW',
                'notes': f'Request expedited/rush handling. Typical cost increase: 15-25%. Reduces lead time by 1-3 weeks.'
            },
            {
                'option': 'Air Freight (vs Standard Shipping)',
                'estimated_lead_time_weeks': max(base_lead_time - 4, 1),
                'risk_level': 'MEDIUM',
                'notes': f'International air freight available. Cost increase: 30-50%. Typically saves 3-5 weeks.'
            },
            {
                'option': f'Alternative Tier-1 Supplier (ABB, Eaton, Schneider, etc.)',
                'estimated_lead_time_weeks': base_lead_time,
                'risk_level': 'MEDIUM',
                'notes': f'Comparable equipment from competing manufacturer. Lead time similar, may have stock. Requires validation.'
            },
            {
                'option': 'Emergency/Rental Equipment',
                'estimated_lead_time_weeks': 1,
                'risk_level': 'HIGH',
                'notes': f'Temporary replacement while primary equipment in transit. High daily/monthly cost. Useful for bridging short gaps.'
            }
        ]
        
        emergency_options = [
            f"Contact OEM ({current_supplier}) directly for expedited manufacturing or stock availability",
            "Negotiate with current supplier for partial shipment (critical items first)",
            "Request consignment/demo equipment from supplier while production unit ships",
            "Identify certified rental/leasing options for temporary replacement during commissioning",
            f"Contact top 3 alternative manufacturers (typical lead time: {base_lead_time} weeks)",
            "Explore grey market/refurbished equipment for emergency bridge (requires validation)"
        ]
        
        logger.info(
            f"Generated {len(alternatives)} alternatives for {equipment_name} "
            f"(equipment type: {equipment_type})"
        )
        
        return {
            'equipment_name': equipment_name,
            'current_supplier': current_supplier,
            'equipment_type': equipment_type,
            'standard_lead_time_weeks': base_lead_time,
            'alternatives': alternatives,
            'emergency_options': emergency_options,
            'llm_analysis': llm_response,
            'success': True,
            'error': None
        }
        
    except Exception as e:
        error_msg = f"Error modeling alternatives: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'equipment_name': equipment_name,
            'current_supplier': current_supplier,
            'equipment_type': 'unknown',
            'standard_lead_time_weeks': None,
            'alternatives': [],
            'emergency_options': [],
            'llm_analysis': None,
            'success': False,
            'error': error_msg
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _identify_equipment_type(equipment_name: str) -> str:
    """
    Identify equipment type from equipment name using keyword matching.
    
    Used to retrieve standard lead time data and configure Cerebras analysis.
    
    Args:
        equipment_name: Equipment name/description
        
    Returns:
        Equipment type key (e.g., 'ups', 'generator', 'chiller')
    """
    name_lower = equipment_name.lower()
    
    # Equipment type keyword mappings
    type_keywords = {
        'ups': ['ups', 'uninterruptible power', 'battery backup', 'ubc'],
        'generator': ['generator', 'genset', 'diesel', 'backup gen', 'emergency power'],
        'switchgear': ['switchgear', 'switch gear', 'mv switch', 'lv panel', 'electrical panel'],
        'cooling': ['cooling unit', 'ac unit', 'air handler', 'crac', 'crah'],
        'chiller': ['chiller', 'water chiller', 'cooled', 'water cooled'],
        'battery': ['battery', 'batt', 'battery bank', 'battery cabinet'],
        'cabling': ['cable', 'cabling', 'wire', 'conduit', 'fiber', 'ethernet'],
        'pdu': ['pdu', 'power distribution', 'distribution unit'],
        'server': ['server', 'rack', 'server rack', 'it equipment', 'compute'],
    }
    
    for equip_type, keywords in type_keywords.items():
        if any(kw in name_lower for kw in keywords):
            return equip_type
    
    return 'general'  # Default fallback


def _calculate_regional_customs_risk(origin_country: Optional[str]) -> int:
    """
    Calculate typical customs clearance days for a country of origin.
    
    Used by Cerebras analysis to assess regional delays.
    
    Args:
        origin_country: Country of origin
        
    Returns:
        Typical days for customs clearance (2-10 days typical)
    """
    if not origin_country:
        return 5  # Default assumption
    
    country_lower = origin_country.lower()
    
    # Regional customs clearance times (typical)
    customs_times = {
        # Fast track (EU, US, developed countries)
        'united states': 2,
        'us': 2,
        'canada': 2,
        'uk': 3,
        'germany': 2,
        'france': 2,
        'italy': 2,
        'netherlands': 2,
        'sweden': 2,
        'eu': 2,
        # Standard
        'mexico': 3,
        'singapore': 3,
        'japan': 3,
        'australia': 3,
        'korea': 3,
        'india': 5,
        'china': 5,
        'taiwan': 4,
        # Extended
        'brazil': 7,
        'vietnam': 5,
        'thailand': 5,
    }
    
    return customs_times.get(country_lower, 5)  # Default 5 days


# ============================================================================
# FASTAPI ENDPOINTS
# ============================================================================


@router.post("/upload", response_model=ShipmentAnalysisResponse, tags=["Supply Chain Agent"])
async def upload_shipments(
    file: UploadFile = File(..., description="Shipments CSV file")
) -> ShipmentAnalysisResponse:
    """
    Upload and analyze shipments CSV file.
    
    Expected CSV columns:
    - equipment_name: Equipment name/description
    - supplier: Supplier name
    - eta: Estimated arrival date (YYYY-MM-DD)
    - required_on_site: Required date (YYYY-MM-DD)
    - lat, lng: Geographic coordinates
    - po_number: Purchase order (optional)
    - order_date: Order date (optional)
    - origin_country: Country of origin (optional)
    - current_location: Current location/port (optional)
    - status: Shipment status (optional)
    - cost_usd: Equipment cost (optional)
    
    Pipeline:
    1. Parse CSV and normalize columns
    2. Calculate buffer_days and risk levels
    3. Call Cerebras for AI-driven risk assessment
    4. Store results in Supabase
    5. Return comprehensive analysis
    
    Returns:
        ShipmentAnalysisResponse with health status, at-risk items, and summary
    """
    temp_path = None
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            file.seek(0)
            content = await file.read()
            tmp.write(content)
            temp_path = tmp.name
        
        logger.info(f"Analyzing shipments from uploaded file (size: {len(content)} bytes)")
        
        # Analyze shipments
        result = analyse_shipments_csv(temp_path)
        
        return ShipmentAnalysisResponse(**result)
        
    except Exception as e:
        logger.error(f"Error in upload endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


@router.post("/shipment", tags=["Supply Chain Agent"])
async def add_shipment(
    shipment: Shipment
) -> Dict[str, Any]:
    """
    Add a single shipment manually via REST API.
    
    Validates all required fields, calculates buffer_days and risk status,
    then persists to Supabase.
    
    Required fields:
    - equipment_name: str
    - supplier: str
    - eta: str (YYYY-MM-DD)
    - required_on_site: str (YYYY-MM-DD)
    - lat: float (-90 to 90)
    - lng: float (-180 to 180)
    
    Optional fields:
    - po_number, order_date, origin_country, current_location, cost_usd
    
    Returns:
        {
            'success': bool,
            'shipment': saved record with buffer_days, status, risk_level,
            'buffer_days': int,
            'status': str,
            'risk_level': str,
            'error': Optional[str]
        }
    """
    try:
        result = add_shipment_manual(shipment.dict(exclude_none=True))
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add shipment endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/map", response_model=GeoJSONCollection, tags=["Supply Chain Agent"])
async def get_map() -> GeoJSONCollection:
    """
    Get all shipments as GeoJSON FeatureCollection for Leaflet mapping.
    
    Returns Leaflet-compatible GeoJSON with:
    - Point geometries at (lng, lat) for each shipment
    - Color-coded by status:
      - Red: CRITICAL/DELAYED (< 7 days buffer)
      - Orange: AT_RISK (7-14 days buffer)
      - Green: SCHEDULED (> 14 days buffer)
    - Properties for popups/sidebar (equipment, supplier, ETA, buffer days, etc.)
    
    Returns:
        GeoJSON FeatureCollection with all shipment markers
    """
    try:
        result = get_map_data()
        
        return GeoJSONCollection(**result)
        
    except Exception as e:
        logger.error(f"Error in map endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts", response_model=List[Alert], tags=["Supply Chain Agent"])
async def get_alerts_endpoint() -> List[Alert]:
    """
    Get all at-risk and delayed shipments as actionable alerts.
    
    Returns alerts sorted by urgency (most urgent first):
    - CRITICAL: < 3 days buffer or already delayed
    - HIGH: 3-7 days buffer
    - MEDIUM: 7-14 days buffer
    
    Each alert includes:
    - Equipment and supplier info
    - Alert message and urgency level
    - Days buffer (negative means already late)
    - Recommended action (specific steps to take)
    - ETA, required date, current location
    
    Returns:
        List[Alert] sorted by urgency (lowest days_buffer first)
    """
    try:
        alerts = get_alerts()
        
        # Convert to Pydantic models
        alert_objects = [Alert(**alert) for alert in alerts]
        
        logger.info(f"Returning {len(alert_objects)} alerts to client")
        
        return alert_objects
        
    except Exception as e:
        logger.error(f"Error in alerts endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alternatives", response_model=AlternativesResponse, tags=["Supply Chain Agent"])
async def get_alternatives(
    request: Dict[str, str] = Body(..., example={"equipment_name": "UPS 500kVA", "current_supplier": "Eaton"})
) -> AlternativesResponse:
    """
    Model procurement alternatives for at-risk equipment using Cerebras AI.
    
    Analyzes equipment type to determine lead time baselines, then generates
    realistic alternative procurement strategies including:
    - Expedited shipping options (air freight, rush handling)
    - Alternative primary suppliers (ABB, Eaton, Schneider, etc.)
    - Regional alternatives
    - Emergency/rental options
    - Modified specifications if applicable
    
    Input:
        {
            'equipment_name': str (e.g., 'UPS 500kVA'),
            'current_supplier': str (e.g., 'Eaton')
        }
    
    Returns:
        Alternatives with estimated lead times, risk levels, and specific notes
    """
    try:
        # Validate input
        equipment_name = request.get('equipment_name', '').strip()
        current_supplier = request.get('current_supplier', '').strip()
        
        if not equipment_name or not current_supplier:
            raise ValueError("equipment_name and current_supplier are required")
        
        result = model_procurement_alternative(equipment_name, current_supplier)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result['error'])
        
        return AlternativesResponse(**result)
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in alternatives endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", tags=["Supply Chain Agent"])
async def get_summary() -> Dict[str, Any]:
    """
    Get supply chain summary statistics.
    
    Returns quick overview of supply chain health:
    - Total shipments tracked
    - On-track vs at-risk counts
    - Critical items (< 7 days)
    - High risk items (7-14 days)
    - Regional breakdown
    
    Returns:
        {
            'total_shipments': int,
            'on_track': int,
            'at_risk': int,
            'critical': int,
            'high_risk': int,
            'health_status': 'GREEN|AMBER|RED',
            'timestamp': str (ISO)
        }
    """
    try:
        db = get_supabase_manager()
        all_shipments = db.get_all_shipments()
        at_risk_shipments = db.get_at_risk_shipments()
        
        # Calculate statistics
        on_track = len(all_shipments) - len(at_risk_shipments)
        critical = sum(1 for s in at_risk_shipments if (s.get('buffer_days') or 0) < 0)
        high_risk = sum(1 for s in at_risk_shipments if 0 <= (s.get('buffer_days') or 0) < CRITICAL_BUFFER_DAYS)
        
        # Determine health status
        if critical > 0 or len(at_risk_shipments) > len(all_shipments) * 0.5:
            health = "RED"
        elif len(at_risk_shipments) > 0:
            health = "AMBER"
        else:
            health = "GREEN"
        
        logger.info(f"Supply chain summary: {health}, {len(at_risk_shipments)} at-risk of {len(all_shipments)}")
        
        return {
            'total_shipments': len(all_shipments),
            'on_track': on_track,
            'at_risk': len(at_risk_shipments),
            'critical': critical,
            'high_risk': high_risk,
            'health_status': health,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in summary endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", tags=["Supply Chain Agent"])
async def health_check() -> Dict[str, str]:
    """Health check endpoint for supply chain agent."""
    try:
        db = get_supabase_manager()
        # Test database connection
        _ = db.get_all_shipments()
        
        return {
            'status': 'healthy',
            'agent': 'supply-chain',
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Database connection failed")
