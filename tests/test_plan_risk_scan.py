"""Tests for plan_risk_scan."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plan_risk_scan import scan_plan, summarise  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


def load(name):
    return json.loads((EXAMPLES / name).read_text())


def codes(findings, severity=None):
    return [f["code"] for f in findings
            if severity is None or f["severity"] == severity]


def minimal_plan(**overrides):
    """A clean one-step plan; override fields to break exactly one thing."""
    plan = {
        "goal": "Check the figures.",
        "steps": [{
            "id": "step-1",
            "action": "Check the figures against the ledger.",
            "why": "Catches a wrong number before it is shared.",
            "needs_permission": False,
            "failure_points": ["Ledger is out of date."],
            "alternatives_considered": ["Ask the owner to check."],
        }],
        "assumptions": ["The ledger is current."],
        "constraints": ["Share nothing externally before approval."],
        "risks": ["A wrong figure is shared."],
        "human_decision": {"status": "approved"},
    }
    plan.update(overrides)
    return plan


class TestPlanRiskScan(unittest.TestCase):
    def test_clean_plan_has_no_findings(self):
        self.assertEqual(scan_plan(load("clean-plan.json")), [])

    def test_risky_plan_flags_both_high_findings(self):
        findings = scan_plan(load("risky-plan.json"))
        self.assertIn("ungated-irreversible", codes(findings, "high"))
        self.assertIn("permission-no-failure-mode", codes(findings, "high"))
        self.assertEqual(summarise(findings)["high"], 2)

    def test_empty_plan(self):
        findings = scan_plan({})
        self.assertIn("no-goal", codes(findings, "high"))
        self.assertIn("no-steps", codes(findings, "high"))

    def test_ungated_irreversible_action(self):
        plan = minimal_plan()
        plan["steps"][0]["action"] = "Delete the old backups."
        self.assertIn("ungated-irreversible", codes(scan_plan(plan), "high"))

    def test_gated_step_with_failure_points_is_clean(self):
        plan = minimal_plan()
        plan["steps"][0]["action"] = "Send the email."
        plan["steps"][0]["needs_permission"] = True
        self.assertEqual(scan_plan(plan), [])

    def test_duplicate_step_ids(self):
        plan = minimal_plan()
        plan["steps"].append(dict(plan["steps"][0]))
        self.assertEqual(codes(scan_plan(plan)), ["duplicate-step-id"])

    def test_step_without_why(self):
        plan = minimal_plan()
        del plan["steps"][0]["why"]
        self.assertEqual(codes(scan_plan(plan)), ["step-no-why"])

    def test_findings_sorted_high_before_low(self):
        findings = scan_plan(load("risky-plan.json"))
        order = {"high": 0, "medium": 1, "low": 2}
        severities = [order[f["severity"]] for f in findings]
        self.assertEqual(severities, sorted(severities))

    def test_cli_exit_codes(self):
        clean = subprocess.run(
            [sys.executable, str(ROOT / "plan_risk_scan.py"),
             str(EXAMPLES / "clean-plan.json")],
            capture_output=True, text=True)
        risky = subprocess.run(
            [sys.executable, str(ROOT / "plan_risk_scan.py"),
             str(EXAMPLES / "risky-plan.json")],
            capture_output=True, text=True)
        self.assertEqual(clean.returncode, 0)
        self.assertEqual(risky.returncode, 1)
        self.assertIn("No findings", clean.stdout)
        self.assertIn("HIGH", risky.stdout)


if __name__ == "__main__":
    unittest.main()
