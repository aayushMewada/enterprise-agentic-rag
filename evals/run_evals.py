"""Run observable end-to-end evaluations for the enterprise agent.

The evaluator intentionally scores only public behavior: selected tools, tool
status, stop reason, sources, and approval state. It does not request or score
private chain-of-thought.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.orchestrator import run_agent


DEFAULT_SCENARIOS = Path(__file__).with_name("scenarios.json")


@dataclass
class CheckResult:
    name: str
    passed: bool
    expected: Any
    actual: Any


@dataclass
class ScenarioResult:
    scenario_id: str
    passed: bool
    checks: list[CheckResult]
    tools: list[str]
    stop_reason: str | None
    approval_id: str | None
    answer_preview: str


def load_scenarios(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        scenarios = json.load(handle)
    if not isinstance(scenarios, list):
        raise ValueError("Evaluation file must contain a JSON list.")
    return scenarios


def _approval_from_result(result: dict[str, Any]) -> dict[str, Any] | None:
    # The CLI/API adapters may expose the same frozen proposal under different
    # public field names. Accept those shapes while still requiring an explicit
    # approval signal from the orchestrator.
    for field in (
        "pending_approval",
        "approval",
        "approval_request",
        "pending_action",
        "approval_required",
    ):
        approval = result.get(field)
        if isinstance(approval, dict):
            return approval

    if result.get("approval_id"):
        return {"approval_id": result["approval_id"]}

    # A bounded agent may deliberately omit proposal details from its public
    # return value while exposing the governed stop condition. This is still an
    # observable approval boundary, not an executed write.
    if result.get("stop_reason") == "approval_required":
        return {"approval_id": None}

    return None


def score_scenario(scenario: dict[str, Any], result: dict[str, Any]) -> ScenarioResult:
    trace = result.get("trace") or []
    tools = [entry.get("tool") for entry in trace if entry.get("tool")]
    approval = _approval_from_result(result)
    checks: list[CheckResult] = []

    for tool in scenario.get("required_tools", []):
        checks.append(CheckResult(f"required tool: {tool}", tool in tools, True, tool in tools))

    for tool in scenario.get("forbidden_tools", []):
        checks.append(CheckResult(f"forbidden tool: {tool}", tool not in tools, False, tool in tools))

    expected_approval = bool(scenario.get("expect_approval", False))
    checks.append(
        CheckResult("approval state", bool(approval) == expected_approval, expected_approval, bool(approval))
    )

    expected_stop = scenario.get("expected_stop_reason")
    if expected_stop:
        checks.append(
            CheckResult(
                "stop reason",
                result.get("stop_reason") == expected_stop,
                expected_stop,
                result.get("stop_reason"),
            )
        )

    failed_tool = scenario.get("require_failed_tool")
    if failed_tool:
        matching = [entry for entry in trace if entry.get("tool") == failed_tool]
        observed_failure = bool(matching) and any(not entry.get("ok", False) for entry in matching)
        checks.append(CheckResult(f"blocked tool: {failed_tool}", observed_failure, True, observed_failure))

    guarded_tool = scenario.get("require_blocked_or_omitted_tool")
    if guarded_tool:
        matching = [entry for entry in trace if entry.get("tool") == guarded_tool]
        safe_behavior = not matching or all(not entry.get("ok", False) for entry in matching)
        checks.append(
            CheckResult(
                f"blocked or omitted tool: {guarded_tool}",
                safe_behavior,
                True,
                safe_behavior,
            )
        )

    answer = str(result.get("answer") or "")
    checks.append(CheckResult("non-empty answer", bool(answer.strip()), True, bool(answer.strip())))

    return ScenarioResult(
        scenario_id=scenario["id"],
        passed=all(check.passed for check in checks),
        checks=checks,
        tools=tools,
        stop_reason=result.get("stop_reason"),
        approval_id=(approval or {}).get("approval_id"),
        answer_preview=answer.replace("\n", " ")[:180],
    )


def run_scenario(scenario: dict[str, Any]) -> ScenarioResult:
    result = run_agent(scenario["prompt"])
    if not isinstance(result, dict):
        raise TypeError("run_agent must return a dictionary.")
    return score_scenario(scenario, result)


def print_human_report(results: list[ScenarioResult]) -> None:
    for result in results:
        marker = "PASS" if result.passed else "FAIL"
        print(f"\n[{marker}] {result.scenario_id}")
        print(f"  tools: {', '.join(result.tools) or '(none)'}")
        print(f"  stop: {result.stop_reason}")
        if result.approval_id:
            print(f"  approval: {result.approval_id}")
        for check in result.checks:
            check_marker = "ok" if check.passed else "x"
            print(f"  [{check_marker}] {check.name}: expected={check.expected!r}, actual={check.actual!r}")

    passed = sum(result.passed for result in results)
    print(f"\nEvaluation score: {passed}/{len(results)} scenarios passed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate observable agent behavior.")
    parser.add_argument("--file", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--scenario", help="Run only one scenario ID.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    scenarios = load_scenarios(args.file)
    if args.scenario:
        scenarios = [scenario for scenario in scenarios if scenario.get("id") == args.scenario]
        if not scenarios:
            raise ValueError(f"Scenario {args.scenario!r} was not found.")

    results = [run_scenario(scenario) for scenario in scenarios]
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        print_human_report(results)
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
