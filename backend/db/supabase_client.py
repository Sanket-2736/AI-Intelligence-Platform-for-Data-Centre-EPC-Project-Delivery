"""
Supabase Client module.
Manages PostgreSQL database connections and operations via Supabase.
Handles CRUD operations for all EPC Intelligence Platform tables.
Singleton pattern ensures only one client instance across application.
"""

from supabase import create_client, Client
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import config

logger = logging.getLogger(__name__)

# Status constants
STATUS_OPEN = "open"
STATUS_CLOSED = "closed"
STATUS_DEFERRED = "deferred"
STATUS_IN_PROGRESS = "in_progress"

# Severity constants
SEVERITY_CRITICAL = "critical"
SEVERITY_MAJOR = "major"
SEVERITY_MINOR = "minor"
SEVERITY_OBSERVATION = "informational"

# Risk levels
RISK_HIGH = "high"
RISK_MEDIUM = "medium"
RISK_LOW = "low"

# Test results
TEST_PASS = "pass"
TEST_FAIL = "fail"
TEST_CONDITIONAL = "conditional_pass"
TEST_NOT_TESTED = "not_tested"


class SupabaseManager:
    """
    Singleton manager for Supabase PostgreSQL database.
    Handles all CRUD operations for platform tables.
    Uses service role key for write operations to bypass RLS policies.
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern - ensure only one instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize Supabase clients (read and write)."""
        if self._initialized:
            return
        
        try:
            # Anon key for general operations (respects RLS)
            self.client: Client = create_client(
                config.SUPABASE_URL,
                config.SUPABASE_ANON_KEY
            )
            
            # Service role key for backend writes (bypasses RLS)
            self.admin_client: Client = create_client(
                config.SUPABASE_URL,
                config.SUPABASE_SERVICE_ROLE_KEY
            )
            
            logger.info("Supabase clients initialized (anon + service role)")
            
            # Test connection
            if self.test_connection():
                logger.info("Supabase connection verified")
            else:
                logger.warning("Supabase connection test failed")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize Supabase: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """
        Test database connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Simple count query to test connection
            result = self.client.table('non_conformances').select('count', count='exact').limit(1).execute()
            logger.info("Connection test successful")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False
    
    # ============================================================================
    # NON-CONFORMANCES CRUD
    # ============================================================================
    
    def insert_non_conformance(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert a new non-conformance record.
        Uses service role key to bypass RLS policies.
        
        Args:
            data: Dict with nc_id, severity, clause_ref, description, etc.
            
        Returns:
            {
                'success': bool,
                'data': dict or None,
                'error': str or None
            }
        """
        try:
            # Ensure defaults
            data.setdefault('status', STATUS_OPEN)
            data.setdefault('created_at', datetime.utcnow().isoformat())
            data.setdefault('updated_at', datetime.utcnow().isoformat())
            
            result = self.admin_client.table('non_conformances').insert(data).execute()
            
            logger.info(f"Non-conformance inserted: {data.get('nc_id')}")
            
            return {
                'success': True,
                'data': result.data[0] if result.data else data,
                'error': None
            }
            
        except Exception as e:
            error_msg = f"Error inserting non-conformance: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'data': None,
                'error': error_msg
            }
    
    def get_all_non_conformances(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all non-conformances, optionally filtered by status.
        
        Args:
            status: Optional status filter (open, closed, deferred, in_progress)
            
        Returns:
            List of non-conformance records, empty list on error
        """
        try:
            query = self.client.table('non_conformances').select('*')
            
            if status:
                query = query.eq('status', status)
            
            result = query.execute()
            
            logger.info(f"Retrieved {len(result.data)} non-conformances" + 
                       (f" with status {status}" if status else ""))
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Error retrieving non-conformances: {str(e)}")
            return []
    
    def update_nc_status(
        self,
        nc_id: str,
        status: str,
        resolution: str = ""
    ) -> Dict[str, Any]:
        """
        Update non-conformance status and resolution.
        Uses service role key to bypass RLS policies.
        
        Args:
            nc_id: Non-conformance ID
            status: New status (open, closed, deferred, in_progress)
            resolution: Resolution notes
            
        Returns:
            {
                'success': bool,
                'data': dict or None,
                'error': str or None
            }
        """
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if resolution:
                update_data['recommended_action'] = resolution
            
            result = self.admin_client.table('non_conformances').update(
                update_data
            ).eq('nc_id', nc_id).execute()
            
            logger.info(f"Non-conformance {nc_id} status updated to {status}")
            
            return {
                'success': True,
                'data': result.data[0] if result.data else None,
                'error': None
            }
            
        except Exception as e:
            error_msg = f"Error updating non-conformance status: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'data': None,
                'error': error_msg
            }
    
    def get_nc_summary_stats(self) -> Dict[str, Any]:
        """
        Get non-conformance summary statistics by severity.
        
        Returns:
            {
                'total': int,
                'critical': int,
                'major': int,
                'minor': int,
                'observation': int,
                'by_status': {status: count}
            }
        """
        try:
            result = self.client.table('non_conformances').select('severity, status').execute()
            
            stats = {
                'total': len(result.data),
                'critical': 0,
                'major': 0,
                'minor': 0,
                'observation': 0,
                'by_status': {}
            }
            
            for record in result.data:
                severity = record.get('severity', '').lower()
                status = record.get('status', '')
                
                # Count by severity
                if severity == 'critical':
                    stats['critical'] += 1
                elif severity == 'major':
                    stats['major'] += 1
                elif severity == 'minor':
                    stats['minor'] += 1
                else:
                    stats['observation'] += 1
                
                # Count by status
                if status not in stats['by_status']:
                    stats['by_status'][status] = 0
                stats['by_status'][status] += 1
            
            logger.info(f"Non-conformance stats: {stats['critical']} critical, "
                       f"{stats['major']} major, {stats['minor']} minor")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting NC summary stats: {str(e)}")
            return {'total': 0, 'critical': 0, 'major': 0, 'minor': 0, 'observation': 0, 'by_status': {}}
    
    # ============================================================================
    # SCHEDULE RISKS CRUD
    # ============================================================================
    
    def insert_schedule_risk(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert a schedule risk record.
        Uses service role key to bypass RLS policies.
        
        Args:
            data: Dict with task_name, risk_level, risk_description, etc.
            
        Returns:
            {
                'success': bool,
                'data': dict or None,
                'error': str or None
            }
        """
        try:
            data.setdefault('snapshot_date', datetime.now().date().isoformat())
            data.setdefault('created_at', datetime.utcnow().isoformat())
            
            result = self.admin_client.table('schedule_risks').insert(data).execute()
            
            logger.info(f"Schedule risk inserted: {data.get('task_name')}")
            
            return {
                'success': True,
                'data': result.data[0] if result.data else data,
                'error': None
            }
            
        except Exception as e:
            error_msg = f"Error inserting schedule risk: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'data': None,
                'error': error_msg
            }
    
    def get_latest_risks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get latest schedule risks.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of risk records, empty list on error
        """
        try:
            result = self.client.table('schedule_risks').select('*') \
                .order('created_at', desc=True) \
                .limit(limit) \
                .execute()
            
            logger.info(f"Retrieved {len(result.data)} latest risks")
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Error retrieving latest risks: {str(e)}")
            return []
    
    def get_risk_trend(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get risk trend over specified days (grouped by date and risk level).
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of daily risk summaries, empty list on error
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).date().isoformat()
            
            result = self.client.table('schedule_risks').select(
                'snapshot_date, risk_level'
            ).gte('snapshot_date', cutoff_date).execute()
            
            # Group by date and risk level
            trend = {}
            for record in result.data:
                date = record.get('snapshot_date')
                risk = record.get('risk_level', 'unknown')
                
                if date not in trend:
                    trend[date] = {RISK_HIGH: 0, RISK_MEDIUM: 0, RISK_LOW: 0}
                
                if risk in trend[date]:
                    trend[date][risk] += 1
            
            # Convert to list format
            trend_list = [
                {'date': date, **counts}
                for date, counts in sorted(trend.items())
            ]
            
            logger.info(f"Retrieved risk trend for {len(trend_list)} days")
            
            return trend_list
            
        except Exception as e:
            logger.error(f"Error retrieving risk trend: {str(e)}")
            return []
    
    # ============================================================================
    # SHIPMENTS CRUD
    # ============================================================================
    
    def upsert_shipment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upsert a shipment record (insert or update if exists).
        Uses service role key to bypass RLS policies.
        
        Args:
            data: Dict with equipment_name, supplier, status, eta, etc.
            
        Returns:
            {
                'success': bool,
                'data': dict or None,
                'error': str or None
            }
        """
        try:
            data.setdefault('created_at', datetime.utcnow().isoformat())
            data.setdefault('updated_at', datetime.utcnow().isoformat())
            
            result = self.admin_client.table('shipments').upsert(
                data,
                on_conflict='equipment_name'
            ).execute()
            
            logger.info(f"Shipment upserted: {data.get('equipment_name')}")
            
            return {
                'success': True,
                'data': result.data[0] if result.data else data,
                'error': None
            }
            
        except Exception as e:
            error_msg = f"Error upserting shipment: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'data': None,
                'error': error_msg
            }
    
    def get_all_shipments(self) -> List[Dict[str, Any]]:
        """
        Get all shipments.
        
        Returns:
            List of shipment records, empty list on error
        """
        try:
            result = self.client.table('shipments').select('*').execute()
            
            logger.info(f"Retrieved {len(result.data)} shipments")
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Error retrieving shipments: {str(e)}")
            return []
    
    def get_at_risk_shipments(self) -> List[Dict[str, Any]]:
        """
        Get shipments that are at risk or delayed.
        
        Returns:
            List of at-risk shipment records, empty list on error
        """
        try:
            result = self.client.table('shipments').select('*').in_(
                'status',
                ['delayed', 'at_risk']
            ).execute()
            
            logger.info(f"Retrieved {len(result.data)} at-risk shipments")
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Error retrieving at-risk shipments: {str(e)}")
            return []
    
    def bulk_upsert_shipments(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bulk upsert multiple shipment records.
        Uses service role key to bypass RLS policies.
        
        Args:
            items: List of shipment dicts
            
        Returns:
            {
                'success': bool,
                'count': int (number upserted),
                'error': str or None
            }
        """
        try:
            if not items:
                return {'success': True, 'count': 0, 'error': None}
            
            # Add timestamps
            for item in items:
                item.setdefault('created_at', datetime.utcnow().isoformat())
                item.setdefault('updated_at', datetime.utcnow().isoformat())
            
            result = self.admin_client.table('shipments').upsert(
                items,
                on_conflict='equipment_name'
            ).execute()
            
            count = len(result.data) if result.data else len(items)
            logger.info(f"Bulk upserted {count} shipments")
            
            return {'success': True, 'count': count, 'error': None}
            
        except Exception as e:
            error_msg = f"Error bulk upserting shipments: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'count': 0, 'error': error_msg}
    
    # ============================================================================
    # COMMISSIONING RECORDS CRUD
    # ============================================================================
    
    def insert_commissioning_record(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert a commissioning test record.
        Uses service role key to bypass RLS policies.
        
        Args:
            data: Dict with test_id, system, test_name, result, etc.
            
        Returns:
            {
                'success': bool,
                'data': dict or None,
                'error': str or None
            }
        """
        try:
            data.setdefault('created_at', datetime.utcnow().isoformat())
            
            result = self.admin_client.table('commissioning_records').insert(data).execute()
            
            logger.info(f"Commissioning record inserted: {data.get('test_id')}")
            
            return {
                'success': True,
                'data': result.data[0] if result.data else data,
                'error': None
            }
            
        except Exception as e:
            error_msg = f"Error inserting commissioning record: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'data': None,
                'error': error_msg
            }
    
    def get_records_by_system(self, system: str) -> List[Dict[str, Any]]:
        """
        Get commissioning records for a specific system.
        
        Args:
            system: System name
            
        Returns:
            List of commissioning records, empty list on error
        """
        try:
            result = self.client.table('commissioning_records').select('*').eq(
                'system',
                system
            ).execute()
            
            logger.info(f"Retrieved {len(result.data)} commissioning records for {system}")
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Error retrieving commissioning records: {str(e)}")
            return []
    
    def get_commissioning_summary(self) -> Dict[str, Any]:
        """
        Get commissioning summary statistics.
        
        Returns:
            {
                'total': int,
                'pass_count': int,
                'fail_count': int,
                'pending_count': int,
                'pass_rate': float (0-100),
                'by_system': {system: {pass: int, fail: int, pending: int}}
            }
        """
        try:
            result = self.client.table('commissioning_records').select('result, system').execute()
            
            summary = {
                'total': len(result.data),
                'pass_count': 0,
                'fail_count': 0,
                'pending_count': 0,
                'pass_rate': 0.0,
                'by_system': {}
            }
            
            for record in result.data:
                result_status = record.get('result', '').lower()
                system = record.get('system', 'unknown')
                
                # Count overall
                if result_status == TEST_PASS:
                    summary['pass_count'] += 1
                elif result_status == TEST_FAIL:
                    summary['fail_count'] += 1
                else:
                    summary['pending_count'] += 1
                
                # Count by system
                if system not in summary['by_system']:
                    summary['by_system'][system] = {
                        'pass': 0,
                        'fail': 0,
                        'pending': 0
                    }
                
                if result_status == TEST_PASS:
                    summary['by_system'][system]['pass'] += 1
                elif result_status == TEST_FAIL:
                    summary['by_system'][system]['fail'] += 1
                else:
                    summary['by_system'][system]['pending'] += 1
            
            # Calculate pass rate
            if summary['total'] > 0:
                summary['pass_rate'] = (summary['pass_count'] / summary['total']) * 100
            
            logger.info(f"Commissioning summary: {summary['pass_count']} pass, "
                       f"{summary['fail_count']} fail, {summary['pass_rate']:.1f}% pass rate")
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting commissioning summary: {str(e)}")
            return {
                'total': 0,
                'pass_count': 0,
                'fail_count': 0,
                'pending_count': 0,
                'pass_rate': 0.0,
                'by_system': {}
            }
    
    def get_all_records_for_itp(self) -> List[Dict[str, Any]]:
        """
        Get all commissioning records for ITP (Inspection and Test Plan) export.
        
        Returns:
            List of all commissioning records, empty list on error
        """
        try:
            result = self.client.table('commissioning_records').select('*').order(
                'system'
            ).execute()
            
            logger.info(f"Retrieved {len(result.data)} commissioning records for ITP")
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Error retrieving ITP records: {str(e)}")
            return []
    
    # ============================================================================
    # RFI LOG CRUD
    # ============================================================================
    
    def log_rfi(
        self,
        question: str,
        answer: str,
        citations: List[str]
    ) -> Dict[str, Any]:
        """
        Log an RFI question and answer to the database.
        Uses service role key to bypass RLS policies.
        
        Args:
            question: RFI question
            answer: RFI answer
            citations: List of document citations
            
        Returns:
            {
                'success': bool,
                'data': dict or None,
                'error': str or None
            }
        """
        try:
            import json
            
            data = {
                'question': question,
                'answer': answer,
                'citations_json': json.dumps(citations) if citations else '[]',
                'created_at': datetime.utcnow().isoformat()
            }
            
            result = self.admin_client.table('rfi_log').insert(data).execute()
            
            logger.info(f"RFI logged successfully")
            
            return {
                'success': True,
                'data': result.data[0] if result.data else data,
                'error': None
            }
            
        except Exception as e:
            error_msg = f"Error logging RFI: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'data': None,
                'error': error_msg
            }
    
    def get_recent_rfis(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent RFI logs.
        
        Args:
            limit: Maximum number of RFIs to return
            
        Returns:
            List of RFI records, empty list on error
        """
        try:
            result = self.client.table('rfi_log').select('*').order(
                'created_at',
                desc=True
            ).limit(limit).execute()
            
            logger.info(f"Retrieved {len(result.data)} recent RFIs")
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Error retrieving recent RFIs: {str(e)}")
            return []
    
    # ============================================================================
    # DASHBOARD HELPERS
    # ============================================================================
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """
        Get combined dashboard summary from all tables.
        
        Returns:
            {
                'total_ncs': int,
                'open_critical_ncs': int,
                'at_risk_shipments': int,
                'schedule_red_flags': int,
                'commissioning_pass_rate': float,
                'recent_rfis_count': int,
                'timestamp': str
            }
        """
        try:
            # Non-conformances
            nc_stats = self.get_nc_summary_stats()
            open_critical = sum(
                1 for record in self.get_all_non_conformances(STATUS_OPEN)
                if record.get('severity', '').lower() == SEVERITY_CRITICAL
            )
            
            # Shipments
            at_risk_shipments = len(self.get_at_risk_shipments())
            
            # Schedule risks
            high_risks = sum(
                1 for record in self.get_latest_risks(100)
                if record.get('risk_level', '').lower() == RISK_HIGH
            )
            
            # Commissioning
            comm_summary = self.get_commissioning_summary()
            pass_rate = comm_summary.get('pass_rate', 0.0)
            
            # RFIs
            recent_rfis = len(self.get_recent_rfis(100))
            
            summary = {
                'total_ncs': nc_stats['total'],
                'open_critical_ncs': open_critical,
                'at_risk_shipments': at_risk_shipments,
                'schedule_red_flags': high_risks,
                'commissioning_pass_rate': round(pass_rate, 2),
                'recent_rfis_count': recent_rfis,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Dashboard summary generated: {open_critical} critical, "
                       f"{at_risk_shipments} at-risk shipments")
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating dashboard summary: {str(e)}")
            return {
                'total_ncs': 0,
                'open_critical_ncs': 0,
                'at_risk_shipments': 0,
                'schedule_red_flags': 0,
                'commissioning_pass_rate': 0.0,
                'recent_rfis_count': 0,
                'timestamp': datetime.utcnow().isoformat()
            }


# Module-level function for singleton access
_supabase_manager = None

def get_supabase_manager() -> SupabaseManager:
    """
    Get or create Supabase manager singleton.
    
    Returns:
        SupabaseManager instance
    """
    global _supabase_manager
    if _supabase_manager is None:
        _supabase_manager = SupabaseManager()
    return _supabase_manager
