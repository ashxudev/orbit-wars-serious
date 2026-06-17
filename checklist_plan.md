# Orbit Wars Serious Build Checklist

This is the canonical planning ledger for the serious Orbit Wars system build.
This thread maintains this file and does not perform implementation work.

## Coordination Threads

- Planner/reviewer thread: `codex://threads/019ece8c-ea4e-7740-bd9b-a21c4639a4f5`
- Implementation thread: `codex://threads/019ece6e-8e2f-7fb3-a345-75579d4c0231`

## Planning Conventions

- High-level work is grouped into segments.
- Cycle numbering restarts inside each segment.
- Example: the next segment starts at `Planner Cycle 0`, not `Cycle 15`.
- Simulator work is closed unless later planner work exposes a missing mechanical rule.
- This plan should track intended work, completion status, blockers, and next-cycle decisions.

## Current Status

- [x] Simulator segment complete for current planner needs.
- [x] Mission generation segment complete.
- [ ] Mission evaluator segment in progress.
- [ ] Opponent-response segment not started.
- [ ] Commitment-policy segment not started.
- [ ] 2p/4p strategy segment not started.
- [ ] Runtime/submission segment not started.

## Segment 1: Simulator

Status: complete.

Purpose: provide a deterministic, engine-faithful mechanical forward model that planner work can consume.

- [x] Cycle 0: initial simulator skeleton.
- [x] Cycle 1: constants/state/schema groundwork.
- [x] Cycle 2: official observation parsing groundwork.
- [x] Cycle 3: geometry primitives.
- [x] Cycle 4: planet motion/projection.
- [x] Cycle 5: fleet motion/projection.
- [x] Cycle 6: launch arrival and collision forecasting.
- [x] Cycle 7: comet parsing and existing-comet motion.
- [x] Cycle 8: collision/removal facts.
- [x] Cycle 9: combat/event summaries.
- [x] Cycle 10: timeline deltas/events.
- [x] Cycle 11: one-tick next-state construction.
- [x] Cycle 12: idle multi-tick rollout.
- [x] Cycle 13: typed launch insertion what-if API.
- [x] Cycle 14: launch insertion plus rollout composition API.
- [x] Official oracle parity tests added and committed separately.
- [x] Simulator cycle docs moved under `docs/simulator_cycles_md/`.

Implemented simulator capabilities:

- [x] official constants and geometry
- [x] parsed state containers
- [x] planet motion helpers
- [x] fleet motion helpers
- [x] existing comet motion helpers
- [x] collision/removal facts
- [x] combat resolution
- [x] one-tick event summaries and state deltas
- [x] one-tick next-state construction
- [x] idle multi-tick rollout
- [x] typed launch insertion
- [x] launch-plus-rollout composition

Known simulator caveats and intentional deferrals:

- [ ] Future new comet spawning from hidden RNG/seed state.
- [ ] Reward and termination modeling.
- [ ] Kaggle action payload parsing.
- [ ] Branch comparison or candidate search.
- [ ] Planner, mission generation, scoring, or strategy.
- [ ] Submission bundling.

## Segment 2: Planner / Mission Generation

Status: complete.

Purpose: turn simulator facts into plausible action candidates without yet adding heavy scoring or strategy.

### Mission Generation Cycle 0: Planner Package Skeleton And Candidate Types

Status: complete and committed.

- [x] Created separate `ow_planner` package.
- [x] Added typed planner candidate concepts.
- [x] Added deterministic empty `generate_candidates(state, config=None)` boundary.
- [x] Added planner candidate tests.
- [x] Kept simulator modules unchanged.
- [x] Commit: `b2ad9e7 Add planner candidate skeleton`.

### Mission Generation Cycle 1: Legal Launch Action Conversion

Status: complete and committed.

- [x] Added planner-layer action adapter.
- [x] Converted typed `LaunchCandidate` / `MissionCandidate` values to simulator `LaunchOrder` values.
- [x] Converted typed candidates to Kaggle-compatible action rows.
- [x] Added strict validation for source ownership, ship count, angle, and cumulative same-source overspend.
- [x] Preserved launch ordering.
- [x] Added planner action tests.
- [x] Kept simulator modules unchanged.
- [x] Commit: `1d7f2be Add planner launch action conversion`.

### Mission Generation Cycle 2: Board Feature Extraction

Status: complete and committed.

