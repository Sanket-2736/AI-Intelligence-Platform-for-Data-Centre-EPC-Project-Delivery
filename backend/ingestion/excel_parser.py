"""
Excel Parser module.
Handles Excel file parsing using openpyxl for schedule extraction
and project data processing. Production-quality with full type hints.
"""

from typing import List, Dict, Any, Tuple, Optional
import openpyxl
from openpyxl.utils import get_column_letter
import pandas as pd
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


def parse_schedule_excel(file_path: str) -> Dict[str, Any]:
    """
    Parse an Excel project schedule file.
    
    Detects header row, normalizes dates, calculates derived fields.
    
    Args:
        file_path: Path to Excel file
        
    Returns:
        {
            'total_tasks': int,
            'columns': List[str],
            'tasks': List[Dict],
            'overdue_count': int,
            'at_risk_count': int,
            'summary_stats': {
                'pct_complete_avg': float,
                'tasks_completed': int,
                'tasks_in_progress': int,
                'tasks_not_started': int
            },
            'success': bool,
            'error': Optional[str]
        }
    """
    try:
        df = pd.read_excel(file_path, sheet_name=0)
        
        if df.empty:
            return {
                'total_tasks': 0,
                'columns': [],
                'tasks': [],
                'overdue_count': 0,
                'at_risk_count': 0,
                'summary_stats': {},
                'success': False,
                'error': 'Excel sheet is empty'
            }

        # Convert column names to strings and strip whitespace
        df.columns = [str(col).strip() for col in df.columns]
        
        # Remove entirely empty rows
        df = df.dropna(how='all')
        
        tasks = []
        today = datetime.now().date()
        
        for idx, row in df.iterrows():
            task = {}
            
            for col in df.columns:
                value = row[col]
                
                # Convert dates to ISO strings
                if isinstance(value, (datetime, date)):
                    value = value.isoformat()
                elif pd.isna(value):
                    value = None
                    
                task[col] = value
            
            # Calculate derived fields
            finish_col = next((col for col in df.columns if 'finish' in col.lower() or 'end' in col.lower()), None)
            baseline_col = next((col for col in df.columns if 'baseline' in col.lower()), None)
            pct_col = next((col for col in df.columns if '%' in col.lower() or 'complete' in col.lower()), None)
            
            if finish_col and task.get(finish_col):
                try:
                    if isinstance(task[finish_col], str):
                        finish_date = datetime.fromisoformat(task[finish_col]).date()
                    else:
                        finish_date = task[finish_col]
                    
                    days_remaining = (finish_date - today).days
                    task['days_remaining'] = days_remaining
                    
                    pct_complete = float(task.get(pct_col, 0)) if task.get(pct_col) else 0
                    task['is_overdue'] = today > finish_date and pct_complete < 100
                    
                except Exception as e:
                    logger.warning(f"Error calculating days_remaining: {str(e)}")
                    task['days_remaining'] = None
                    task['is_overdue'] = False
            
            if baseline_col and finish_col:
                try:
                    if isinstance(task.get(finish_col), str):
                        finish_date = datetime.fromisoformat(task[finish_col]).date()
                    else:
                        finish_date = task.get(finish_col)
                    
                    if isinstance(task.get(baseline_col), str):
                        baseline_date = datetime.fromisoformat(task[baseline_col]).date()
                    else:
                        baseline_date = task.get(baseline_col)
                    
                    if finish_date and baseline_date:
                        task['float_days'] = (finish_date - baseline_date).days
                    else:
                        task['float_days'] = None
                        
                except Exception as e:
                    logger.warning(f"Error calculating float_days: {str(e)}")
                    task['float_days'] = None
            
            tasks.append(task)
        
        # Calculate summary stats
        overdue_count = sum(1 for t in tasks if t.get('is_overdue', False))
        
        pct_col = next((col for col in df.columns if '%' in col.lower() or 'complete' in col.lower()), None)
        if pct_col:
            pct_values = [float(t.get(pct_col, 0)) for t in tasks if t.get(pct_col) is not None]
            pct_complete_avg = sum(pct_values) / len(pct_values) if pct_values else 0
        else:
            pct_complete_avg = 0

        summary_stats = {
            'pct_complete_avg': round(pct_complete_avg, 2),
            'tasks_completed': sum(1 for t in tasks if t.get(pct_col, 0) == 100) if pct_col else 0,
            'tasks_in_progress': sum(1 for t in tasks if 0 < t.get(pct_col, 0) < 100) if pct_col else 0,
            'tasks_not_started': sum(1 for t in tasks if t.get(pct_col, 0) == 0) if pct_col else 0,
        }

        return {
            'total_tasks': len(tasks),
            'columns': list(df.columns),
            'tasks': tasks,
            'overdue_count': overdue_count,
            'at_risk_count': sum(1 for t in tasks if t.get('days_remaining', 0) and t.get('days_remaining', 0) < 0),
            'summary_stats': summary_stats,
            'success': True,
            'error': None
        }

    except FileNotFoundError:
        error_msg = f"File not found: {file_path}"
        logger.error(error_msg)
        return {
            'total_tasks': 0,
            'columns': [],
            'tasks': [],
            'overdue_count': 0,
            'at_risk_count': 0,
            'summary_stats': {},
            'success': False,
            'error': error_msg
        }
    except Exception as e:
        error_msg = f"Error parsing schedule Excel: {str(e)}"
        logger.error(error_msg)
        return {
            'total_tasks': 0,
            'columns': [],
            'tasks': [],
            'overdue_count': 0,
            'at_risk_count': 0,
            'summary_stats': {},
            'success': False,
            'error': error_msg
        }


