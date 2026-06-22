"""
Predictive Schedule Risk Engine module.
Analyzes project schedules for risks and identifies critical path issues.
"""

import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime, timedelta
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
import tempfile

from ingestion import excel_parser
from utils import cerebras_client
from db.supabase_client import get_supabase_manager
from agents.prompts import SCHEDULE_RISK_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class RiskLevel(str, Enum):
    """Risk levels for schedule tasks."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ScheduleRisk(BaseModel):
    """Single risk finding."""
    risk_id: str
    task_name: str
    risk_level: RiskLevel
    risk_description: str
    potential_delay_days: int
    mitigation: str
    snapshot_date: str


class ScheduleAnalysisResponse(BaseModel):
    """Full schedule analysis response."""
    project_health: str  # GREEN|AMBER|RED
    overall_risk_score: int  # 0-100
    projected_delay_weeks: int
    executive_summary: str
    total_tasks: int
    overdue_tasks: int
    critical_path_at_risk: int
    risks: List[Dict[str, Any]]
    processing_time_ms: int
    success: bool
    error: Optional[str] = None


class BaselineComparison(BaseModel):
    """Baseline schedule comparison."""
    tasks_slipped: int
    tasks_on_time: int
    tasks_ahead: int
    total_slippage_days: int
    critical_path_slippage_days: int
    recovery_analysis: str


class RiskTrendData(BaseModel):
    """Time-series risk data."""
    dates: List[str]
    critical_count: List[int]
    high_count: List[int]
    medium_count: List[int]
    risk_score_trend: List[int]


class CriticalPathTask(BaseModel):
    """Critical path task."""
    task_name: str
    task_id: Optional[str]
    days_remaining: int
    pct_complete: int
    predecessors: Optional[str]
    float_days: Optional[int]


# ============================================================================
# CORE SCHEDULE ANALYSIS FUNCTIONS
# ============================================================================


def analyse_schedule(
    excel_path: str,
    project_name: str = "Data Centre Project"
) -> Dict[str, Any]:
    """
    Analyze project schedule for risks and delays.
    
    Full pipeline: parse, normalize, identify risks, call Cerebras, log findings.
    
    Args:
        excel_path: Path to schedule Excel file
        project_name: Project name for context
        
    Returns:
        Full risk analysis report
    """
    start_time = time.time()
    
    try:
        logger.info(f"Starting schedule analysis for {project_name}")
        
        # Step 1: Parse schedule
        parse_result = excel_parser.parse_schedule_excel(excel_path)
        
        if not parse_result['success']:
            return {
                'project_health': 'UNKNOWN',
                'overall_risk_score': 0,
                'projected_delay_weeks': 0,
                'executive_summary': 'Failed to parse schedule',
                'total_tasks': 0,
                'overdue_tasks': 0,
                'critical_path_at_risk': 0,
                'risks': [],
                'processing_time_ms': round((time.time() - start_time) * 1000, 0),
                'success': False,
                'error': parse_result.get('error')
            }
        
        tasks = parse_result.get('tasks', [])
        total_tasks = len(tasks)
        
        # Step 2: Detect format and normalize
        format_type = excel_parser.detect_schedule_format(excel_path)
        normalized_tasks = excel_parser.normalize_task_columns(tasks, format_type)
        
        # Step 3: Identify key metrics
        overdue_tasks = sum(1 for t in normalized_tasks if t.get('is_overdue', False))
        critical_path_tasks = get_critical_path_tasks(normalized_tasks)
        at_risk_critical = sum(1 for t in critical_path_tasks if t.get('days_remaining', 0) < 0)
        
        # Step 4: Build schedule summary for Cerebras
        schedule_text = _build_schedule_summary(
            normalized_tasks,
            parse_result.get('summary_stats', {}),
            critical_path_tasks
        )
        
        # Step 5: Call Cerebras
        llm = cerebras_client.get_cerebras_client()
        
        user_message = f"""PROJECT: {project_name}
SCHEDULE FORMAT: {format_type}