- [x] Added `ow_planner/features.py`.
- [x] Exported feature API from `ow_planner/__init__.py`.
- [x] Resolved effective player id from explicit argument, then `state.player_id`.
- [x] Partitioned own, neutral, and enemy planets.
- [x] Partitioned own and enemy fleets.
- [x] Built planet and fleet lookups.
- [x] Computed ship totals for planets and fleets.
- [x] Computed production totals by category and owner.
- [x] Computed deterministic source-target distances using `ow_sim.geometry.distance`.
- [x] Computed nearest neutral target per owned source.
- [x] Computed nearest enemy target per owned source.
- [x] Preserved factual target metadata such as production, ships, owner, distance, and comet/static flags.
- [x] Kept outputs immutable or safely side-effect-free.
- [x] Added focused feature extraction tests.
- [x] Did not generate missions, estimate ships, call simulator rollouts, score, rank, or select actions.
- [x] Kept simulator mechanics unchanged.
- [x] Commit: `09d4c79 Add planner board feature extraction`.

### Mission Generation Cycle 3: Source-Target Pair Enumeration

Status: complete and committed.

- [x] Added deterministic source-target pair enumeration.
- [x] Enumerated owned sources against neutral and enemy targets.
- [x] Preserved factual pair data without scoring or ranking.
- [x] Added planner enumeration tests.
- [x] Kept simulator mechanics unchanged.
- [x] Commit: `b3106af Add planner source target enumeration`.

### Mission Generation Cycle 4: Required Ship Estimation

Status: complete and committed.

- [x] Added first-pass ship estimation for neutral captures and enemy attacks.
- [x] Produced affordable launch candidates when source ships were sufficient.
- [x] Preserved deterministic tuple/value-object style.
- [x] Added planner estimation tests.
- [x] Kept scoring, ranking, and simulator rollouts out of the cycle.
- [x] Commit: `0b62ec4 Add planner ship estimation`.

### Mission Generation Cycle 5: Simulator-Validated Candidate Outcomes

Status: complete and committed.

- [x] Added `ow_planner/outcomes.py`.
- [x] Converted affordable estimated pairs through the planner action conversion boundary.
- [x] Ran candidate launches through `simulate_launch_orders(...)`.
- [x] Returned factual source/target after-rollout outcome reports.
- [x] Represented no-launch and simulation-failure cases without crashing.
- [x] Added planner outcome tests.
- [x] Kept scoring, ranking, comparison, and selection out of the cycle.
- [x] Commit: `4e51e53 Add planner candidate outcome validation`.

### Mission Generation Cycle 6: Mission Generator API And Candidate Limits

Status: complete and committed.

- [x] Replaced placeholder `generate_candidates(...)` with a first real deterministic generator.
- [x] Composed source-target enumeration, ship estimation, and simulator-backed outcome validation.
- [x] Returned validated `MissionCandidate` values for affordable neutral/enemy opportunities.
- [x] Mapped neutral captures to `MissionType.CAPTURE_NEUTRAL`.
- [x] Mapped enemy attacks to `MissionType.ATTACK_ENEMY`.
- [x] Added `CandidateGenerationConfig.max_candidates`.
- [x] Applied candidate limits after validation in deterministic order.
- [x] Added generation tests.
- [x] Kept scoring, ranking, opponent modeling, strategy, runtime behavior, and bundling out of the segment.
- [x] Commit: `6cace97 Add bounded planner candidate generation`.

### Mission Generation Segment Deferrals

- [ ] Own-planet defense/reinforcement candidate generation.
- [ ] Evacuation/doomed-source candidate generation.
- [ ] Coordinated multi-source candidate shape.
- [ ] Late-game liquidation candidate shape.
- [ ] More aggressive deterministic pruning for runtime control.
- [ ] Strategic scoring, ranking, and selection.

## Segment 3: Mission Evaluator

Status: in progress.

Purpose: score candidate missions by comparing future board value with and without the mission.

### Mission Evaluation Cycle 0: Evaluation Types And API Boundary

Status: complete and committed.

- [x] Added planner-layer evaluation contracts.
- [x] Added immutable `MissionEvaluationStatus`, `EvaluationConfig`, `ScoreComponent`, `MissionEvaluationFacts`, and `MissionEvaluation` types.
- [x] Added placeholder `evaluate_candidates(...)` API.
- [x] Wrapped input candidates as `UNEVALUATED` structural records in input order.
- [x] Preserved immutable tuple/value-object style.
- [x] Added focused planner evaluation tests.
- [x] Avoided mission fact extraction, baseline rollout, candidate rollout, scoring, ranking, pruning, and action selection.
- [x] Commit: `7f81926 Add planner evaluation contracts`.

