"""
FALSO Automation Services Package.
Exposes PermissionManager, RiskLevel, GoalPlanner, AutopilotAgent, Windows Controllers, and Audit Logging.
"""

from app.services.automation.autopilot import (
    AutopilotAgent,
    autopilot_agent,
    OperatingMode,
    TaskState,
    TaskStatus,
)
from app.services.automation.goal_planner import (
    goal_planner,
    GoalPlanner,
    PlanStep,
    TaskPlan,
)
from app.services.automation.permissions import (
    AuditLogEntry,
    FileOperation,
    PermissionCheckResult,
    PermissionLevel,
    PermissionManager,
    permission_manager,
    RiskLevel,
)

__all__ = [
    "PermissionManager",
    "permission_manager",
    "PermissionLevel",
    "FileOperation",
    "PermissionCheckResult",
    "AuditLogEntry",
    "RiskLevel",
    "AutopilotAgent",
    "autopilot_agent",
    "OperatingMode",
    "TaskStatus",
    "TaskState",
    "GoalPlanner",
    "goal_planner",
    "PlanStep",
    "TaskPlan",
]