{schedule_text}

Perform a comprehensive schedule risk analysis."""
        
        analysis_result = llm.call_structured(
            system_prompt=SCHEDULE_RISK_SYSTEM_PROMPT,
            user_message=user_message
        )
        
        if analysis_result.get('error'):
            logger.error(f"Cerebras error: {analysis_result.get('error')}")
            return {
                'project_health': 'UNKNOWN',
                'overall_risk_score': 0,
                'projected_delay_weeks': 0,
                'executive_summary': 'LLM analysis failed',
                'total_tasks': total_tasks,
                'overdue_tasks': overdue_tasks,
                'critical_path_at_risk': at_risk_critical,
                'risks': [],
                'processing_time_ms': round((time.time() - start_time) * 1000, 0),
                'success': False,
                'error': analysis_result.get('error')
            }
        
        # Step 6: Store findings in Supabase
        db = get_supabase_manager()
        snapshot_date = datetime.now().date().isoformat()
        
        for risk in analysis_result.get('critical_risks', []):
            risk_data = {
                'task_name': risk.get('task_name', 'Unknown'),
                'risk_level': risk.get('severity', 'medium').lower(),
                'risk_description': risk.get('description', ''),
                'mitigation': json.dumps(risk.get('mitigation_options', [])),
                'snapshot_date': snapshot_date
            }
            db.insert_schedule_risk(risk_data)
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        logger.info(
            f"Schedule analysis complete: {analysis_result.get('project_health', 'UNKNOWN')}, "
            f"score: {analysis_result.get('overall_risk_score', 0)}"
        )
        
        return {
            'project_health': analysis_result.get('project_health', 'UNKNOWN'),
            'overall_risk_score': analysis_result.get('overall_risk_score', 0),
            'projected_delay_weeks': analysis_result.get('projected_delay_weeks', 0),
            'executive_summary': analysis_result.get('executive_summary', ''),
            'total_tasks': total_tasks,
            'overdue_tasks': overdue_tasks,
            'critical_path_at_risk': at_risk_critical,
            'risks': analysis_result.get('critical_risks', []),
            'processing_time_ms': round(processing_time_ms, 0),
            'success': True,
            'error': None
        }
        
    except Exception as e:
        error_msg = f"Schedule analysis error: {str(e)}"
        logger.error(error_msg)
        return {
            'project_health': 'UNKNOWN',
            'overall_risk_score': 0,
            'projected_delay_weeks': 0,
            'executive_summary': 'Analysis failed',
            'total_tasks': 0,
            'overdue_tasks': 0,
            'critical_path_at_risk': 0,
            'risks': [],
            'processing_time_ms': round((time.time() - start_time) * 1000, 0),
            'success': False,
            'error': error_msg
        }


def get_critical_path_tasks(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Identify likely critical path tasks using heuristics.
    
    Heuristics:
    - Tasks with 0 float days
    - Tasks with "critical" in name
    - Tasks with latest finish dates that are incomplete
    
    Args:
        tasks: Normalized task list
        
    Returns:
        Sorted list of likely critical path tasks
    """
    try:
        critical_tasks = []
        
        for task in tasks:
            is_critical = False
            critical_reason = ""
            
            # Check 1: Zero float
            if task.get('float_days') == 0:
                is_critical = True
                critical_reason = "Zero float"
            
            # Check 2: "Critical" in name
            if "critical" in (task.get('task_name', '') or "").lower():
                is_critical = True
                critical_reason = "Critical in task name"
            
            # Check 3: Latest finish dates + incomplete
            pct_complete = task.get('pct_complete', 0)
            if pct_complete < 100 and task.get('is_overdue', False):
                is_critical = True
                critical_reason = "Late + incomplete"
            
            if is_critical:
                critical_tasks.append({
                    **task,
                    'critical_reason': critical_reason
                })
        
        # Sort by days_remaining (most at-risk first)
        critical_tasks.sort(
            key=lambda t: (t.get('days_remaining', 999), -t.get('pct_complete', 0))
        )
        
        logger.info(f"Identified {len(critical_tasks)} critical path tasks")
        
        return critical_tasks
        
    except Exception as e:
        logger.error(f"Error identifying critical path: {str(e)}")
        return []