### Mission Evaluation Cycle 1: Candidate Fact Extraction

Status: complete and committed.

- [x] Added deterministic candidate fact extraction for evaluation.
- [x] Kept evaluation structural and factual.
- [x] Avoided scoring, ranking, pruning, and action selection.
- [x] Commit: `178f4b1 Add planner candidate fact extraction`.

### Mission Evaluation Cycle 2: State Lookup Facts

Status: complete and committed.

- [x] Added state lookup facts needed by later evaluation.
- [x] Preserved missing-planet handling as factual data rather than policy.
- [x] Avoided scoring, ranking, pruning, and action selection.
- [x] Commit: `e226657 Add planner state lookup facts`.

### Mission Evaluation Cycle 3: Baseline Future Facts

Status: complete and committed.

- [x] Added idle-baseline future facts for candidate evaluation.
- [x] Established baseline comparison inputs for later cycles.
- [x] Avoided scoring, ranking, pruning, and action selection.
- [x] Commit: `6f6bc34 Add planner baseline future facts`.

### Mission Evaluation Cycle 4: Candidate Future Facts

Status: complete and committed.

- [x] Added mission-future facts for evaluated candidates.
- [x] Captured target/source before-state, idle-baseline, and mission-future fact snapshots.
- [x] Preserved missing planet IDs and mission simulation error facts.
- [x] Avoided scoring, ranking, pruning, and action selection.
- [x] Commit: `ee5deeb Add planner candidate future facts`.

### Mission Evaluation Cycle 5: Mission-Vs-Baseline Delta Facts

Status: complete and committed.

- [x] Added deterministic mission-vs-baseline comparison facts.
- [x] Added planet-level and mission-level future delta dataclasses.
- [x] Compared mission future against idle baseline as the primary mission effect.
- [x] Preserved before-state deltas where useful for source vulnerability.
- [x] Attached delta facts to `MissionEvaluationFacts`.
- [x] Exported delta fact helper(s).
- [x] Handled missing before/baseline/mission facts with safe `None` deltas.
- [x] Preserved mission simulation errors without reinterpretation.
- [x] Avoided scoring, ranking, pruning, opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `79ef5c8 Add planner mission delta facts`.

### Mission Evaluation Cycle 6: Mission Value Facts

Status: complete and committed.

- [x] Added deterministic mission value facts.
- [x] Derived factual value inputs from existing evaluation facts and deltas.
- [x] Kept value extraction separate from scoring weights and selection policy.
- [x] Avoided ranking, pruning, opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `14f5bbc Add planner mission value facts`.

### Mission Evaluation Cycle 7: Mission Scoring Policy

Status: complete and committed.

- [x] Added first-pass mission scoring policy.
- [x] Added scoring configuration and score component handling.
- [x] Kept scoring deterministic and planner-layer only.
- [x] Avoided ranking, pruning, opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `275fe86 Add planner mission scoring policy`.

### Mission Evaluation Cycle 8: Evaluated Scoring Pipeline

Status: complete and committed.

- [x] Added pipeline composition for evaluating and scoring candidates.
- [x] Integrated evaluation facts with scoring components.
- [x] Preserved input order and immutable output behavior.
- [x] Avoided ranking, pruning, selection, opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `fe39552 Add planner evaluated scoring pipeline`.

### Mission Evaluation Cycle 9: Mission Timing Facts

Status: complete and committed.

- [x] Added deterministic mission timing facts.
- [x] Exposed timing facts for later scoring without recomputing geometry in scoring.
- [x] Kept timing factual and separate from scoring policy.
- [x] Avoided ranking, pruning, selection, opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `664cbc9 Add planner mission timing facts`.

### Mission Evaluation Cycle 10: Timing-Aware Scoring Components

Status: in progress in implementation thread.

- [ ] Add first-pass scoring support for `MissionTimingFacts`.
- [ ] Add timing scoring helper, likely `score_mission_timing_facts(...)`.
- [ ] Add timing scoring config fields such as `arrival_tick_weight` and `incomplete_timing_penalty`.
- [ ] Keep `score_mission_value_facts(...)` backward-compatible and value-only.
- [ ] Update `score_evaluations(...)` to append timing components after value components.
- [ ] Use deterministic timing summary, preferably `max_arrival_ticks`, for launch timing.
- [ ] Avoid timing penalty for complete no-launch timing with no arrival ticks.
- [ ] Add explicit incomplete timing penalty for otherwise valid evaluations.
- [ ] Avoid ranking, sorting, pruning, selection, opponent modeling, strategy, runtime, and bundling.

