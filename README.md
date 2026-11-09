# plan-risk-scan

Flag what needs a human's attention before an InspectablePlan is
approved — so the reviewer sees the weak spots first instead of
finding them after execution.

Part of Week 1 (Inspectable Plans) of the trustworthy-agentic-ai
prototype for **BRJP26100123 — Building Trustworthy AI Systems through
Explainability and Human-in-the-Loop Control**. Companion repos:
[trustworthy-agentic-ai](https://github.com/anubhav9369/trustworthy-agentic-ai)
(the InspectablePlan schema),
[plan-explainer](https://github.com/anubhav9369/plan-explainer)
(plain-language rendering + review checklist), and
[plan-diff](https://github.com/anubhav9369/plan-diff)
(what changed between two plan versions).

## What it checks

`scan_plan` runs deterministic checks over a plan and returns findings
with a severity — high, medium, or low — worst first:

| Check | Severity | What it catches |
| --- | --- | --- |
| `no-goal` / `no-steps` / `empty-action` / `malformed-step` | high | Plan has nothing to check, execute, or review |
| `duplicate-step-id` | high | Two steps share an id, so matching by id is ambiguous |
| `ungated-irreversible` | high | A send / delete / publish / pay step runs without human permission |
| `permission-no-failure-mode` | high | A permission-gated step declares no failure points |
| `step-no-why` | medium | A step states no reason for existing |
| `step-no-failure-points` | medium | A step declares nothing that could go wrong |
| `no-constraints` | medium | Nothing bounds what the agent may do |
| `no-assumptions` | low | Hidden assumptions cannot be challenged |
| `no-alternatives` | low | A step lists no fallback |
| `decision-pending` | low | Plan has not been approved yet |
| `long-plan` | low | More than 8 steps — easy to approve without reading |

No LLM call: every finding traces to something the plan itself
declares (or fails to declare). Stdlib only, no third-party
dependencies.

## Usage

```bash
python3 plan_risk_scan.py plan.json
python3 plan_risk_scan.py plan.json --json
```

Exit code is 1 when any high-severity finding exists, 0 otherwise —
so the scan can gate execution in a script or CI step.

Examples — `examples/risky-plan.json` trips 14 findings (2 high,
7 medium, 5 low), including an ungated send step; `examples/clean-plan.json`
(the approved summarise-and-email plan) passes with 0 findings:

```bash
python3 plan_risk_scan.py examples/risky-plan.json   # exit 1
python3 plan_risk_scan.py examples/clean-plan.json   # exit 0
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

9 tests, all passing.
