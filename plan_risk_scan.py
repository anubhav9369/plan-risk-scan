"""Plan risk scan — flag what needs a human's attention before approval.

An InspectablePlan is only trustworthy if a reviewer can see its weak
spots before approving it. ``scan_plan`` runs a set of deterministic
checks over the plan (Week 1 InspectablePlan schema from the
trustworthy-agentic-ai hub, BRJP26100123) and returns findings with a
severity — high, medium, or low — so the reviewer knows what to fix
first. No LLM call: every finding traces to something the plan itself
declares (or fails to declare).

Usage:
    python3 plan_risk_scan.py plan.json
    python3 plan_risk_scan.py plan.json --json

Exit code is 1 when any high-severity finding exists, 0 otherwise —
so the scan can gate execution in a script or CI step.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SEVERITIES = ("high", "medium", "low")

# Verbs whose effect is hard or impossible to undo once executed.
IRREVERSIBLE_WORDS = (
    "send", "email", "publish", "post", "share",
    "delete", "remove", "pay", "transfer", "charge",
)

MAX_STEPS_BEFORE_FATIGUE = 8


def _finding(code, severity, message, where="plan"):
    return {"code": code, "severity": severity, "message": message, "where": where}


def _steps(plan):
    steps = plan.get("steps")
    return steps if isinstance(steps, list) else []


def _sorted(findings):
    return sorted(findings,
                  key=lambda f: (SEVERITIES.index(f["severity"]), f["code"], f["where"]))


def scan_plan(plan: dict) -> list[dict]:
    """Scan an InspectablePlan dict and return findings, worst first."""
    if not isinstance(plan, dict):
        return [_finding("not-a-plan", "high", "Plan is not a JSON object.", "plan")]
    findings = []
    steps = _steps(plan)

    if not (plan.get("goal") or "").strip():
        findings.append(_finding(
            "no-goal", "high",
            "No goal stated — there is nothing to check the plan against."))
    if not steps:
        findings.append(_finding(
            "no-steps", "high",
            "Plan has no steps — nothing to execute or review."))
        return _sorted(findings)

    seen_ids = {}
    for index, step in enumerate(steps):
        where = step.get("id") or f"step {index + 1}"
        if not isinstance(step, dict):
            findings.append(_finding(
                "malformed-step", "high",
                f"Step {index + 1} is not an object.", where))
            continue
        action = (step.get("action") or "").strip()
        if not action:
            findings.append(_finding(
                "empty-action", "high",
                "Step has no action — it cannot be executed or reviewed.", where))
            continue
        step_id = step.get("id")
        if step_id:
            if step_id in seen_ids:
                findings.append(_finding(
                    "duplicate-step-id", "high",
                    f"Step id '{step_id}' is used twice — matching steps by id is ambiguous.",
                    where))
            seen_ids[step_id] = index
        irreversible = any(word in action.lower() for word in IRREVERSIBLE_WORDS)
        if irreversible and not step.get("needs_permission"):
            findings.append(_finding(
                "ungated-irreversible", "high",
                f"'{action}' is hard to undo but runs without human permission.", where))
        if step.get("needs_permission") and not step.get("failure_points"):
            findings.append(_finding(
                "permission-no-failure-mode", "high",
                "Permission-gated step declares no failure points — the approver cannot judge the risk.",
                where))
        if not (step.get("why") or "").strip():
            findings.append(_finding(
                "step-no-why", "medium",
                "Step states no reason — a reviewer cannot tell whether it serves the goal.",
                where))
        if not step.get("failure_points"):
            findings.append(_finding(
                "step-no-failure-points", "medium",
                "Step declares no failure points — nothing says what could go wrong.", where))
        if not step.get("alternatives_considered"):
            findings.append(_finding(
                "no-alternatives", "low",
                "Step lists no alternatives — no fallback was considered.", where))

    if not plan.get("constraints"):
        findings.append(_finding(
            "no-constraints", "medium",
            "No constraints declared — nothing bounds what the agent may do."))
    if not plan.get("assumptions"):
        findings.append(_finding(
            "no-assumptions", "low",
            "No assumptions declared — hidden assumptions cannot be challenged."))
    decision = plan.get("human_decision") or {}
    if decision.get("status") != "approved":
        findings.append(_finding(
            "decision-pending", "low",
            "Plan has not been approved yet — review before execution."))
    if len(steps) > MAX_STEPS_BEFORE_FATIGUE:
        findings.append(_finding(
            "long-plan", "low",
            f"Plan has {len(steps)} steps — long plans are easy to approve without reading."))
    return _sorted(findings)


def summarise(findings):
    """Count findings by severity: {'total': n, 'high': n, 'medium': n, 'low': n}."""
    counts = {severity: 0 for severity in SEVERITIES}
    for finding in findings:
        counts[finding["severity"]] += 1
    return {"total": len(findings), **counts}


def render_report(plan, findings):
    """One short Markdown report a reviewer can read in a minute."""
    goal = (plan.get("goal") or "(no goal)").strip()
    counts = summarise(findings)
    lines = [
        f"# Risk scan: {goal}",
        "",
        f"{counts['total']} finding(s) — {counts['high']} high, "
        f"{counts['medium']} medium, {counts['low']} low.",
        "",
    ]
    if not findings:
        lines.append("No findings — nothing in the plan tripped a check.")
    for finding in findings:
        lines.append(
            f"- [{finding['severity'].upper()}] {finding['code']} "
            f"({finding['where']}): {finding['message']}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    argv = [arg for arg in argv if arg != "--json"]
    if len(argv) != 1:
        print("usage: python3 plan_risk_scan.py plan.json [--json]", file=sys.stderr)
        return 2
    try:
        plan = json.loads(Path(argv[0]).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read plan: {exc}", file=sys.stderr)
        return 2
    findings = scan_plan(plan)
    if as_json:
        print(json.dumps({
            "goal": plan.get("goal"),
            "summary": summarise(findings),
            "findings": findings,
        }, indent=2))
    else:
        print(render_report(plan, findings), end="")
    return 1 if summarise(findings)["high"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