def compare_schedule_to_baseline(
    current_path: str,
    baseline_path: str
) -> Dict[str, Any]:
    """
    Compare current schedule to baseline and identify slippage.
    
    Args:
        current_path: Path to current schedule
        baseline_path: Path to baseline schedule
        
    Returns:
        Slippage analysis
    """
    start_time = time.time()
    
    try:
        logger.info("Comparing schedule to baseline")
        
        # Parse both schedules
        current_result = excel_parser.parse_schedule_excel(current_path)
        baseline_result = excel_parser.parse_schedule_excel(baseline_path)
        
        if not current_result['success'] or not baseline_result['success']:
            return {
                'tasks_slipped': 0,
                'tasks_on_time': 0,
                'tasks_ahead': 0,
                'total_slippage_days': 0,
                'critical_path_slippage_days': 0,
                'recovery_analysis': 'Failed to parse schedules',
                'success': False
            }
        
        current_tasks = {t.get('task_name'): t for t in current_result.get('tasks', [])}
        baseline_tasks = {t.get('task_name'): t for t in baseline_result.get('tasks', [])}
        
        # Compare tasks
        slipped = []
        on_time = []
        ahead = []
        total_slippage = 0
        
        for task_name, current_task in current_tasks.items():
            baseline_task = baseline_tasks.get(task_name)
            
            if not baseline_task:
                continue
            
            try:
                current_finish = current_task.get('end_date', '')
                baseline_finish = baseline_task.get('end_date', '')
                
                if current_finish and baseline_finish:
                    # Simple string comparison (assumes ISO date format)
                    if current_finish > baseline_finish:
                        slippage_days = (
                            len(current_finish) > 0 and 
                            len(baseline_finish) > 0 and
                            (datetime.fromisoformat(current_finish) - 
                             datetime.fromisoformat(baseline_finish)).days
                        ) or 0
                        
                        slipped.append({
                            'task_name': task_name,
                            'slippage_days': slippage_days,
                            'baseline_finish': baseline_finish,
                            'current_finish': current_finish
                        })
                        total_slippage += max(slippage_days, 0)
                    elif current_finish == baseline_finish:
                        on_time.append(task_name)
                    else:
                        ahead.append(task_name)
            except Exception as e:
                logger.warning(f"Error comparing task {task_name}: {str(e)}")
        
        # Identify critical path slippage
        critical_tasks = get_critical_path_tasks(current_result.get('tasks', []))
        critical_slipped = [t for t in slipped if any(ct.get('task_name') == t['task_name'] for ct in critical_tasks)]
        critical_slippage = sum(t.get('slippage_days', 0) for t in critical_slipped)
        
        # Call Cerebras for analysis
        slippage_text = f"""Current slippage summary:
- Tasks slipped: {len(slipped)}
- Total slippage: {total_slippage} days
- Critical path slippage: {critical_slippage} days
- Tasks on time: {len(on_time)}
- Tasks ahead: {len(ahead)}

Top slipped tasks: {json.dumps(slipped[:5], indent=2)}"""
        
        llm = cerebras_client.get_cerebras_client()
        
        recovery = llm.call(
            system_prompt="You are a schedule recovery expert. Analyze the slippage and recommend recovery options.",
            user_message=slippage_text,
            temperature=0.3,
            max_tokens=1500
        )
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        logger.info(f"Baseline comparison complete: {len(slipped)} tasks slipped")
        
        return {
            'tasks_slipped': len(slipped),
            'tasks_on_time': len(on_time),
            'tasks_ahead': len(ahead),
            'total_slippage_days': total_slippage,
            'critical_path_slippage_days': critical_slippage,
            'recovery_analysis': recovery,
            'processing_time_ms': round(processing_time_ms, 0),
            'success': True
        }
        
    except Exception as e:
        error_msg = f"Error comparing to baseline: {str(e)}"
        logger.error(error_msg)
        return {
            'tasks_slipped': 0,
            'tasks_on_time': 0,
            'tasks_ahead': 0,
            'total_slippage_days': 0,
            'critical_path_slippage_days': 0,
            'recovery_analysis': error_msg,
            'success': False
        }


