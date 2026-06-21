# V1 Deterministic Leak Fix Fixtures

This note records the compact replay-derived fixture set for the V1
deterministic leak fix segment. The fixtures are single-observation JSON cases
under `tests/fixtures/v1_replay_leaks/`; they are not full Kaggle replay dumps.

Source submission:

- Competition: `orbit-wars`
- Submission ref: `53894832`
- Submission file: `orbit_wars_v1_submission.py`
- Message: `serious-v1 local readiness passed 4e66048`
- Replay-analysis source:
  `docs/submission_replay_analyses/ashxudev_orbit_wars_v1_submission/`

Cycle 0 is characterization only. It does not change candidate generation,
strategy selection, defense policy, denial policy, capture-hold policy, scoring,
simulator mechanics, budget guards, action conversion, evaluation gates, or
submission behavior.

## Fixture Map

| Fixture | Source episode | Turn | Player | Leak class | Current characterization |
|---|---:|---:|---:|---|---|
| `two_p_production_retention_80999800_t150_p0.json` | `80999800` | `150` | `0` | `owned_production_threat_unanswered` | Emits one reserve-preserving action while owned production is already under collapse pressure. |
| `two_p_production_retention_80979989_t084_p1.json` | `80979989` | `84` | `1` | `owned_production_threat_unanswered` | Has candidates but emits no action because two-player selection rejects all options below score threshold. |
| `two_p_production_retention_80987824_t156_p1.json` | `80987824` | `156` | `1` | `owned_production_threat_unanswered` | Emits one reserve-preserving action in a later pressure-collapse window. |
| `two_p_own_transfer_spam_80991772_t160_p0.json` | `80991772` | `160` | `0` | `own_transfer_spam` | Has candidates but emits no action at a sampled own-transfer/pressure window. |
| `two_p_own_transfer_spam_80986331_t161_p1.json` | `80986331` | `161` | `1` | `own_transfer_spam` | Emits one reserve-preserving action in an own-transfer-heavy loss. |
| `two_p_enemy_denial_absent_80989880_t200_p0.json` | `80989880` | `200` | `0` | `enemy_denial_absent` | Emits one reserve-preserving non-denial action in a high-production ahead state. |
| `four_p_plateau_80984201_t240_p0.json` | `80984201` | `240` | `0` | `four_player_plateau` | Has candidates but emits no action after plateauing at two planets and five production. |
| `four_p_plateau_80981260_t060_p2.json` | `80981260` | `60` | `2` | `four_player_plateau` | Has candidates but no eligible four-player strategy after a tiny opening. |
| `four_p_plateau_80982912_t250_p0.json` | `80982912` | `250` | `0` | `four_player_plateau` | Emits one reserve-preserving action while still failing to convert a long midgame lead. |
| `four_p_thin_capture_recaptured_80979440_t054_p0.json` | `80979440` | `54` | `0` | `thin_capture_recaptured` | Emits one reserve-preserving capture shortly before the high-value target is recaptured. |

## Deferred Fixes

Later cycles should use these fixtures to prove targeted improvements:

- Protect owned production under visible pressure before continuing expansion.
- Replace own-transfer spam with purposeful pooling, defense, or conversion.
- Add enemy-production denial in ahead 2P positions.
- Continue useful 4P midgame action after the opening instead of plateauing.
- Gate or resize 4P captures that are likely to be immediately recaptured.

These fixtures intentionally preserve current behavior so future cycles can show
deterministic before/after movement without relying on live Kaggle feedback.
