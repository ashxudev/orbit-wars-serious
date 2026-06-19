# Competitive Improvement Baseline

This runbook establishes the local baseline for the current committed Orbit
Wars runtime agent before changing strategy, planner scoring, candidate
generation, or turn behavior.

The baseline is local evaluation only. It runs local `kaggle_environments`
matches through the existing `ow_eval` harness and does not submit to live Kaggle,
call Daytona, upload agents, or consume live competition submission quota.

## Purpose

Measure current strength before changing strategy. The committed manifest at
`experiments/manifests/competitive-baseline-smoke.json` mixes deterministic 2p
and 4p scenarios against built-in baseline opponents. It is broader than the
quick smoke fixtures but still small enough for routine local execution. Each
scenario sets `episode_steps` metadata so the local official environment runs a
bounded 5-step benchmark instead of a full-length match.

Do not tune scoring weights, planner candidate generation, mission evaluation,
response modeling, commitment policy, runtime dispatch, simulator behavior, or
submission bundling as part of this baseline cycle.

## Baseline Command

Run from `/Users/user/dev/hackathons/orbit-wars-serious`.

```bash
.venv/bin/python -m unittest discover -s tests
```

Then run the baseline manifest and write the generated report under `/tmp`.

```bash
.venv/bin/python scripts/run_evaluation_experiment.py experiments/manifests/competitive-baseline-smoke.json --report-output /tmp/ow-competitive-baseline-report.json
```

Inspect the compact result.

```bash
.venv/bin/python -c "import json; data=json.load(open('/tmp/ow-competitive-baseline-report.json', encoding='utf-8')); print(data['manifest_name'], data['scoreboard_record']['completed_matches'], data['promotion_decision']['passed'])"
```

## Interpreting The Report

- `scoreboard_record` summarizes completed matches, wins, losses, errors, win
  rate, mean rank, mean score, and triage counts for the current agent.
- `analysis_pack` lists losses and severe/no-op-heavy behavior that should be
  converted into planner-improvement work items.
- `promotion_decision` applies conservative smoke thresholds. It is a
  baseline health check, not proof that the agent is competitive enough for a
  live submission.

## Output Policy

Generated reports, scoreboards, logs, match outputs, replays, generated
submissions, and temporary artifacts should not be committed. Use `/tmp` or
another ignored local path for baseline reports unless a future cycle
explicitly promotes a generated artifact to source.