def get_risk_trend_data() -> Dict[str, Any]:
    """
    Get risk trend data from Supabase for charting.
    
    Returns:
        Time-series data with dates and risk counts by level
    """
    try:
        db = get_supabase_manager()
        
        # Get trend data from past 30 days
        trend_data = db.get_risk_trend(days=30)
        
        dates = []
        critical_count = []
        high_count = []
        medium_count = []
        risk_score_trend = []
        
        for day_data in trend_data:
            dates.append(day_data.get('date', ''))
            critical_count.append(day_data.get('critical', 0))
            high_count.append(day_data.get('high', 0))
            medium_count.append(day_data.get('medium', 0))
            
            # Calculate daily risk score (weighted average)
            score = (
                critical_count[-1] * 10 +
                high_count[-1] * 5 +
                medium_count[-1] * 2
            ) / max(critical_count[-1] + high_count[-1] + medium_count[-1], 1)
            risk_score_trend.append(int(score))
        
        logger.info(f"Retrieved {len(dates)} days of risk trend data")
        
        return {
            'dates': dates,
            'critical_count': critical_count,
            'high_count': high_count,
            'medium_count': medium_count,
            'risk_score_trend': risk_score_trend,
            'success': True
        }
        
    except Exception as e:
        logger.error(f"Error getting risk trend: {str(e)}")
        return {
            'dates': [],
            'critical_count': [],
            'high_count': [],
            'medium_count': [],
            'risk_score_trend': [],
            'success': False
        }


def generate_weekly_risk_report(project_name: str) -> str:
    """
    Generate professional weekly risk report.
    
    Args:
        project_name: Project name
        
    Returns:
        Markdown-formatted report
    """
    try:
        db = get_supabase_manager()
        
        # Get latest risks
        latest_risks = db.get_latest_risks(limit=20)
        
        # Get summary stats
        stats = db.get_nc_summary_stats()
        
        # Build report content for Cerebras
        report_content = f"""PROJECT: {project_name}
REPORT DATE: {datetime.now().strftime('%Y-%m-%d')}

CURRENT RISKS (Last 20):
"""
        
        for risk in latest_risks[:5]:
            report_content += f"\n- {risk.get('task_name')}: {risk.get('risk_description')}\n"
            report_content += f"  Level: {risk.get('risk_level')}\n"
        
        report_content += f"\nSUMMARY:\nTotal identified risks: {len(latest_risks)}"
        
        # Call Cerebras to generate narrative
        llm = cerebras_client.get_cerebras_client()
        
        report_prompt = f"""Generate a professional weekly schedule risk report in markdown format.
Include:
1. Executive Summary (1-2 paragraphs)
2. Top 5 Critical Risks
3. Recommended Immediate Actions
4. Look-Ahead (next 2 weeks)

{report_content}"""
        
        report = llm.call(
            system_prompt="You are a professional project controls manager. Generate a clear, actionable weekly risk report.",
            user_message=report_prompt,
            temperature=0.4,
            max_tokens=2500
        )
        
        logger.info("Weekly report generated")
        
        return report
        
    except Exception as e:
        error_msg = f"Error generating report: {str(e)}"
        logger.error(error_msg)
        return f"# Error\n\n{error_msg}"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _build_schedule_summary(
    tasks: List[Dict[str, Any]],
    summary_stats: Dict[str, Any],
    critical_path: List[Dict[str, Any]]
) -> str:
    """Build concise schedule summary for Cerebras."""
    
    summary = f"""SCHEDULE SUMMARY:
Total Tasks: {len(tasks)}
% Complete (Avg): {summary_stats.get('pct_complete_avg', 0)}%
Completed Tasks: {summary_stats.get('tasks_completed', 0)}
In Progress: {summary_stats.get('tasks_in_progress', 0)}
Not Started: {summary_stats.get('tasks_not_started', 0)}

OVERDUE TASKS:
"""
    
    overdue = [t for t in tasks if t.get('is_overdue', False)]
    for task in overdue[:5]:
        summary += f"- {task.get('task_name')}: {task.get('days_remaining', 0)} days late\n"
    
    summary += f"\nCRITICAL PATH TASKS ({len(critical_path)} identified):\n"
    for task in critical_path[:10]:
        summary += f"- {task.get('task_name')}: {task.get('days_remaining', 0)} days remaining\n"
    
    # Tasks with tight buffer
    tight_buffer = [t for t in tasks if 0 < t.get('days_remaining', 999) < 7]
    summary += f"\nTASKS WITH < 7 DAY BUFFER: {len(tight_buffer)}\n"
    for task in tight_buffer[:5]:
        summary += f"- {task.get('task_name')}: {task.get('days_remaining', 0)} days\n"
    
    return summary