def parse_procurement_csv(file_path: str) -> Dict[str, Any]:
    """
    Parse procurement/shipments CSV file.
    
    Expected columns: equipment_name, supplier, po_number, order_date, 
    required_on_site, eta, status, cost_usd, lat, lng
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        {
            'total_items': int,
            'at_risk_count': int,
            'items': List[Dict],
            'at_risk_items': List[Dict],
            'success': bool,
            'error': Optional[str]
        }
    """
    try:
        df = pd.read_csv(file_path)
        
        if df.empty:
            return {
                'total_items': 0,
                'at_risk_count': 0,
                'items': [],
                'at_risk_items': [],
                'success': False,
                'error': 'CSV file is empty'
            }

        df.columns = [str(col).strip() for col in df.columns]
        df = df.dropna(how='all')
        
        items = []
        at_risk_items = []
        
        for idx, row in df.iterrows():
            item = {}
            
            for col in df.columns:
                value = row[col]
                if pd.isna(value):
                    value = None
                item[col] = value
            
            # Calculate derived fields
            required_col = next((col for col in df.columns if 'required' in col.lower() or 'needed' in col.lower()), None)
            eta_col = next((col for col in df.columns if 'eta' in col.lower()), None)
            status_col = next((col for col in df.columns if 'status' in col.lower()), None)
            
            if required_col and eta_col:
                try:
                    if isinstance(item.get(required_col), str):
                        required_date = pd.to_datetime(item[required_col]).date()
                    else:
                        required_date = item.get(required_col)
                    
                    if isinstance(item.get(eta_col), str):
                        eta_date = pd.to_datetime(item[eta_col]).date()
                    else:
                        eta_date = item.get(eta_col)
                    
                    if required_date and eta_date:
                        buffer_days = (required_date - eta_date).days
                        item['buffer_days'] = buffer_days
                        
                        # Flag at risk
                        status = str(item.get(status_col, '')).upper()
                        at_risk = buffer_days < 14 or status == "DELAYED"
                        item['at_risk'] = at_risk
                        
                        if at_risk:
                            at_risk_items.append(item)
                    else:
                        item['buffer_days'] = None
                        item['at_risk'] = False
                        
                except Exception as e:
                    logger.warning(f"Error calculating buffer_days: {str(e)}")
                    item['buffer_days'] = None
                    item['at_risk'] = False
            else:
                item['at_risk'] = False
            
            items.append(item)
        
        return {
            'total_items': len(items),
            'at_risk_count': len(at_risk_items),
            'items': items,
            'at_risk_items': at_risk_items,
            'success': True,
            'error': None
        }

    except FileNotFoundError:
        error_msg = f"File not found: {file_path}"
        logger.error(error_msg)
        return {
            'total_items': 0,
            'at_risk_count': 0,
            'items': [],
            'at_risk_items': [],
            'success': False,
            'error': error_msg
        }
    except Exception as e:
        error_msg = f"Error parsing procurement CSV: {str(e)}"
        logger.error(error_msg)
        return {
            'total_items': 0,
            'at_risk_count': 0,
            'items': [],
            'at_risk_items': [],
            'success': False,
            'error': error_msg
        }


