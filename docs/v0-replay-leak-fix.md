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