# ============================================================================
# FASTAPI ENDPOINTS
# ============================================================================


@router.post("/analyse", response_model=ScheduleAnalysisResponse, tags=["Schedule Agent"])
async def post_analyse_schedule(
    file: UploadFile = File(...),
    project_name: str = Form(default="Data Centre Project")
) -> ScheduleAnalysisResponse:
    """
    Analyze schedule for risks and delays.
    
    Args:
        file: Excel schedule file
        project_name: Project name
        
    Returns:
        Full risk analysis
    """
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            file.seek(0)
            tmp.write(await file.read())
            temp_path = tmp.name
        
        result = analyse_schedule(temp_path, project_name)
        
        return ScheduleAnalysisResponse(**result)
        
    except Exception as e:
        logger.error(f"Error in analyse endpoint: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


@router.post("/compare", response_model=BaselineComparison, tags=["Schedule Agent"])
async def post_compare_schedule(
    current: UploadFile = File(...),
    baseline: UploadFile = File(...)
) -> BaselineComparison:
    """
    Compare current schedule to baseline.
    
    Args:
        current: Current schedule file
        baseline: Baseline schedule file
        
    Returns:
        Baseline comparison analysis
    """
    temp_files = []
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            current.seek(0)
            tmp.write(await current.read())
            current_path = tmp.name
            temp_files.append(current_path)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            baseline.seek(0)
            tmp.write(await baseline.read())
            baseline_path = tmp.name
            temp_files.append(baseline_path)
        
        result = compare_schedule_to_baseline(current_path, baseline_path)
        
        return BaselineComparison(**result)
        
    except Exception as e:
        logger.error(f"Error in compare endpoint: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        for path in temp_files:
            Path(path).unlink(missing_ok=True)


@router.get("/trend", response_model=RiskTrendData, tags=["Schedule Agent"])
async def get_trend() -> RiskTrendData:
    """Get risk trend time-series data for charting."""
    try:
        result = get_risk_trend_data()
        return RiskTrendData(**result)
    except Exception as e:
        logger.error(f"Error in trend endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report", tags=["Schedule Agent"])
async def get_report(project_name: str = "Data Centre Project"):
    """Generate weekly risk report."""
    try:
        report = generate_weekly_risk_report(project_name)
        
        return {
            'report': report,
            'project_name': project_name,
            'generated_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in report endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risks", tags=["Schedule Agent"])
async def get_risks(
    risk_level: Optional[str] = None,
    limit: int = 20
):
    """Get schedule risks with optional filtering."""
    try:
        db = get_supabase_manager()
        
        risks = db.get_latest_risks(limit=limit)
        
        if risk_level:
            risks = [r for r in risks if r.get('risk_level', '').lower() == risk_level.lower()]
        
        return {
            'count': len(risks),
            'risks': risks,
            'risk_level_filter': risk_level
        }
        
    except Exception as e:
        logger.error(f"Error in risks endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
