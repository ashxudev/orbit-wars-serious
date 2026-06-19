# Live Submission V0 Mechanism Preflight

This runbook documents the live Kaggle submission mechanism for Orbit Wars. It
does not authorize a live submission by itself. Run the local readiness gates and
confirm the final artifact before using the submit command.

## Competition

- Kaggle competition slug: `orbit-wars`
- Local source references:
  - `/Users/user/dev/hackathons/orbit-wars/README.md`
  - `/Users/user/dev/hackathons/orbit-wars-2/src/ow2/replay/top10.py`

## Final Artifact

Build the exact intended upload artifact outside the repo.

```bash
.venv/bin/python scripts/build_submission.py --output /tmp/orbit_wars_v0_submission.py
```

Confirm the file exists and record size/hash for the submission note.

```bash
.venv/bin/python -c "import hashlib, pathlib; p=pathlib.Path('/tmp/orbit_wars_v0_submission.py'); print(p, p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())"
```

## No-Submit Preflight

Before the live submission cycle, verify the local machine can call Kaggle and
has credentials configured. Do not print credential values.

```bash
command -v kaggle
kaggle --version
kaggle competitions submit --help
```

Credential presence can be checked by confirming `~/.kaggle/kaggle.json` exists
and contains non-empty `username` and `key` fields. Do not commit or display the
file contents.

## Live Submit Command

Use this command only in the later live-submission cycle, after final artifact
freeze and readiness approval.

```bash
kaggle competitions submit -c orbit-wars -f /tmp/orbit_wars_v0_submission.py -m "V0 local preflight passed"
```

If using a venv-installed Kaggle CLI instead of a global executable, replace
`kaggle` with `.venv/bin/kaggle`.

## Cycle 0 Local Status

Cycle 0 verified the artifact can be built and hashed, and local source
references identify `orbit-wars` as the competition slug. The local machine did
not have a callable `kaggle` executable on `PATH`, the project venv did not have
the `kaggle` Python package installed, and `~/.kaggle/kaggle.json` was not
present. Those are blockers for a later live submission cycle until fixed.

No generated submissions, reports, scoreboards, logs, replays, or temporary
artifacts should be committed.
