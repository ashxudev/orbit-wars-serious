# Historical Champion Gauntlet

This runbook tracks the local historical-opponent registry for the Distributed
Historical Champion Gauntlet segment. Cycle 0 is inventory only: it does not
run local gauntlet matches, launch Daytona jobs, or copy historical agent code
into this repo.

## Registry

The source-controlled registry is:

```text
experiments/historical_champions/registry.json
```

Each entry records a stable opponent name, source repo, absolute source file
path, source kind, callable name, historical submission ref and public score
where known, intended modes, loadability status, and a skip reason when the
current harness cannot load the candidate.

Loadable entries are intended to become `python_file` opponents in later full
500-step gauntlet manifests. Skipped entries are retained as explicit inventory
so known historical candidates are not silently lost.

## Current Loadable Champion Pool

The strongest currently loadable historical opponents come from
`/Users/user/dev/hackathons/orbit-wars-claude`, including prior visible
800+ public-score submissions:

- `claude-v3-wide-search-forecast` (`53555669`, public score `912.2`).
- `claude-v28-mode-split-champion` (`53585590`, public score `872.4`).
- `claude-v37-race-fix-mode-split` (`53602635`, public score `870.4`).
- `claude-v14-hammer-discipline` (`53585594`, public score `859.1`).
- `claude-v8-leader-weighted-denial` (`53556108`, public score `851.1`).
- `claude-v9-hold-aware-capture` (`53556449`, public score `841.9`).
- `claude-v31-race-awareness` (`53602639`, public score `826.6`).
- `claude-v62-low-pickoff-bundled` (`53641340`, public score `824.4`).

The registry also includes loadable `orbit-wars-2` frozen agents that were used
by the earlier bounded legacy-opponent smoke benchmark.

## Skipped Historical Candidates

Some original `/Users/user/dev/hackathons/orbit-wars` exported submissions are
listed as skipped because they currently raise loader errors under the
`python_file` harness. They should not be forced into a gauntlet until loader
compatibility is addressed. Keeping them in the registry with skip reasons
makes the inventory explicit without weakening the harness.

## Validation

Cycle 0 validation is loadability only. It proves that every entry marked
`loadable` can be imported as a callable through the current evaluation harness;
it does not call the agent, run official matches, write reports, or create
Daytona plans.

```bash
.venv/bin/python -m unittest tests.test_historical_champion_registry
.venv/bin/python -m unittest tests.test_evaluation_agent_loading tests.test_evaluation_official_runner
git diff --check
```

Future cycles should build full 500-step local/Daytona gauntlet manifests from
this registry, keeping generated match reports, logs, scoreboards, replays, and
temporary artifacts out of source control.

## Cycle 1 Full-Horizon Scenario Matrix

Cycle 1 adds source-controlled full-horizon manifest definitions only. These
manifests are Daytona-ready inputs for later sharding work, but this cycle does
not run any official-environment matches, Daytona packages, Daytona jobs, or
Kaggle commands.

The committed manifests are:

```text
experiments/manifests/historical-champion-gauntlet-2p-500.json
experiments/manifests/historical-champion-gauntlet-4p-500.json
```

Both manifests use the current modular runtime agent as `candidate_agent` and
schedule only registry entries with `loadability_status == "loadable"`. Every
scenario has `metadata.episode_steps` set to `"500"` so future local and
Daytona runners execute full-horizon gauntlet games intentionally.

The 2P matrix includes every loadable historical champion opponent across both
candidate seats, producing 22 deterministic scenarios. The 4P matrix includes
8 deterministic pool scenarios:

- Top-score champion pools across candidate seats 0, 1, 2, and 3.
- Mixed champion style pools across candidate seats 0 and 2.
- `orbit-wars-2` smoke-reference pools across candidate seats 0 and 3.

Skipped registry entries remain documented in the registry but are not included
in runnable manifests.

Cycle 1 validation is manifest parsing and loadability only:

```bash
.venv/bin/python -m unittest tests.test_historical_champion_registry tests.test_historical_champion_gauntlet_manifests
.venv/bin/python -m unittest tests.test_evaluation_manifest_fixtures tests.test_evaluation_agent_loading tests.test_evaluation_official_runner
git diff --check
```
