import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent.tools import execute_tool


ROOT = Path(__file__).resolve().parents[1]
APPROVALS_PATH = ROOT / "data" / "runtime" / "approvals.json"
APPROVAL_TTL_MINUTES = 30
_APPROVAL_LOCK = threading.Lock()


def create_pending_approval(tool: str, arguments: dict) -> dict:
    now = datetime.now(timezone.utc)
    approval = {
        "approval_id": f"APR-{uuid.uuid4().hex[:8].upper()}",
        "tool": tool,
        "arguments": arguments,
        "status": "Pending",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=APPROVAL_TTL_MINUTES)).isoformat(),
        "reviewed_at": None,
        "reviewed_by": None,
        "execution_result": None,
    }

    with _APPROVAL_LOCK:
        approvals = _load_approvals()
        approvals.append(approval)
        _write_approvals(approvals)

    return approval


def approve_pending_action(approval_id: str, approved_by: str) -> dict:
    if not approved_by.strip():
        raise ValueError("approved_by is required.")

    with _APPROVAL_LOCK:
        approvals = _load_approvals()
        approval = _find_approval(approvals, approval_id)
        _validate_pending(approval)

        result = execute_tool(
            approval["tool"],
            approval["arguments"],
            approval_context={
                "approval_id": approval["approval_id"],
                "approved_by": approved_by.strip(),
            },
        )
        approval["status"] = "Executed" if result.get("ok") else "Execution Failed"
        approval["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        approval["reviewed_by"] = approved_by.strip()
        approval["execution_result"] = result
        _write_approvals(approvals)

    return {"approval": approval, "result": result}


def reject_pending_action(approval_id: str, rejected_by: str) -> dict:
    if not rejected_by.strip():
        raise ValueError("rejected_by is required.")

    with _APPROVAL_LOCK:
        approvals = _load_approvals()
        approval = _find_approval(approvals, approval_id)
        _validate_pending(approval)
        approval["status"] = "Rejected"
        approval["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        approval["reviewed_by"] = rejected_by.strip()
        _write_approvals(approvals)

    return {"approval": approval, "message": "Proposed action rejected; no write occurred."}


def _load_approvals() -> list[dict]:
    if not APPROVALS_PATH.exists():
        return []
    return json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))


def _find_approval(approvals: list[dict], approval_id: str) -> dict:
    normalized = approval_id.upper().strip()
    approval = next(
        (item for item in approvals if item.get("approval_id") == normalized),
        None,
    )
    if approval is None:
        raise ValueError(f"Approval {normalized} was not found.")
    return approval


def _validate_pending(approval: dict):
    if approval.get("status") != "Pending":
        raise ValueError(
            f"Approval {approval['approval_id']} is already {approval.get('status')}."
        )
    expires_at = datetime.fromisoformat(approval["expires_at"])
    if datetime.now(timezone.utc) >= expires_at:
        approval["status"] = "Expired"
        raise ValueError(f"Approval {approval['approval_id']} has expired.")


def _write_approvals(approvals: list[dict]):
    APPROVALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = APPROVALS_PATH.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(approvals, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(APPROVALS_PATH)