### Later Mission Evaluation Cycles

- [ ] Score production gained.
- [ ] Score production denied.
- [ ] Score ships spent.
- [ ] Score capture survival.
- [ ] Score opportunity cost of draining source.
- [ ] Define concrete mission outcome scoring data model beyond structural contracts.
- [ ] Add tests for obviously good/bad candidate ordering.
- [ ] Document scoring assumptions and known blind spots.

## Segment 4: Opponent Response Model

Status: not started.

Purpose: estimate punishment, defense, races, and third-party effects.

- [ ] Detect whether opponent can reinforce target before arrival.
- [ ] Detect neutral-planet race or tie risk.
- [ ] Detect counterattack risk on emptied source.
- [ ] Detect whether responding sources are pinned or threatened.
- [ ] Add four-player third-party benefit checks.
- [ ] Classify candidates as undefendable, defendable-profitable, donation, race-risk, or source-drain bait.
- [ ] Add focused response-model tests.

## Segment 5: Commitment Policy

Status: not started.

Purpose: choose ship sizing as an evaluated decision rather than a fixed rule.

- [ ] Generate minimum-capture sizing.
- [ ] Generate capture-and-hold sizing.
- [ ] Generate reserve-preserving sizing.
- [ ] Generate full-source attack sizing.
- [ ] Generate coordinated multi-source sizing.
- [ ] Include no-attack as an explicit option.
- [ ] Add tests showing full-send is available when profitable but not globally forced.

## Segment 6: 2p / 4p Strategy Modes

Status: not started.

Purpose: separate direct duel optimization from rank-aware free-for-all play.

### Two-Player Mode

- [ ] Maximize advantage over single opponent.
- [ ] Prioritize production denial.
- [ ] Favor direct tactical exchanges when profitable.
- [ ] Add 2p fixture/scenario tests.

### Four-Player Mode

- [ ] Maximize final rank, not just raw board value.
- [ ] Avoid becoming exposed leader too early.
- [ ] Attack current leader when profitable.
- [ ] Preserve survival paths while behind.
- [ ] Exploit late rank-swing opportunities.
- [ ] Add 4p fixture/scenario tests.

## Segment 7: Runtime / Submission

Status: not started.

Purpose: convert planner components into a reliable Kaggle agent with strict runtime control.

- [ ] Build per-turn runtime budget.
- [ ] Add cheap candidate prefilter.
- [ ] Fully evaluate only top candidates.
- [ ] Greedily commit compatible missions.
- [ ] Add low-time fallback behavior.
- [ ] Add deterministic smoke-run script for an agent turn.
- [ ] Add local evaluation harness.
- [ ] Add submission bundler only after a real agent imports `ow_sim`.

### Packaging / Bundling Later

- [ ] Create `scripts/build_submission.py`.
- [ ] Input: agent entrypoint, likely `agents/submission_agent.py`.
- [ ] Output: Kaggle-ready single-file `submission.py`.
- [ ] Inline only required runtime modules.
- [ ] Exclude tests, docs, oracle tooling, and development-only scripts.
- [ ] Rewrite/remove package imports cleanly.
- [ ] Run syntax/import smoke check on generated file.
- [ ] Run behavior parity check between package version and bundled version on a fixture.

## Open Questions

- [x] Planner package boundary chosen: `ow_planner`.
- [x] Initial candidate types implemented for neutral captures and enemy attacks.
- [ ] What horizon should candidate simulation use initially?
- [ ] What is the first local benchmark/evaluation standard before Kaggle submission?

## Update Log

- 2026-06-17: Created canonical checklist plan. Recorded simulator complete, next segment as Planner Cycle 0, and segment-local cycle numbering.
- 2026-06-17: Updated mission-generation status from thread poll. Mission Generation Cycle 0 and Cycle 1 are complete and committed; Cycle 2 board feature extraction is in progress.
- 2026-06-17: Poll confirmed `MISSION_GENERATION_SEGMENT_COMPLETE`. Marked Mission Generation Cycles 0-6 complete and set Mission Evaluation as the next segment.
- 2026-06-17: Poll found Mission Evaluation Cycle 0 complete and committed as `7f81926 Add planner evaluation contracts`.
- 2026-06-17: Poll found Mission Evaluation Cycles 1-4 complete and committed. Mission Evaluation Cycle 5 delta facts is in progress.
- 2026-06-17: Poll found Mission Evaluation Cycles 5-9 complete and committed. Mission Evaluation Cycle 10 timing-aware scoring is in progress.