def detect_schedule_format(file_path: str) -> str:
    """
    Detect whether Excel was exported from P6 or MS Project.
    
    Args:
        file_path: Path to Excel file
        
    Returns:
        "P6" | "MS_PROJECT" | "GENERIC"
    """
    try:
        df = pd.read_excel(file_path, sheet_name=0, nrows=1)
        columns_lower = [col.lower() for col in df.columns]
        
        # P6 indicators
        p6_indicators = ['activity id', 'activity name', 'baseline start', 'baseline finish']
        p6_count = sum(1 for ind in p6_indicators if any(ind in col for col in columns_lower))
        
        # MS Project indicators
        ms_indicators = ['task name', 'duration', 'predecessors', 'resource names']
        ms_count = sum(1 for ind in ms_indicators if any(ind in col for col in columns_lower))
        
        if p6_count >= 2:
            logger.info(f"Detected P6 format for {file_path}")
            return "P6"
        elif ms_count >= 2:
            logger.info(f"Detected MS Project format for {file_path}")
            return "MS_PROJECT"
        else:
            logger.info(f"Detected generic schedule format for {file_path}")
            return "GENERIC"

    except Exception as e:
        logger.warning(f"Error detecting schedule format: {str(e)} - defaulting to GENERIC")
        return "GENERIC"


def normalize_task_columns(tasks: List[Dict[str, Any]], format: str) -> List[Dict[str, Any]]:
    """
    Normalize task columns to standard names based on detected format.
    
    Maps format-specific column names to:
    task_id, task_name, start_date, end_date, duration_days, pct_complete, predecessors, resources
    
    Args:
        tasks: List of task dictionaries
        format: "P6" | "MS_PROJECT" | "GENERIC"
        
    Returns:
        List of normalized task dictionaries
    """
    try:
        if not tasks:
            return []

        normalized = []
        
        for task in tasks:
            normalized_task = {}
            
            # Map based on format
            if format == "P6":
                normalized_task['task_id'] = task.get('Activity ID') or task.get('activity id')
                normalized_task['task_name'] = task.get('Activity Name') or task.get('activity name')
                normalized_task['start_date'] = task.get('Start') or task.get('start')
                normalized_task['end_date'] = task.get('Finish') or task.get('finish')
                normalized_task['duration_days'] = task.get('Duration') or task.get('duration')
                normalized_task['pct_complete'] = task.get('% Complete') or task.get('% complete')
                normalized_task['predecessors'] = task.get('Predecessor(s)') or task.get('Predecessors')
                normalized_task['resources'] = task.get('Resource Name(s)') or task.get('Resource Names')
                
            elif format == "MS_PROJECT":
                normalized_task['task_id'] = task.get('ID')
                normalized_task['task_name'] = task.get('Task Name') or task.get('Task name')
                normalized_task['start_date'] = task.get('Start') or task.get('start')
                normalized_task['end_date'] = task.get('Finish') or task.get('finish')
                normalized_task['duration_days'] = task.get('Duration') or task.get('duration')
                normalized_task['pct_complete'] = task.get('% Complete') or task.get('% complete')
                normalized_task['predecessors'] = task.get('Predecessors') or task.get('predecessors')
                normalized_task['resources'] = task.get('Resource Names') or task.get('Resource names')
                
            else:  # GENERIC
                # Try common column names
                for key, standard_name in [
                    ('task_id', ['ID', 'Task ID', 'id']),
                    ('task_name', ['Task Name', 'Name', 'Task', 'task']),
                    ('start_date', ['Start', 'Start Date', 'start']),
                    ('end_date', ['Finish', 'End', 'End Date', 'finish']),
                    ('duration_days', ['Duration', 'duration']),
                    ('pct_complete', ['% Complete', '% complete', '%_complete']),
                    ('predecessors', ['Predecessors', 'Predecessor', 'predecessors']),
                    ('resources', ['Resources', 'Resource', 'resources']),
                ]:
                    normalized_task[key] = next((task.get(col) for col in standard_name if col in task), None)
            
            # Add all original fields
            normalized_task.update(task)
            normalized.append(normalized_task)
        
        logger.info(f"Normalized {len(normalized)} tasks from {format} format")
        return normalized

    except Exception as e:
        logger.error(f"Error normalizing task columns: {str(e)}")
        return tasks
