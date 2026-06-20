# V0 Replay Leak Fix Fixtures

This note records the committed fixture set for the V0 replay leak fix segment.
The fixtures are compact single-observation JSON cases under
`tests/fixtures/v0_replay_leaks/`; full Kaggle replay downloads stay under
`docs/submission_replay_analyses/.../replay_episodes/` and should not be copied
into tests.

The fixture set characterizes current behavior only. It does not change
candidate generation, strategy selection, defense policy, capture-hold policy,
scoring, simulator mechanics, or action conversion.

Covered live submission `53862054` leak classes:

- 4P no-action/candidate starvation from episodes `80766287` and `80761836`.
- 2P pressure collapse from episodes `80756891` and `80760443`.
- 2P idle/near-idle opening from episode `80768833`.
- Capture-hold failure windows from episode `80763852` around turns `125` and
  `131`.

The later idle window in `80768833` is not committed because local state parsing
currently rejects later target-agent observations containing non-integer
`fleet.from_planet_id` rows. The committed opening observation remains parseable
and preserves the near-idle case context for later cycles.

## Cycle 9 V1 Candidate Readiness

Cycle 9 is a no-submit preparation cycle. It does not upload to Kaggle, does not
call Daytona, and does not change runtime or planner behavior. Generated
reports and submission artifacts were written only under `/tmp`.

Readiness was checked from commit `e3d0cde Add V0 replay regression harness`.

Replay regression summary:

```text
v0_replay_regression cases=7 live_actions=5 live_no_actions=2 budget_guarded=1 budgetless_actions=7 pressure_actions=4 risky_thin_captures=0 unresolved_planner_no_actions=0
```

The negative-overage pressure fixture remains counted as budget-blocked, not as
an unresolved planner leak.

Local readiness checks:

```text
.venv/bin/python -m unittest tests.test_v0_replay_regression
Ran 7 tests in 17.908s
OK

.venv/bin/python -m unittest tests.test_v0_replay_leak_fixtures
Ran 9 tests in 15.432s
OK

.venv/bin/python -m unittest discover -s tests
Ran 1249 tests in 324.254s
OK

.venv/bin/python scripts/evaluation_gate.py
gate=PASS matches=2 win_rate=1 mean_rank=1 error_rate=0 parity=pass failures=0

.venv/bin/python scripts/submission_preflight.py
submission_preflight=PASS total=4 passed=4 failed=0 failed_checks=none exit_code=0
```

Benchmark reports under `/tmp`:

```text
legacy-opponent-smoke 4 0.0 True
competitive-baseline-smoke 6 0.0 True
```

V1 candidate artifact:

```text
/tmp/orbit_wars_v1_candidate.py 316055 b05984e62d14190cf937c0b749862304e4a67a28e822c901fd47a7fbc57cc514
```

Optional local V1-vs-V0 smoke comparison was feasible without dirtying the repo:
the V0 source snapshot from commit `c558a30` was extracted under `/tmp`, a V0
reference artifact was built, and a temporary manifest compared the V1
candidate artifact against that V0 reference artifact.

```text
/tmp/orbit_wars_v0_reference_from_c558a30.py 304475 66b95ae02cf82a0801de2d4827496f1d992bf8de8cb790ac2a1743907d58ca64
v1-candidate-vs-v0-reference-smoke 2 0.0 True 1.0 1.0
```

Readiness conclusion: V1 is ready to proceed to the next live-submission
segment. The next segment should rebuild a fresh final artifact under `/tmp`,
rerun the local readiness checks, and make at most one live Kaggle submission
only after explicit live-submission approval.
