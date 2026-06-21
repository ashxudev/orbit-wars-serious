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
| `two_p_production_retention_80979989_t084_p1.json` | `80979989` | `84` | `1` | `owned_production_threat_unanswered` | Cycle 2 emits one reserve-preserving retention action under owned-production pressure. |
| `two_p_production_retention_80987824_t156_p1.json` | `80987824` | `156` | `1` | `owned_production_threat_unanswered` | Emits one reserve-preserving action in a later pressure-collapse window. |
| `two_p_own_transfer_spam_80991772_t160_p0.json` | `80991772` | `160` | `0` | `own_transfer_spam` | Cycle 2 emits one reserve-preserving retention action in an owned-production pressure window. |
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

## Cycle 1 Owned Threat Facts

Cycle 1 adds `ow_planner.owned_threats` as a deterministic fact surface for
owned production under visible replay pressure. It reports per-owned-planet
incoming hostile ships, incoming friendly ships, earliest hostile/friendly ETA,
projected balance, likely-flip and at-risk labels, production under pressure,
and whether outgoing friendly fleets have drained a threatened source.

The V1 production-retention fixtures now assert that this surface recognizes
their owned-production pressure windows. The cycle remains observability only:
it does not change candidate generation, scoring, strategy selection, runtime
action conversion, simulator mechanics, evaluation gates, or submission
behavior.

## Cycle 2 Owned Production Retention Selection

Cycle 2 threads the owned-production threat report into the two-player selector
from the runtime planner pipeline. When visible owned-production pressure is
present, the selector admits conservative reserve-preserving options through the
score floor and prefers validated owned-retention missions
(`REINFORCE` / `DEFEND_OWN`) over ordinary expansion or attack choices.

This specifically changes the `80979989` production-retention fixture from a
score-floor no-action into a reserve-preserving retention launch. The
`80991772` own-transfer fixture also now emits a reserve-preserving retention
action because it contains the same owned-production pressure signal. No
four-player behavior, opening fallback behavior, simulator mechanics, action
conversion, evaluation gates, or submission behavior is changed.

## Cycle 3 Own-Transfer Intent Facts

Cycle 3 adds `ow_planner.own_transfers` as a deterministic fact surface for
existing in-flight own-to-own transfer fleets. It infers owned targets from the
fleet ray, records source/target production and ship context, ETA/distance, and
labels whether a transfer looks purposeful or potentially spammy.

The `80991772` and `80986331` own-transfer fixtures now assert that this fact
surface identifies potentially spammy own-to-own movement. The repeated
`80986331` stream is also labeled as repeated own-transfer activity. This cycle
does not change candidate generation, scoring, strategy selection, runtime
action conversion, simulator mechanics, evaluation gates, or submission
behavior.

## Cycle 4 Own-Transfer Spam Reduction Selection

Cycle 4 threads `own_transfer_intent_facts` into the two-player selector beside
the owned-production threat report. When potentially spammy own-transfer
activity is visible and owned production is not under pressure, the selector now
prefers validated productive non-transfer alternatives over new
owned-retention-style actions.

The direct selector tests cover this policy boundary. The live `80991772`
fixture still selects reserve-preserving retention because owned-production
pressure is active. The live `80986331` fixture remains behaviorally unchanged
because the current bundle set exposes only reinforce-style candidates and no
validated productive non-transfer alternative to prefer. This cycle does not
change candidate generation, scoring, simulator mechanics, action conversion,
evaluation gates, or submission behavior.

## Cycle 5 Enemy Production Denial Facts

Cycle 5 adds `ow_planner.enemy_denial` as a deterministic fact surface for
ahead-state opponent production denial opportunities. It reports opponent-owned
production targets, nearest owned source, source capacity, distance/ETA
estimates, production and ship balance, plausible-denial labels, and
high-value-denial labels.

The `80989880` enemy-denial fixture now asserts that this surface identifies
multiple plausible opponent production targets, including high-value denial
opportunities. This cycle is observability only: it does not change candidate
generation, scoring, strategy selection, runtime action conversion, simulator
mechanics, evaluation gates, or submission behavior.

## Cycle 6 Enemy Production Denial Selection

Cycle 6 threads the enemy-denial opportunity report into the two-player
selector. When no owned-production pressure or response-pressure safety rule is
active, the selector now prefers validated `ATTACK_ENEMY` bundles that target
high-value opponent production denial opportunities identified by
`ow_planner.enemy_denial`.

Owned-production retention remains higher priority. The live `80989880`
fixture still selects the existing reserve-preserving retention action because
its state contains a likely-flip owned-production threat. Direct selector tests
cover the new no-pressure denial preference, the owned-pressure override, and
the interaction with own-transfer spam suppression. This cycle does not change
candidate generation, scoring, simulator mechanics, action conversion,
evaluation gates, or submission behavior.

## Cycle 7 Four-Player Plateau Opportunity Facts

Cycle 7 adds `ow_planner.four_player_plateau` as a deterministic fact surface
for stalled four-player replay windows. It reports current owned planet,
production, and ship counts, active opponents, neutral/enemy production
opportunity counts, nearest expansion/denial targets, and optional runtime
metadata such as candidate count, action count, and no-action reason.

The three V1 `four_player_plateau` fixtures now assert plateau facts. The two
no-action fixtures are labeled as candidate-backed no-action plateau windows,
while the action-emitting `80982912` fixture is labeled separately as an
action-emitting plateau. This cycle is observability only: it does not change
four-player selection, candidate generation, scoring, simulator mechanics,
action conversion, evaluation gates, or submission behavior.
