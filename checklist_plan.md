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
- [x] Mission evaluator segment complete.
- [x] Opponent-response segment complete.
- [x] Commitment-policy segment complete.
- [x] 2p/4p strategy segment complete.
- [x] Runtime/submission segment complete.
- [x] Evaluation harness / match testing segment complete for local pre-submission readiness.
- [ ] Distributed evaluation / Daytona sharding segment in progress.

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

Status: complete.

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

Status: complete and committed.

- [x] Added first-pass scoring support for `MissionTimingFacts`.
- [x] Added timing scoring helper.
- [x] Added timing scoring config fields.
- [x] Kept `score_mission_value_facts(...)` backward-compatible and value-only.
- [x] Updated `score_evaluations(...)` to append timing components after value components.
- [x] Used deterministic timing facts rather than recomputing geometry in scoring.
- [x] Avoided ranking, sorting, pruning, selection, opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `67eb079 Add planner timing-aware scoring`.

### Mission Evaluation Cycle 11: Capture Outcome Scoring

Status: complete and committed.

- [x] Added first-pass capture/retain/loss outcome scoring.
- [x] Kept outcome scoring isolated from value and timing scoring.
- [x] Composed outcome components into evaluated scoring.
- [x] Avoided ranking, sorting, pruning, selection, opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `d2ebcf1 Add planner capture outcome scoring`.

### Mission Evaluation Cycle 12: Source-Drain Opportunity-Cost Scoring

Status: complete and committed.

- [x] Added source-drain opportunity-cost scoring.
- [x] Added source drain fraction and depleted source count components.
- [x] Added incomplete source opportunity penalty.
- [x] Composed source opportunity components after value, timing, and outcome components.
- [x] Kept deeper source danger and enemy punishment deferred to Opponent Response.
- [x] Avoided ranking, sorting, pruning, selection, opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `3c3e792 Add planner source opportunity scoring`.

### Mission Evaluation Cycle 13: Scoring Sanity Scenarios And Assumptions Documentation

Status: complete and committed.

- [x] Added obvious good/bad scoring scenario tests.
- [x] Added one end-to-end `evaluate_and_score_candidates(...)` sanity comparison.
- [x] Documented current score component families.
- [x] Documented assumptions and blind spots.
- [x] Kept tests as score comparisons without adding ranking or selection APIs.
- [x] Avoided opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `08cb1d2 Add planner scoring sanity docs`.

### Mission Evaluation Segment Deferrals

- [ ] Opponent reinforcement modeling.
- [ ] Neutral race/tie modeling.
- [ ] Enemy counterattack/source-threat modeling.
- [ ] Four-player rank/swing modeling.
- [ ] Runtime candidate pruning/selection policy.
- [ ] Autoresearch/tuning loop for first-pass weights.

## Segment 4: Opponent Response Model

Status: complete.

Purpose: estimate punishment, defense, races, and third-party effects.

### Opponent Response Model Cycle 0: API Boundary

Status: complete and committed.

- [x] Defined the stable opponent-response model package/API boundary.
- [x] Kept the first cycle structural and deterministic.
- [x] Avoided strategic response scoring.
- [x] Preserved separation from mission evaluation scoring, commitment policy, 2p/4p strategy, runtime, and bundling.
- [x] Commit: `e54d108 Add planner response model boundary`.

### Opponent Response Model Cycle 1: Target Reinforcement Response Facts

Status: complete and committed.

- [x] Added deterministic target reinforcement response facts.
- [x] Exposed whether opponents can reinforce the target before/around mission arrival.
- [x] Kept facts conservative and non-scoring.
- [x] Avoided ranking, pruning, selection, strategy, runtime, and bundling.
- [x] Commit: `ea8c092 Add planner reinforcement response facts`.

### Opponent Response Model Cycle 2: Target Race Response Facts

Status: complete and committed.

- [x] Added deterministic target race response facts.
- [x] Exposed neutral/enemy race-risk facts without deciding mission quality.
- [x] Kept response facts separate from scoring and policy.
- [x] Avoided ranking, pruning, selection, strategy, runtime, and bundling.
- [x] Commit: `0898870 Add planner target race response facts`.

### Opponent Response Model Cycle 3: Source Counterattack Response Facts

Status: complete and committed.

- [x] Added deterministic source counterattack response facts.
- [x] Exposed whether drained sources are vulnerable to enemy counterattack facts.
- [x] Kept deeper source danger as factual response data, not strategy.
- [x] Avoided ranking, pruning, selection, strategy, runtime, and bundling.
- [x] Commit: `7b5900b Add planner source counterattack response facts`.

### Opponent Response Model Cycle 4: FFA Third-Party Benefit Facts

Status: complete and committed.

- [x] Added deterministic FFA third-party benefit facts.
- [x] Added `ThirdPartyOwnerFacts` and `ThirdPartyBenefitFacts`.
- [x] Attached third-party facts to `MissionResponseFacts`.
- [x] Exposed `third_party_benefit_facts(...)`.
- [x] Summarized unaffected non-player owners in four-player/free-for-all settings.
- [x] Treated two-player/no-third-party cases conservatively.
- [x] Kept the FFA model factual and conservative.
- [x] Avoided response scoring, ranking, pruning, selection, strategy, runtime, and bundling.
- [x] Commit: `6ef77f4 Add planner third-party response facts`.

### Opponent Response Model Cycle 5: Response Summary Labels

Status: complete and committed.

- [x] Added deterministic response summary labels.
- [x] Added `ResponseSummaryFacts`.
- [x] Populated `MissionResponseFacts.response_labels` from summary labels.
- [x] Kept labels factual and stable.
- [x] Avoided response scoring, ranking, pruning, selection, strategy, runtime, and bundling.
- [x] Commit: `2ad4648 Add planner response summary labels`.

### Opponent Response Model Cycle 6: Responding Source Pressure Facts

Status: complete and committed.

- [x] Added deterministic pinned/threatened responding-source facts.
- [x] Added `RespondingSourcePressureFacts` and `ResponseSourcePressureFacts`.
- [x] Attached source pressure facts to `MissionResponseFacts`.
- [x] Kept source pressure factual and separate from classification.
- [x] Avoided response scoring, ranking, pruning, selection, strategy, runtime, and bundling.
- [x] Commit: `603569f Add planner response source pressure facts`.

### Opponent Response Model Cycle 7: Response Classification Labels

Status: complete and committed.

- [x] Added isolated first-pass response classification labels.
- [x] Added `ResponseClassificationFacts` and `classify_response_facts(...)`.
- [x] Kept classification separate from deterministic response fact extraction.
- [x] Covered undefendable, defendable-profitable, donation, race-risk, and source-drain bait labels.
- [x] Avoided ranking, pruning, selection, commitment policy, strategy, runtime, and bundling.
- [x] Commit: `bfa50c3 Add planner response classification labels`.

### Opponent Response Model Segment Deferrals

- [ ] Tune first-pass classification rules through evaluation/autoresearch.
- [ ] Integrate response classifications into downstream commitment and strategy policy.

## Segment 5: Commitment Policy

Status: complete.

Purpose: choose ship sizing as an evaluated decision rather than a fixed rule.

### Commitment Policy Cycle 0: API Boundary

Status: complete and committed.

- [x] Added planner commitment-policy API boundary.
- [x] Added commitment option/status/config/container types.
- [x] Added deterministic `commitment_options_for_candidates(...)` structural wrapper.
- [x] Kept the boundary free of sizing, evaluation, scoring, ranking, selection, runtime, and bundling behavior.
- [x] Commit: `95527e6 Add planner commitment policy boundary`.

### Commitment Policy Cycle 1: Explicit No-Attack Option

Status: complete and committed.

- [x] Added explicit no-attack commitment option.
- [x] Attached one no-attack option per candidate when option limits allow.
- [x] Preserved candidate order and option order.
- [x] Kept ship-sending options deferred.
- [x] Avoided sizing, evaluation, scoring, ranking, selection, runtime, and bundling behavior.
- [x] Commit: `7d749c9 Add planner no-attack commitment option`.

### Commitment Policy Cycle 2: Minimum-Capture Option

Status: complete and committed.

- [x] Added minimum-capture commitment option.
- [x] Mirrored existing candidate launches without recomputing ship requirements.
- [x] Summed committed ships and preserved launch/source ordering.
- [x] Added no-launch rejection behavior.
- [x] Kept hold sizing, reserve sizing, evaluation, scoring, ranking, selection, runtime, and bundling deferred.
- [x] Commit: `1451df4 Add planner minimum-capture commitment option`.

### Commitment Policy Cycle 3: Capture-And-Hold Option

Status: complete and committed.

- [x] Added first-pass capture-and-hold commitment option.
- [x] Added configurable hold buffer allocation over existing candidate launches.
- [x] Preserved source affordability, launch angles, player IDs, source IDs, and target IDs.
- [x] Added deterministic rejection notes for no launches, missing sources, non-owned sources, and insufficient hold buffer.
- [x] Kept reserve-preserving, full-source, coordinated multi-source, evaluation, scoring, ranking, selection, runtime, and bundling deferred.
- [x] Commit: `1557b1a Add planner capture-and-hold commitment option`.

### Commitment Policy Cycle 4: Reserve-Preserving Option

Status: complete and committed.

- [x] Added `reserve_ships_per_source` config validation.
- [x] Added exported `reserve_preserving_commitment_option(...)`.
- [x] Integrated reserve-preserving as option 4 after no-attack, minimum-capture, and capture-and-hold.
- [x] Covered repeated same-source reserve accounting and deterministic rejection notes.
- [x] Commit: `a484c9d Add planner reserve-preserving commitment option`.

### Commitment Policy Cycle 5: Full-Source Commitment Option

Status: complete and committed.

- [x] Added full-source commitment option.
- [x] Made aggressive full-source sending available when structurally valid.
- [x] Preserved conservative options alongside full-source.
- [x] Kept profitability decisions, ranking, and selection deferred.
- [x] Commit: `4979c2a Add planner full-source commitment option`.

### Commitment Policy Cycle 6: Coordinated Multi-Source Commitment Option

Status: complete and committed.

- [x] Added coordinated multi-source commitment option.
- [x] Kept coordinated sending as an available option rather than a selected policy.
- [x] Preserved deterministic option ordering and limit behavior.
- [x] Avoided scoring, response modeling, ranking, selection, runtime, and bundling.
- [x] Commit: `2daa0d0 Add planner coordinated multi-source commitment option`.

### Commitment Policy Cycle 7: Commitment Option Availability Sanity Tests

Status: complete and committed.

- [x] Added final sanity coverage proving full-source can be available when valid.
- [x] Proved full-source is not globally forced because conservative alternatives remain available.
- [x] Proved option limits can exclude full-source below its slot.
- [x] Kept the cycle test-focused and free of selection/ranking behavior.
- [x] Commit: `ec2df8b Add planner commitment option availability sanity tests`.

### Commitment Policy Segment Deferrals

- [ ] Tune commitment option generation and sizing through evaluation/autoresearch.
- [ ] Add a later selector for choosing among generated options.
- [ ] Integrate commitment choices into strategy and runtime policy.

## Segment 6: 2p / 4p Strategy Modes

Status: complete.

Purpose: separate direct duel optimization from rank-aware free-for-all play.

### Strategy Modes Cycle 0: Strategy Mode Boundary

Status: complete and committed.

- [x] Added `StrategyMode` enum with `TWO_PLAYER`, `FOUR_PLAYER`, and `UNKNOWN`.
- [x] Added immutable `StrategyModeFacts`.
- [x] Added `strategy_mode_facts(...)` and `detect_strategy_mode(...)`.
- [x] Counted active players from non-neutral planet/fleet owners plus current player id.
- [x] Kept this cycle as mode detection only, with no strategy selection.
- [x] Commit: `78fe13d Add planner strategy mode boundary`.

### Strategy Modes Cycle 1: Planner Decision Bundle Boundary

Status: complete and committed.

- [x] Added immutable `PlannerDecisionBundle`.
- [x] Added `planner_decision_bundles(...)` structural join helper.
- [x] Joined candidates, evaluations, response evaluations, commitment options, and shared strategy mode facts by candidate identity.
- [x] Preserved candidate order and deterministic missing-artifact notes.
- [x] Avoided strategy selection, ranking, pruning, and simulator/runtime calls.
- [x] Commit: `c2b3237 Add planner decision bundle boundary`.

### Strategy Modes Cycle 2: Strategy Selection Result API

Status: complete and committed.

- [x] Added strategy selection result contracts.
- [x] Added selected, no-action, and rejected result helpers.
- [x] Kept result construction structural and policy-free.
- [x] Avoided 2p/4p facts, selection heuristics, ranking, pruning, simulator calls, runtime, and bundling.
- [x] Commit: `a6eecdf Add planner strategy selection result API`.

### Strategy Modes Cycle 3: Two-Player Direct Advantage Facts

Status: complete and committed.

- [x] Added `TwoPlayerAdvantageFacts`.
- [x] Added `two_player_advantage_facts(...)` and batch helper.
- [x] Extracted deterministic 2p facts from existing decision bundles, evaluation facts, scores, and response labels.
- [x] Preserved bundle identity and input order.
- [x] Kept this cycle fact-only, with no selection policy.
- [x] Commit: `dd31ee6 Add planner two-player advantage facts`.

### Strategy Modes Cycle 4: First-Pass Two-Player Direct-Advantage Selector

Status: complete and committed.

- [x] Added `TwoPlayerSelectionConfig`.
- [x] Added `select_two_player_direct_advantage(...)`.
- [x] Selected from existing planner decision bundles and existing validated commitment options.
- [x] Used deterministic lexicographic 2p ranking with input order as final tie-breaker.
- [x] Returned selected, no-action, or rejected `StrategySelectionResult` values.
- [x] Avoided 4p selection, new scoring components, generation/evaluation/response/commitment recomputation, simulator calls, runtime, and bundling.
- [x] Commit: `183a3d2 Add planner two-player direct selector`.

### Strategy Modes Cycle 5: Four-Player Board Rank and Survival Facts

Status: complete and committed.

- [x] Added `FourPlayerStandingFacts`.
- [x] Added `FourPlayerBoardFacts`.
- [x] Added `four_player_board_facts(...)`.
- [x] Computed active-player standings, production ranks, total-ship ranks, leader ids, deficits, and survival-pressure context.
- [x] Kept this cycle factual only, with no four-player mission selection or commitment choice.
- [x] Commit: `c65731b Add planner four-player board facts`.

### Strategy Modes Cycle 6: Four-Player Mission and Target Facts

Status: complete and committed.

- [x] Added `FourPlayerMissionFacts`.
- [x] Added `four_player_mission_facts(...)` and batch helper.
- [x] Extracted deterministic 4p target/mission facts from existing bundles, evaluation facts, response summaries, and Cycle 5 board standings.
- [x] Covered leader-target capture facts, leader production denied, net ship delta, third-party benefit, and source-counterattack risk labels.
- [x] Kept this cycle fact-only, with no four-player selection policy.
- [x] Commit: `a8d1423 Add planner four-player mission facts`.

### Strategy Modes Cycle 7: First-Pass Four-Player Selector

Status: complete and committed.

- [x] Added `FourPlayerSelectionConfig`.
- [x] Added `select_four_player_strategy(...)`.
- [x] Selected from existing planner decision bundles and existing validated commitment options.
- [x] Used Cycle 5 board facts and Cycle 6 mission facts for deterministic 4p ranking and exclusion behavior.
- [x] Covered production-leader targets, total-ship-leader fallback, leader production denied, total-score ranking, risk/third-party exclusions, thresholds, and commitment preference order.
- [x] Avoided two-player changes, final dispatch, action conversion, runtime, and recomputing generation/evaluation/response/commitment artifacts.
- [x] Commit: `ca43b35 Add planner four-player selector`.

### Strategy Modes Cycle 8: Unified Strategy Dispatch Boundary

Status: complete and committed.

- [x] Added `StrategyDispatchConfig`.
- [x] Added `select_strategy_for_mode(...)`.
- [x] Routed two-player mode to the existing 2p selector.
- [x] Routed four-player mode to the existing 4p selector.
- [x] Passed through exact configs, bundles, and four-player board facts without reinterpretation or recomputation.
- [x] Returned deterministic rejected results for missing or unknown mode facts.
- [x] Avoided runtime/submission behavior, action conversion, generation, evaluation, scoring, response modeling, and commitment creation.
- [x] Commit: `bdc8934 Add planner strategy dispatch boundary`.

### Strategy Modes Cycle 9: Deterministic End-to-End Strategy Fixtures

Status: complete and committed.

- [x] Added fixture-level integration tests for the public strategy dispatch entrypoint.
- [x] Exercised real 2p and 4p selector behavior without mocking selector internals.
- [x] Covered 2p selected/no-action behavior, 4p leader-target selection, config pass-through, and missing/unknown mode rejection.
- [x] Asserted selected bundle identity and selected commitment option identity.
- [x] Kept this cycle test-only with no production code changes.
- [x] Commit: `58e8fe5 Add planner strategy mode fixture tests`.

### Strategy Modes Segment Completion

- [x] Planner/reviewer confirmed `STRATEGY_MODES_SEGMENT_COMPLETE` after Cycle 9.
- [x] Next high-level segment: Runtime / Submission.

### Two-Player Mode Deferrals

- [ ] Maximize advantage over single opponent.
- [ ] Prioritize production denial.
- [ ] Favor direct tactical exchanges when profitable.
- [ ] Add 2p fixture/scenario tests.

### Four-Player Mode Deferrals

- [ ] Maximize final rank, not just raw board value.
- [ ] Avoid becoming exposed leader too early.
- [ ] Attack current leader when profitable.
- [ ] Preserve survival paths while behind.
- [ ] Exploit late rank-swing opportunities.
- [ ] Add 4p fixture/scenario tests.

## Segment 7: Runtime / Submission

Status: complete.

Purpose: convert planner components into a reliable Kaggle agent with strict runtime control.

### Runtime / Submission Cycle 0: Runtime Agent Entrypoint

Status: complete and committed.

- [x] Added initial `agents` package boundary.
- [x] Added `agents/orbit_wars_agent.py` with safe no-action `agent(...)` entrypoint.
- [x] Added runtime entrypoint tests.
- [x] Kept this cycle as an entrypoint only, with no observation parsing, planner wiring, action conversion, timing budget, or bundling.
- [x] Commit: `dad92fd Add runtime agent entrypoint`.

### Runtime / Submission Cycle 1: Observation-To-State Adapter

Status: complete and committed.

- [x] Added `agents/runtime_state.py`.
- [x] Added `observation_to_game_state(...)` as a thin adapter over `GameState.from_obs(...)`.
- [x] Added representative 2p, 4p, and fleet-observation parser tests.
- [x] Preserved parser errors and kept `agent(...)` as no-action.
- [x] Avoided planner, selector, action conversion, fallback policy, timing budget, and bundling behavior.
- [x] Commit: `ebe0969 Add runtime observation adapter`.

### Runtime / Submission Cycle 2: Planner Pipeline Composition Boundary

Status: complete and committed.

- [x] Added `RuntimePlannerConfig`.
- [x] Added `RuntimePlannerResult`.
- [x] Added `run_planner_pipeline(...)` from parsed `GameState` through strategy selection.
- [x] Returned candidates, evaluations, responses, commitments, mode facts, optional 4p board facts, bundles, and selection.
- [x] Kept action conversion and `agent(...)` wiring deferred.
- [x] Commit: `9226a36 Add runtime planner pipeline`.

### Runtime / Submission Cycle 3: Selected Commitment To Kaggle Actions

Status: complete and committed.

- [x] Added `agents/runtime_actions.py`.
- [x] Added `selected_commitment_to_actions(...)`.
- [x] Added `planner_result_to_actions(...)`.
- [x] Converted selected validated commitment-option launches into Kaggle action rows.
- [x] Returned fresh empty lists for non-selected, invalid, no-attack, or empty selections.
- [x] Kept fallback handling and `agent(...)` wiring deferred.
- [x] Commit: `32e881d Add runtime action conversion`.

### Runtime / Submission Cycle 4: Safe Turn Orchestration And Fallback Policy

Status: complete and committed.

- [x] Added `RuntimeTurnStatus`.
- [x] Added `RuntimeTurnConfig`.
- [x] Added `RuntimeTurnResult`.
- [x] Added `run_runtime_turn(...)` around observation parsing, planner pipeline execution, and action conversion.
- [x] Added `safe_actions_for_observation(...)`.
- [x] Wired `agent(...)` through the safe turn boundary.
- [x] Caught parse, planner, and action-conversion failures into deterministic no-action fallback results.
- [x] Commit: `e8f760d Add runtime safe turn orchestration`.

### Runtime / Submission Cycle 5: Runtime Turn Budget Guards

Status: complete and committed.

- [x] Added deterministic budget guard primitives.
- [x] Added stage-start budget checks around expensive runtime turn stages.
- [x] Preserved safe no-action fallback behavior when budget is exhausted.
- [x] Kept tests deterministic without real-time sleeps or global mutable timing state.
- [x] Commit: `034d780 Add runtime turn budget guards`.

### Runtime / Submission Cycle 6: Runtime Default Config Wiring

Status: complete and committed.

- [x] Added runtime config/defaults boundary.
- [x] Derived `RuntimeTurnConfig` from Kaggle observation/configuration inputs.
- [x] Wired default budget guard config into `agent(...)`.
- [x] Used `remainingOverageTime` conservatively when numeric and ignored missing/non-numeric values safely.
- [x] Commit: `88fa2d6 Add runtime default config wiring`.

### Runtime / Submission Cycle 7: Deterministic Single-File Submission Bundler

Status: complete and committed.

- [x] Added `scripts/build_submission.py`.
- [x] Added deterministic single-file bundle generation for `ow_sim`, `ow_planner`, and `agents`.
- [x] Exposed top-level `agent` in the generated submission file.
- [x] Added bundler tests for deterministic output, module inclusion, CLI build, and import/run outside the repo root.
- [x] Verified generated `/tmp/orbit_wars_submission.py` imported and returned `[]` on a fixture.
- [x] Commit: `0949f95 Add submission bundler`.

### Runtime / Submission Segment Completion

- [x] Planner/reviewer confirmed `RUNTIME_SUBMISSION_SEGMENT_COMPLETE` after Cycle 7.
- [x] Modular agent is Kaggle-callable, safely orchestrated, budget-guarded, and bundleable.
- [x] Remaining caveat: this is structural submission readiness, not competitive-strength validation.
- [x] Next high-level segment: Evaluation Harness / Match Testing.

## Segment 8: Evaluation Harness / Match Testing

Status: complete for local pre-submission readiness.

Purpose: evaluate the bundled and modular agents in local official Kaggle Orbit Wars environments before spending scarce live submissions.

Important caveat:

- [x] Use local `kaggle_environments.make(...)` match execution as the evaluation authority.
- [x] Do not submit to live Kaggle as part of this segment.
- [x] Treat live submissions as a later, explicitly approved workflow because only the latest two daily submissions are live-evaluated.

### Evaluation Harness Cycle 0: Evaluation Result Contracts

Status: complete and committed.

- [x] Added typed result/config structures for agent specs, opponent specs, match config, match result, turn/error status, and summary metric placeholders.
- [x] Added validation for malformed opponent entries during deserialization.
- [x] Commit: `a7d6399 Add evaluation harness contracts`.

### Evaluation Harness Cycle 1: Single Match Smoke Runner

Status: complete and committed.

- [x] Added `run_official_match(...)`.
- [x] Ran one local official-environment Orbit Wars match from a `MatchConfig`.
- [x] Added private no-op built-in baseline support for smoke opponents.
- [x] Kept `kaggle_environments` import lazy and avoided artifact writing.
- [x] Commit: `c0f0385 Add official evaluation smoke runner`.

### Evaluation Harness Cycle 2: Agent Loading Modes

Status: complete and committed.

- [x] Added reusable `load_agent_callable(...)`.
- [x] Supported `MODULAR_AGENT`, `PYTHON_FILE`, `SUBMISSION_FILE`, and `BUILTIN_BASELINE`.
- [x] Refactored `run_official_match(...)` to use the shared loader for candidates and opponents.
- [x] Proved file agents with the same filename in different directories do not collide.
- [x] Proved generated single-file submission agents can run in local official matches.
- [x] Commit: `0de77fa Add evaluation agent loading modes`.

### Evaluation Harness Cycle 3: Deterministic Baseline Opponents

Status: complete and committed.

- [x] Added controlled built-in baseline opponent specs.
- [x] Added no-op baseline support.
- [x] Added deterministic baseline behavior suitable for local official smoke matches.
- [x] Kept richer opponent families and batch comparison deferred.
- [x] Commit: `1495471 Add evaluation built-in baselines`.

### Evaluation Harness Cycle 4: Replay And Artifact Capture

Status: complete and committed.

- [x] Added `EvaluationArtifactConfig`.
- [x] Added deterministic replay artifact writing.
- [x] Added deterministic match-result artifact writing.
- [x] Wired optional artifact capture into `run_official_match(...)`.
- [x] Preserved no-artifact behavior by default.
- [x] Commit: `d5bda21 Add evaluation artifact capture`.

### Evaluation Harness Cycle 5: Match Metrics Extraction

Status: complete and committed.

- [x] Added `extract_match_metrics(...)`.
- [x] Extended `MatchMetrics` with final production, invalid-action count, and timeout count.
- [x] Extracted final rank, final score, survival turns, final planets, final ships, final production, no-action count, error count, invalid-action count, and timeout count where observable.
- [x] Wired `run_official_match(...)` to attach metrics from safe replay payloads before artifact writing.
- [x] Preserved lazy `kaggle_environments` import.
- [x] Commit: `ef16d96 Add evaluation metrics extraction`.

### Evaluation Harness Cycle 6: Batch Evaluation Runner

Status: complete and committed.

- [x] Run many matches across fixed seeds, player counts, seats, and opponent sets with deterministic output ordering and summary tables.
- [x] Keep evaluation local and deterministic without live Kaggle submission.
- [x] Commit: `153050d Add evaluation batch runner`.

### Evaluation Harness Cycle 7: Generated Submission Parity Check

Status: complete and committed.

- [x] Run the same smoke/batch checks for modular agent vs bundled submission and compare outputs/status on fixed scenarios.
- [x] Fix submission loading isolation so bundled modules do not reuse or leak repo modules/import finders.
- [x] Commit: `803d839 Add generated submission parity check`.

### Evaluation Harness Cycle 8: Failure Triage Report

Status: complete and committed.

- [x] Group failures into parse crash, planner crash, action conversion crash, timeout/budget fallback, invalid/no-op-heavy behavior, and normal loss.
- [x] Add deterministic report items, summary counts, and keyword coverage for state adapter, evaluation, candidate, timeout, fallback, and invalid-action phrases.
- [x] Commit: `d21f817 Add evaluation failure triage reports`.

### Evaluation Harness Cycle 9: Baseline Scoreboard

Status: complete and committed.

- [x] Implementer has added the scoreboard module, public exports, and focused scoreboard tests.
- [x] Persist scoreboard records with agent version/commit, scenario set, win rate, mean rank, error rate, and notes.
- [x] Add `ScoreboardRecord` and deterministic conversion from Cycle 6 batch summaries.
- [x] Include triage category counts from Cycle 8.
- [x] Add JSONL write, append, and read helpers with stable ordering.
- [x] Complete final verifier checks in the implementation thread.
- [x] Planner/reviewer review and discrete commit.
- [x] Commit after implementation and review.
- Commit: `2e75ae4 Add evaluation scoreboard records`.

### Evaluation Harness Cycle 10: Regression Gate

Status: complete and committed.

- [x] Add a canonical quick evaluation command that exits nonzero on crashes, import failures, invalid submission build, or severe regression thresholds.
- [x] Add regression gate API and script.
- [x] Fix false-pass blocker by triaging severe categories in actual modular and submission parity batches, not only the built-in candidate batch.
- [x] Accept current nonzero script exit as correct because the real modular and bundled submission parity batches are currently no-op-heavy.
- [x] Commit: `623c456 Add evaluation regression gate`.

### Evaluation Harness Cycle 11: Analysis Pack For Planner Improvement

Status: complete and committed.

- [x] Generate compact diagnostic summaries from losing games with selected missions, action counts, final deltas, opponent type, and replay pointers.
- [x] Add pure analysis-pack layer over existing `EvaluationBatchResult` data.
- [x] Include losses, severe triage cases, no-op-heavy behavior, replay/artifact paths, selected metadata, deterministic ordering, max-items support, and JSON-safe output.
- [x] Commit: `7431618 Add evaluation planner analysis packs`.

### Evaluation Harness Cycle 12: Experiment Manifest Contracts And Match Expansion

Status: complete and committed.

- [x] Add deterministic experiment manifest contracts for local evaluation scenarios.
- [x] Add `ExperimentScenario`, `ExperimentManifest`, `PromotionThresholds`, and `manifest_to_match_configs(...)`.
- [x] Support JSON-safe round-trips, validation, fixed scenario ordering, and 2p/4p expansion into `MatchConfig` objects.
- [x] Export manifest API from `ow_eval`.
- [x] Keep this cycle as contracts and expansion only: no match execution, promotion enforcement, distributed execution, live submission, or result-file writing.
- Commit: `feb68ca Add evaluation experiment manifests`.

### Evaluation Harness Cycle 13: Experiment Manifest Local Runner

Status: complete and committed.

- [x] Add deterministic local experiment runner over `ExperimentManifest`.
- [x] Expand manifest into ordered `MatchConfig` values and execute through existing batch evaluation.
- [x] Return structured run result with expanded matches, batch result, scoreboard record, analysis pack, and summary text.
- [x] Preserve default no-artifact behavior and local-only evaluation boundaries.
- Commit: `3ef6b6b Add evaluation experiment runner`.

### Evaluation Harness Cycle 14: Promotion Gate

Status: complete and committed.

- [x] Add in-memory promotion/rejection decision layer over experiment run results.
- [x] Compare manifest thresholds against scoreboard metrics with deterministic failure ordering.
- [x] Cover passing decisions, individual threshold violations, unset thresholds, `None` metric handling, and JSON-safe output.
- [x] Avoid match execution and file writing in the gate layer.
- Commit: `50d747f Add evaluation promotion gate`.

### Evaluation Harness Cycle 15: Experiment Report Records And Persistence

Status: complete and committed.

- [x] Add deterministic report record combining `ExperimentRunResult` and `PromotionGateDecision`.
- [x] Include manifest identity, candidate, commit, run summary, gate summary, scoreboard, analysis pack, decision, and metadata.
- [x] Support JSON-safe round-trips plus explicit deterministic report write/read helpers.
- [x] Keep report writing explicit only; no matches, live submission, or distributed orchestration.
- Commit: `8dee2f2 Add evaluation experiment reports`.

### Evaluation Harness Cycle 16: End-To-End Local Experiment Command Layer

Status: complete and committed.

- [x] Implementer added CLI workflow module, script entrypoint, exports, and focused tests.
- [x] Workflow loads manifest JSON, runs experiment manifest, evaluates promotion gate, builds experiment report, optionally writes report JSON, and returns deterministic summary/exit code.
- [x] Implementer reported focused, grouped, full discovery, lazy import, and whitespace checks passing.
- [x] Implementer reported manual scope check: no matches at import time, report writing only with explicit output path.
- [x] Planner/reviewer review and discrete commit.
- [x] Commit after implementation and review.
- Commit: `03539f5 Add evaluation experiment CLI`.

### Evaluation Harness Cycle 17: Canonical Local Experiment Manifest Fixtures

Status: complete and committed.

- [x] Add committed JSON manifest fixtures under `experiments/manifests/`.
- [x] Include quick 2p smoke, quick 4p smoke, and promotion smoke manifests.
- [x] Verify fixtures parse, round-trip, expand deterministically, and stay compatible with the Cycle 16 CLI without running official matches in tests.
- [x] Keep fixtures data-only with no generated results, reports, logs, replays, submissions, or match outputs.
- Commit: `6da884d Add evaluation manifest fixtures`.

### Evaluation Harness Cycle 18: Local Experiment Suite Command

Status: complete and committed.

- [x] Add suite runner that executes multiple manifest fixtures through the existing Cycle 16 experiment CLI workflow.
- [x] Support explicit manifest paths or default committed fixtures in stable order.
- [x] Produce deterministic suite result and summary with pass/fail counts and failed manifest names.
- [x] Write reports only when an explicit report directory is supplied.
- Commit: `2317b08 Add evaluation experiment suite runner`.

### Evaluation Harness Cycle 19: Local Submission-Readiness Preflight Command

Status: complete and committed.

- [x] Add preflight layer that composes submission build, generated-submission parity, regression gate, and experiment suite checks.
- [x] Return ordered per-check records, deterministic summary text, and nonzero exit on failed or raised checks.
- [x] Keep unit tests patched at existing API boundaries so they do not run official matches or create real generated artifacts.
- [x] Export preflight API and add `scripts/submission_preflight.py`.
- Commit: `69d2ea3 Add evaluation submission preflight`.

### Evaluation Harness Cycle 20: Operational Runbook And Documentation Guardrails

Status: complete and committed.

- [x] Add local evaluation/pre-submission runbook at `docs/evaluation-harness.md`.
- [x] Document local-not-live scope, scarce live submission caveat, workflow commands, module/script responsibilities, manifest fixtures, artifact policy, and result interpretation.
- [x] Add docs guardrail tests for runbook paths, commands, help surfaces, local-not-live wording, artifact policy, and preflight script coverage.
- [x] Keep cycle docs/test only; no evaluation logic or generated artifacts.
- Commit: `cba9efd Add evaluation harness runbook`.

### Later Evaluation Infrastructure

- [x] Enforce promotion/rejection decisions over fixed seed blocks, opponent sets, 2p/4p mixes, paired seats, and pass/fail thresholds after manifest contracts exist.
- [x] Add a reviewed/committed end-to-end local experiment CLI if Cycle 16 is accepted.
- [x] Add canonical manifest fixtures, suite runner, submission preflight command, and runbook/docs guardrails.
- [x] Add Daytona/distributed evaluation only as a shardable execution layer for the same local official-environment manifests.
- [ ] Add live Kaggle submission discipline as a separate, explicitly approved workflow after local/distributed gates pass.

## Segment 9: Distributed Evaluation / Daytona Sharding

Status: complete.

Purpose: scale the same local official-environment evaluation manifests into deterministic shards that can later run locally, in parallel, or on Daytona sandboxes.

Important caveat:

- [x] Do not call Daytona, submit to live Kaggle, or execute matches until the sharding contracts are reviewed and committed.
- [x] Keep this segment grounded in existing local manifests and `MatchConfig` expansion.
- [x] Treat Cycle 0 as a pure planning-contract layer, not a remote-execution layer.
- [x] Continue avoiding Daytona calls, live Kaggle submissions, and real match execution until the distributed execution boundary is explicitly approved.

### Distributed Evaluation Cycle 0: Deterministic Shard-Plan Contracts

Status: complete and committed.

- [x] Add pure shard planning layer in `ow_eval/sharding.py`.
- [x] Define `EvaluationShard`, `EvaluationShardPlan`, `ShardPlanConfig`, and `build_evaluation_shard_plan(...)`.
- [x] Expand committed manifests through `ExperimentManifest` / `manifest_to_match_configs(...)`.
- [x] Partition expanded matches deterministically by either `shard_count` or `matches_per_shard`.
- [x] Produce stable shard IDs, labels, manifest references, match labels, seed lists, suggested local commands, JSON-safe `to_dict()`, and summary text.
- [x] Export API from `ow_eval` while preserving lazy import behavior.
- [x] Keep non-goals explicit: no Daytona calls, no multiprocessing/subprocess orchestration, no match execution, no generated artifacts.
- Commit: `ea4ab49 Add evaluation shard plan contracts`.

### Distributed Evaluation Cycle 1: Local Single-Shard Runner

Status: complete and committed.

- [x] Add a local runner over exactly one `EvaluationShard`.
- [x] Validate shard input and pass shard matches to `run_evaluation_batch(...)`.
- [x] Preserve default no-artifact behavior, with optional artifact config and prefix passthrough.
- [x] Return `EvaluationShardRunResult` with shard, batch result, deterministic summary, and JSON-safe `to_dict()`.
- [x] Keep non-goals explicit: no Daytona calls, no multiprocessing/subprocess orchestration, no persistence, no merging, and no CLI behavior.
- Commit: `e53812a Add evaluation shard runner`.

### Distributed Evaluation Cycle 2: Shard Run Result Persistence

Status: complete and committed.

- [x] Add deterministic single-shard result persistence in `ow_eval/shard_persistence.py`.
- [x] Write and read `EvaluationShardRunResult` as deterministic UTF-8 JSON with sorted keys, two-space indentation, and a trailing newline.
- [x] Create parent directories only when an explicit output path requires them.
- [x] Reconstruct typed nested `EvaluationShard`, `MatchConfig`, `EvaluationBatchResult`, `MatchResult`, `EvaluationBatchSummary`, and `EvaluationShardRunResult` objects.
- [x] Validate malformed payloads with `ValueError`.
- [x] Preserve roundtrip equality through `read(write(result)).to_dict() == result.to_dict()`.
- [x] Export the persistence API from `ow_eval` while preserving lazy import behavior.
- [x] Keep non-goals explicit: no match execution, no Daytona calls, no worker behavior, no CLI behavior, and no result merging.
- Commit: `90f3f40 Add evaluation shard result persistence`.

### Distributed Evaluation Cycle 3: Shard Result Merge

Status: complete and committed.

- [x] Add deterministic merge layer in `ow_eval/shard_merge.py`.
- [x] Merge in-memory `EvaluationShardRunResult` objects in deterministic input order.
- [x] Merge persisted shard-result JSON files through `read_evaluation_shard_run_result(...)`.
- [x] Recompute aggregate `EvaluationBatchSummary` from match results rather than trusting shard summaries.
- [x] Return frozen/slotted `EvaluationShardMergeResult` with shard results, merged batch result, summary text, and JSON-safe `to_dict()`.
- [x] Validate empty input, string input, wrong object types, malformed paths, and duplicate shard IDs.
- [x] Keep non-goals explicit: no match execution, no Daytona calls, no subprocesses, no CLI orchestration, no promotion gate.
- Commit: `1e93198 Add evaluation shard result merge`.

### Distributed Evaluation Cycle 4: Local Sequential Multi-Shard Workflow And CLI

Status: complete and committed.

- [x] Add `ow_eval/shard_cli.py` and `scripts/run_evaluation_shards.py`.
- [x] Compose shard planning, single-shard execution, explicit shard-result persistence, and shard-result merge.
- [x] Support one sharding strategy per run: `--shard-count` or `--matches-per-shard`.
- [x] Run shards sequentially in shard-plan order.
- [x] Persist shard result files only when an explicit output directory is supplied.
- [x] Return frozen/slotted `EvaluationShardCliResult` with plan, shard results, paths, merged result, exit code, summary text, error text, and JSON-safe `to_dict()`.
- [x] Keep focused tests mocked at existing boundaries so they do not run official matches, call Daytona, spawn subprocesses, or write repo artifacts.
- Commit: `2b83c60 Add evaluation shard CLI workflow`.

### Distributed Evaluation Cycle 5: Deterministic Shard Manifest Materialization

Status: complete and committed.

- [x] Add `ow_eval/shard_manifests.py`.
- [x] Convert each planned `EvaluationShard` into a shard-local `ExperimentManifest`.
- [x] Preserve match order, labels, seeds, player counts, controlled seats, opponent agents, and metadata.
- [x] Require one candidate agent per shard manifest and raise `ValueError` for mixed candidates.
- [x] Write deterministic UTF-8 JSON to each shard's planned manifest path.
- [x] Return frozen/slotted manifest write result with plan, manifest paths, commands, summary text, and JSON-safe `to_dict()`.
- [x] Keep non-goals explicit: no Daytona calls, no remote execution, no subprocess orchestration, no parallelism, no match execution.
- Commit: `57227d8 Add evaluation shard manifest materialization`.

### Distributed Evaluation Cycle 6: Deterministic Shard Job Package / Index Contracts

Status: complete and committed.

- [x] Implementer added `ow_eval/shard_jobs.py`, export wiring, and shard job tests.
- [x] Build one portable `EvaluationShardJob` per planned shard.
- [x] Include stable job id, shard id, label, manifest path, report path, shard-result path, job path, existing command, source manifest refs, match labels, and seeds.
- [x] Optionally materialize shard manifests through the Cycle 5 writer.
- [x] Write deterministic per-shard job JSON and a deterministic job index JSON.
- [x] Return frozen/slotted package result with plan, jobs, manifest paths, job paths, index path, commands, summary text, and JSON-safe `to_dict()`.
- [x] Keep non-goals explicit: no Daytona calls, no local parallelism, no worker orchestration, no command execution, no result persistence, no result merging, no CLI.
- Commit: `3f5c4a1 Add evaluation shard job packages`.

### Distributed Evaluation Cycle 7: Shard Package Preparation CLI

Status: complete and committed.

- [x] Add `ow_eval/shard_package_cli.py` and `scripts/prepare_evaluation_shards.py`.
- [x] Prepare shard job packages from manifests and an explicit output directory.
- [x] Require explicit output directory for package preparation.
- [x] Delegate deterministic job package/index writing to the Cycle 6 layer.
- [x] Return structured result and CLI exit behavior without executing shard jobs.
- [x] Keep non-goals explicit: no match execution, no Daytona calls, no subprocess execution, no worker orchestration, no result merging.
- Commit: `a56680f Add evaluation shard package CLI`.

### Distributed Evaluation Cycle 8: Local Single-Shard Job Runner

Status: complete and committed.

- [x] Add `ow_eval/shard_job_runner.py` and `scripts/run_evaluation_shard_job.py`.
- [x] Read one shard job JSON and reconstruct the corresponding `EvaluationShard` from its materialized manifest.
- [x] Validate reconstructed match labels and seeds against job metadata.
- [x] Run the reconstructed shard through the existing in-process shard runner.
- [x] Persist the shard run result to the job's planned shard-result path.
- [x] Return structured job-run result and CLI exit behavior.
- [x] Keep non-goals explicit: no Daytona calls, no package-index orchestration, no local parallelism, no command-string execution, no merge behavior.
- Commit: `f9b0b64 Add evaluation shard job runner`.

### Distributed Evaluation Cycle 9: Local Shard Job Index Runner

Status: complete and committed.

- [x] Add `ow_eval/shard_index_runner.py` and `scripts/run_evaluation_shard_index.py`.
- [x] Read the shard job package index into typed index records.
- [x] Run each packaged shard job sequentially through the Cycle 8 single-job runner.
- [x] Do not execute stored job command strings.
- [x] Merge persisted shard result files when all jobs pass.
- [x] Return nonzero and skip merge when any job fails, preserving attempted job results.
- [x] Return structured index-run result and CLI exit behavior.
- [x] Keep non-goals explicit: no Daytona calls, no local parallelism, no worker pools, no scheduling, no retries, no timeout management.
- Commit: `4652997 Add evaluation shard index runner`.

### Distributed Evaluation Cycle 10: Daytona Worker Job Spec Contracts

Status: complete and committed.

- [x] Add `ow_eval/daytona_jobs.py`.
- [x] Convert a committed shard job index into Daytona-ready worker job specs.
- [x] Preserve deterministic job-index order.
- [x] Emit structured worker argv, working directory, sandbox naming prefix, expected upload paths, and expected download/result paths.
- [x] Validate malformed config and malformed index/job metadata with clear errors.
- [x] Return frozen/slotted Daytona job plan/spec values with deterministic summary text and JSON-safe `to_dict()`.
- [x] Keep non-goals explicit: no Daytona SDK/config/credentials, no sandbox creation, no subprocess execution, no command execution, no uploads/downloads, no match execution.
- Commit: `80e660d Add evaluation Daytona job specs`.

### Distributed Evaluation Cycle 11: Deterministic Daytona Job Plan JSON Writer And CLI

Status: complete and committed.

- [x] Add `ow_eval/daytona_plan_cli.py` and `scripts/prepare_daytona_shard_jobs.py`.
- [x] Build Daytona shard job plans from a committed shard job index.
- [x] Write deterministic Daytona job plan JSON with sorted keys, two-space indentation, and trailing newline.
- [x] Create parent directories only for the explicitly supplied output path.
- [x] Support CLI config for working directory, Python command, runner script, sandbox name prefix, and no-prefix mode.
- [x] Return frozen/slotted plan write result with index path, output path, config, plan, exit code, summary text, error text, and JSON-safe `to_dict()`.
- [x] Keep non-goals explicit: no Daytona calls, no sandbox interaction, no subprocess execution, no worker command execution, no uploads/downloads, no match execution.
- Commit: `dbdeabc Add evaluation Daytona plan CLI`.

### Distributed Evaluation Cycle 12: Daytona Job Plan Reader And Preflight Validator

Status: complete and committed.

- [x] Add `ow_eval/daytona_preflight.py` and `scripts/validate_daytona_shard_jobs.py`.
- [x] Read Cycle 11 plan JSON and reconstruct typed `DaytonaShardJobPlan`, config, specs, nested `EvaluationShardJobIndex`, and nested jobs.
- [x] Preserve deterministic roundtrip behavior through `read_daytona_shard_job_plan(path).to_dict() == json.loads(path.read_text())`.
- [x] Validate non-empty spec fields, worker argv containing runner script and job path, non-empty upload/download paths, unique sandbox names, and existing upload paths when required.
- [x] Treat expected download/result paths as future outputs that do not need to exist yet.
- [x] Return frozen/slotted validation result with plan path, typed plan, missing upload paths, duplicate sandbox names, warning/error text, exit code, summary text, and JSON-safe `to_dict()`.
- [x] Add CLI flags for no upload path existence check and allowing duplicate sandbox names.
- [x] Keep non-goals explicit: no Daytona calls, no sandbox interaction, no subprocess execution, no worker argv execution, no match execution, no uploads/downloads, no result-file writing.
- Commit: `66ca026 Add evaluation Daytona preflight`.

### Distributed Evaluation Cycle 13: Daytona Executor Protocol And Fake-Executor Orchestration Boundary

Status: complete and committed.

- [x] Add `ow_eval/daytona_executor.py`.
- [x] Define typed execution requests, execution results, batch results, and injected executor protocol.
- [x] Preflight Daytona job plans before any executor call.
- [x] Build execution requests in plan spec order with structured argv, upload/download paths, working directory, sandbox name, and result path.
- [x] Run injected executor sequentially and preserve attempted execution results.
- [x] Skip merge on preflight or execution failure.
- [x] Merge shard result files in execution order when all executions pass and merge is enabled.
- [x] Keep non-goals explicit: no Daytona calls, no sandbox interaction, no subprocess execution, no worker argv execution, no uploads/downloads, no match execution.
- Commit: `2a89ee3 Add evaluation Daytona executor boundary`.

### Distributed Evaluation Cycle 14: Deterministic Daytona Executor Dry-Run CLI

Status: complete and committed.

- [x] Add `ow_eval/daytona_executor_cli.py` and `scripts/run_daytona_shard_jobs.py`.
- [x] Add deterministic dry-run executor over the Cycle 13 executor boundary.
- [x] Require dry-run mode for this cycle.
- [x] Support preflight flags for upload-path existence and duplicate sandbox-name behavior.
- [x] Support deterministic synthetic failure by job id or job index.
- [x] Default to `merge_results=False` in dry-run mode so shard result files do not need to exist.
- [x] Optionally write deterministic JSON output only to an explicit path.
- [x] Keep non-goals explicit: no Daytona calls, no sandbox interaction, no subprocess execution, no worker argv execution, no uploads/downloads, no match execution.
- Commit: `75bfd6c Add evaluation Daytona dry-run CLI`.

### Distributed Evaluation Cycle 15: Deterministic Daytona Sandbox Operation-Plan Contracts

Status: complete and committed.

- [x] Add `ow_eval/daytona_operations.py`.
- [x] Convert Cycle 13 execution requests into explicit sandbox operation plans.
- [x] Preserve request order exactly.
- [x] Represent upload operations, one structured command operation, download operations, sandbox metadata, working directory, and local result path.
- [x] Keep worker argv as structured tuple/list payload, not a shell string.
- [x] Return frozen/slotted JSON-safe operation-plan dataclasses with deterministic summary text.
- [x] Keep non-goals explicit: no Daytona imports, no sandbox starts, no command execution, no uploads/downloads, no match execution, no CLI.
- Commit: `4b244c6 Add evaluation Daytona operation plans`.

### Distributed Evaluation Cycle 16: Injected Daytona Client Executor Adapter Boundary

Status: complete and committed.

- [x] Add `ow_eval/daytona_client_executor.py`.
- [x] Define injected Daytona-like client protocol and support result/event dataclasses.
- [x] Adapt Cycle 15 operation plans into deterministic client method calls.
- [x] Preserve event traces for sandbox preparation, uploads, structured command, downloads, and cleanup.
- [x] Return structured nonzero results for client exceptions and command failures.
- [x] Add helper to run a Daytona job plan through the injected client executor.
- [x] Keep non-goals explicit: no Daytona SDK imports, no real sandbox creation, no subprocess execution, no worker argv execution, no real uploads/downloads, no match execution, no CLI.
- Commit: `c5a22f7 Add evaluation Daytona client executor`.

### Distributed Evaluation Cycle 17: Daytona Client Execution Report And Trace Capture

Status: complete and committed.

- [x] Add `ow_eval/daytona_client_report.py`.
- [x] Wrap the injected client executor with deterministic report capture.
- [x] Preserve batch result, client event trace, operation plans, exit code, summary text, and error text.
- [x] Preserve empty traces when preflight fails before client execution.
- [x] Preserve partial traces when execution stops after a failing job.
- [x] Provide JSON-safe report output.
- [x] Keep non-goals explicit: no Daytona SDK imports, no real sandbox creation, no subprocess execution, no worker argv execution, no real uploads/downloads, no match execution, no CLI.
- Commit: `248c413 Add evaluation Daytona client reports`.

### Distributed Evaluation Cycle 18: Deterministic Daytona Client Report Dry-Run CLI

Status: complete and committed.

- [x] Add `ow_eval/daytona_client_report_cli.py` and `scripts/run_daytona_client_report.py`.
- [x] Run Daytona plan JSON through the Cycle 17 client-report path with a deterministic fake/recording client.
- [x] Require dry-run mode for this cycle.
- [x] Support preflight flags, deterministic synthetic failure injection, and command exit-code simulation.
- [x] Default to `merge_results=False` so dry-run reports do not require shard result files to exist.
- [x] Optionally write deterministic JSON report output only to an explicit path.
- [x] Keep non-goals explicit: no Daytona SDK imports, no real sandbox creation, no subprocess execution, no worker argv execution, no real uploads/downloads, no match execution.
- Commit: `4672c56 Add evaluation Daytona client report CLI`.

### Distributed Evaluation Cycle 19: Real-Daytona Safety Gate And SDK Adapter Skeleton

Status: complete and committed.

- [x] Implementer added `ow_eval/daytona_real_config.py`, `ow_eval/daytona_sdk_adapter.py`, export wiring, and focused tests.
- [x] Add explicit real-execution config and readiness objects.
- [x] Fail readiness unless `allow_real_daytona=True`.
- [x] Fail readiness when required environment variables are absent or empty.
- [x] Add SDK adapter skeleton without importing Daytona at package import time.
- [x] Reviewer found initial safety blocker: injected clients could receive calls even when readiness was blocked.
- [x] Implementer applied the requested fix: adapter operations now gate through readiness before touching injected clients, and tests require explicit opt-in for fake-client success paths.
- [x] Keep non-goals explicit: no real Daytona SDK calls, no credentials use, no sandbox creation, no remote execution, no subprocess execution, no worker argv execution, no uploads/downloads, no match execution.
- [x] Planner/reviewer re-reviewed the readiness-gate fix and committed the discrete cycle.
- Commit: `cc09daa Add evaluation Daytona real execution safety gate`.

### Distributed Evaluation Cycle 20: Lazy Daytona SDK Loading And Client-Factory Boundary

Status: complete and committed.

- [x] Extend `DaytonaSdkAdapter` with lazy SDK module resolution and client-factory plumbing.
- [x] Preserve injected-client behavior while adding the future real SDK import/factory boundary.
- [x] Enforce readiness before SDK import, factory construction, or client calls.
- [x] Cache the resolved fake/protocol client after first operation.
- [x] Add deterministic `DaytonaSdkUnavailableError` handling for missing SDK/factory and bad factory returns.
- [x] Preserve lazy `ow_eval` import behavior.
- [x] Keep non-goals explicit: no live Daytona calls, no credentials use, no sandbox creation, no uploads/downloads, no remote command execution, no worker argv execution, no live Kaggle submissions.
- Commit: `e53531b Add evaluation Daytona SDK lazy loading`.

### Distributed Evaluation Cycle 21: Daytona SDK Protocol Client Facade

Status: complete and committed.

- [x] Add a concrete protocol-shaped facade for a low-level Daytona-like SDK object.
- [x] Implement facade methods for sandbox open/upload/command/download/close using fake SDK shapes in tests.
- [x] Convert low-level command results and sandbox handles into existing Daytona client protocol types.
- [x] Validate malformed SDK modules, constructors, low-level methods, and returns with deterministic adapter errors.
- [x] Make `DaytonaSdkAdapter` use the facade builder as its default factory path.
- [x] Preserve readiness-first behavior, fake-only tests, and lazy `ow_eval` import.
- [x] Keep non-goals explicit: no real Daytona package dependency, no real sandboxes, no uploads/downloads, no remote commands, no live Kaggle submissions.
- Commit: `c83b425 Add evaluation Daytona SDK protocol facade`.

### Distributed Evaluation Cycle 22: Guarded Real-Daytona Client Execution CLI Boundary

Status: complete and committed.

- [x] Add `ow_eval/daytona_real_cli.py` and `scripts/run_daytona_real_shard_jobs.py`.
- [x] Compose Daytona plan reading, real-execution readiness, SDK adapter construction, and client-report execution behind one guarded CLI/API boundary.
- [x] Require both environment readiness and explicit `--allow-real-daytona`.
- [x] Fail closed before importing Daytona, constructing a client, or calling client methods when readiness/allow is missing.
- [x] Preserve deterministic structured result and optional sorted JSON output.
- [x] Support existing preflight options for upload path existence and duplicate sandbox names.
- [x] Export the new public API from `ow_eval` while preserving lazy import behavior.
- [x] Keep non-goals explicit: no live Daytona calls in tests, no real credentials, no live Kaggle submissions, no retries, no worker pools, no scheduling, no promotion logic.
- Commit: `22c68d9 Add evaluation Daytona real execution CLI`.

### Distributed Evaluation Cycle 23: Operational Runbook And Safety Guardrails

Status: complete and committed.

- [x] Planner/reviewer issued the Cycle 23 goal prompt.
- [x] Implementer started the cycle and added the initial distributed-evaluation Daytona runbook document.
- [x] Add docs guardrail tests for script paths, command snippets, safety policy, and artifact policy.
- [x] Verify the requested docs/test/help-command/full-discovery checks.
- [x] Planner/reviewer review and discrete commit.
- Scope: document local-only sharding, shard package/index workflow, Daytona plan/preflight, fake/dry-run executor/report workflows, guarded real-Daytona CLI workflow, required env plus `--allow-real-daytona`, artifact policy, and troubleshooting.
- Non-goals: no live Daytona calls, no real sandboxes, no live Kaggle submissions, no new execution logic, no scheduling/retries/multiprocessing, no generated artifacts committed.
- Commit: `e242952 Add distributed Daytona evaluation runbook`.

### Distributed Evaluation Cycle 24: One-Command Distributed Evaluation Preflight

Status: complete and committed.

- [x] Add `ow_eval/distributed_preflight.py` and `scripts/distributed_evaluation_preflight.py`.
- [x] Compose shard packaging, Daytona plan generation, plan preflight, fake executor dry-run, fake client-report dry-run, and guarded real-Daytona fail-closed behavior into one deterministic local preflight.
- [x] Keep the preflight local/fake/guarded: no live Daytona calls, no live Kaggle submissions, and no real remote execution.
- [x] Support deterministic JSON output to an explicit path only.
- [x] Update distributed Daytona docs and guardrail tests with the new command.
- [x] Preserve lazy import behavior and keep generated artifacts out of the repo.
- [x] Planner/reviewer reviewed and committed the final distributed-evaluation acceptance gate.
- Commit: `b113207 Add distributed evaluation preflight`.

### Distributed Evaluation Segment Completion

- [x] Distributed shard planning, local shard execution, result persistence/merge, shard packaging/indexing, Daytona job planning/preflight, fake executor/client-report dry-runs, guarded real-Daytona CLI boundary, runbook guardrails, and one-command distributed preflight are complete.
- [x] Planner/reviewer moved the next high-level work to Competitive Improvement rather than adding more Daytona plumbing.
- [ ] Live Kaggle submission remains a separate, explicitly approved workflow after readiness gates pass.

## Segment 10: Competitive Improvement

Status: in progress.

Purpose: measure and improve competitive strength now that the deterministic build, local evaluation, and distributed-evaluation scaffolding are in place.

Current readiness finding:

- [x] Broad deterministic scaffolding is present: simulator, planner components, runtime/submission, local evaluation harness, distributed/Daytona evaluation, and baseline measurement pack.
- [x] A bounded local current-agent baseline now exists and passes its conservative local promotion threshold.
- [x] Stricter regression gate is now clean after Cycle 2: `scripts/evaluation_gate.py` exits `0` with `gate=PASS matches=2 win_rate=1 mean_rank=1 error_rate=0 parity=pass failures=0`.
- [x] Submission preflight is now green after Cycle 3; `scripts/submission_preflight.py` passed in about 164 seconds, and the default suite now completes in about 3.5 seconds.
- [x] Legacy-opponent smoke benchmark added after Cycle 4 and passed with `legacy-opponent-smoke 4 0.0 True`.
- [x] Planner/reviewer accepted Competitive Readiness / Submit V0 as complete after `4fd15ba Add legacy opponent smoke benchmark`.
- [ ] Live Kaggle baseline v0 remains blocked until Kaggle CLI and credentials are configured.

### Competitive Improvement Cycle 0: Current-Agent Baseline Measurement Pack

Status: complete and committed.

- [x] Add `experiments/manifests/competitive-baseline-smoke.json`.
- [x] Add `docs/competitive-improvement.md`.
- [x] Add `tests/test_competitive_improvement_docs.py`.
- [x] Add bounded official-runner support through scenario metadata `episode_steps` so the current-agent baseline remains routine.
- [x] Add report compatibility key `scoreboard_record.completed_matches` for compact baseline inspection.
- [x] Verify the baseline locally with report output under `/tmp` only.
- [x] Baseline report result: `competitive-baseline-smoke 6 True`.
- [x] Keep non-goals explicit: no planner/runtime/simulator/strategy changes, no live Kaggle submission, no real Daytona calls, no generated reports committed.
- Commit: `1055e57 Add competitive baseline measurement pack`.

### Competitive Readiness / Submit V0 Cycle 0: Gate Failure Diagnosis

Status: complete and committed.

- [x] Add deterministic diagnostics that explain why the current runtime agent is classified as `invalid_or_noop_heavy_behavior`.
- [x] Surface no-op/failure causes through runtime/evaluation report paths without changing action output.
- [x] Preserve modular/generated-submission parity diagnostics.
- [x] Allow the gate to keep failing only if it now reports actionable deterministic causes.
- [x] Gate result after this cycle: still exits `1`, with `budget_guard_budget_exhausted:499` for both modular and bundled parity.
- [x] Keep non-goals explicit: no planner scoring, candidate generation, commitment policy, strategy selection, simulator mechanics, runtime action behavior, live submission, network, or Daytona changes.
- Commit: `ae5ee3c Add competitive readiness gate diagnostics`.

### Competitive Readiness / Submit V0 Cycle 1: Runtime Candidate Budget Fix

Status: complete and committed.

- [x] Bound runtime candidate generation/validation through explicit config.
- [x] Cap estimated source-target pairs before simulator validation.
- [x] Add a small bounded parity overage budget so parity runs diagnose behavior rather than budget exhaustion.
- [x] Preserve diagnostics and avoid scoring/simulator changes.
- [x] Gate result after this cycle: still exits `1`, but no longer due to `budget_guard_budget_exhausted`; remaining issues are mostly `strategy_selection_no_action`, with some `no_candidates_generated`.
- [x] Competitive baseline still reports `competitive-baseline-smoke 6 True`.
- Commit: `e31a2bc Bound runtime candidate validation work`.

### Competitive Readiness / Submit V0 Cycle 2: No-Op Reduction Pass

Status: complete and committed.

- [x] Planner/reviewer issued Cycle 2 implementer prompt.
- [x] Implementer identified two current no-op causes: bounded candidate validation can starve valid candidates, and selected candidates can be rejected by minimum score.
- [x] Apply a focused runtime-default fix: validate a few ordered opportunities and use a runtime-only permissive selection floor.
- [x] Resolve no-op-heavy gate failure without weakening diagnostics, gate thresholds, or modular/generated-submission parity.
- [x] Ensure `scripts/evaluation_gate.py` exits `0` with `gate=PASS matches=2 win_rate=1 mean_rank=1 error_rate=0 parity=pass failures=0`.
- [x] Preserve bounded runtime candidate work and avoid broad scoring/simulator changes.
- [x] Planner/reviewer review and discrete commit.
- Commit: `3386c8f Reduce runtime no-op behavior`.

### Competitive Readiness / Submit V0 Cycle 3: Submission Preflight Green

Status: complete and committed.

- [x] Planner/reviewer issued Cycle 3 implementer prompt.
- [x] Primary goal: make `scripts/submission_preflight.py` exit `0` from committed state `3386c8f`.
- [x] Implementer found the preflight path is dominated by cumulative local suite runtime rather than gate failure; quick 2-player suite manifest alone took about 133 seconds.
- [x] Implementer stopped a stale interrupted preflight process before retrying.
- [x] Planner/reviewer guidance identified unbounded default smoke manifests as the long pole, not runtime candidate cap.
- [x] Bound the default smoke suite by adding positive `episode_steps` metadata to the default smoke manifests.
- [x] Confirm `scripts/submission_preflight.py` exits `0`; reviewer measured about 164 seconds.
- [x] Confirm `scripts/run_evaluation_suite.py` exits `0`; reviewer measured about 3.5 seconds.
- [x] Confirm `scripts/evaluation_gate.py` still exits `0` with `gate=PASS matches=2 win_rate=1 mean_rank=1 error_rate=0 parity=pass failures=0`.
- [x] Confirm focused tests, full discovery, and `git diff --check` pass.
- [x] Temporary runtime candidate cap experiments were reverted; no runtime behavior/scoring/simulator changes were included.
- Commit: `94d4f80 Bound submission preflight smoke suite`.

### Competitive Readiness / Submit V0 Cycle 4: Legacy Opponent Benchmark Pack

Status: complete and committed.

- [x] Planner/reviewer issued Cycle 4 implementer prompt.
- [x] Add bounded local benchmark manifest using current modular runtime agent against viable historical `python_file` opponents.
- [x] Implementer selected only historical files that completed bounded local harness probes; import-failing candidates are being documented/skipped rather than forced.
- [x] Implementer added `experiments/manifests/legacy-opponent-smoke.json`, `tests/test_legacy_opponent_benchmark.py`, manifest fixture guardrail updates, and a `docs/competitive-improvement.md` update.
- [x] Bounded legacy benchmark completed with compact report: `legacy-opponent-smoke 4 0.0 True`.
- [x] `scripts/evaluation_gate.py` remained green.
- [x] `scripts/submission_preflight.py` passed with all four checks green.
- [x] Full discovery passed after test cleanup.
- [x] Planner/reviewer review and discrete commit.
- Commit: `4fd15ba Add legacy opponent smoke benchmark`.

### Competitive Readiness / Submit V0 Segment Completion

- [x] Gate diagnostics, runtime budget bounding, no-op reduction, submission preflight boundedness, and legacy-opponent smoke benchmark are complete.
- [x] Planner/reviewer explicitly treated this segment as complete after `4fd15ba Add legacy opponent smoke benchmark`.
- [x] Next segment: Live Submission V0.

## Segment 11: Live Submission V0

Status: complete.

Purpose: build the exact V0 artifact, verify local readiness, make exactly one live Kaggle submission, and record enough metadata for replay-analysis handoff.

Important caveat:

- [x] User narrowed the segment to end at making one live Kaggle submission, with no additional approval required once local readiness and submission mechanism are clean.
- [x] Submit at most once.
- [x] Do not tune agent behavior, planner scoring, runtime logic, simulator mechanics, manifests, gates, or thresholds in this segment.
- [x] Live upload proceeded only after Kaggle CLI/package and credentials were configured/usable.

### Live Submission V0 Cycle 0: Submission Mechanism Preflight

Status: complete and committed.

- [x] Identify exact future live-submit command: `kaggle competitions submit -c orbit-wars -f /tmp/orbit_wars_v0_submission.py -m "V0 local preflight passed"`.
- [x] Confirm competition slug: `orbit-wars`.
- [x] Build `/tmp/orbit_wars_v0_submission.py` and record artifact metadata.
- [x] Artifact size/hash: `304475` bytes, SHA256 `66b95ae02cf82a0801de2d4827496f1d992bf8de8cb790ac2a1743907d58ca64`.
- [x] Confirm no live submission was made and no upload command was run.
- [x] Add source-controlled runbook `docs/live-submission-v0.md`.
- [x] Initial blocker confirmed at Cycle 0 time: no system `kaggle` command, venv could not import `kaggle`, and `~/.kaggle/kaggle.json` was not present.
- [x] `git diff --check` passed.
- Commit: `c558a30 Add live submission mechanism preflight`.

### Live Submission V0 Cycle 1: Final Artifact Freeze, Local Readiness, And Submit Once

Status: complete and committed.

- [x] Configure/verify Kaggle CLI or package availability: `.venv/bin/kaggle` usable, `Kaggle CLI 2.2.2`.
- [x] Configure/verify Kaggle credentials without exposing secrets; non-upload submissions listing worked before upload.
- [x] Rebuild and hash final `/tmp/orbit_wars_v0_submission.py`.
- [x] Final artifact size/hash: `304475` bytes, SHA256 `66b95ae02cf82a0801de2d4827496f1d992bf8de8cb790ac2a1743907d58ca64`.
- [x] Rerun local readiness before upload: `scripts/evaluation_gate.py` passed with `gate=PASS matches=2 win_rate=1 mean_rank=1 error_rate=0 parity=pass failures=0`.
- [x] Rerun local readiness before upload: `scripts/submission_preflight.py` passed with `submission_preflight=PASS total=4 passed=4`.
- [x] Run the live submit command exactly once: `.venv/bin/kaggle competitions submit -c orbit-wars -f /tmp/orbit_wars_v0_submission.py -m "serious-v0 local preflight passed c558a30"`.
- [x] Kaggle accepted the upload with submission ref `53862054`.
- [x] Reviewer verified submission status is `SubmissionStatus.COMPLETE` with public score `600.0`.
- [x] No generated reports/artifacts or secrets were committed; only the runbook/metadata record was committed.
- Commit: `80fca70 Record live V0 Kaggle submission`.

### Live Submission V0 Segment Completion

- [x] Exactly one live Kaggle submission was made for V0.
- [x] Submission metadata recorded in `docs/live-submission-v0.md`.
- [x] Replay-analysis handoff should continue in a separate chat once games are available.
- [x] Segment completion sentinel: `LIVE_SUBMISSION_V0_SEGMENT_COMPLETE`.

## Segment 12: Live Feedback Intake + Competitive Improvement Loop

Status: Cycle 0 complete; follow-up work moved into Segment 13, V0 Replay Leak Fix.

Purpose: use live Kaggle feedback and local evaluation to identify concrete V0 weaknesses, then run disciplined improvement cycles before spending additional live submissions.

Operating rules:

- [x] Do not change agent behavior until V0 live status/replays have been captured and reviewed.
- [x] Use live submissions deliberately; avoid blind retries or rapid-slot spending.
- [x] Keep replay analysis in the separate replay-analysis chat when available, then summarize plan-relevant findings here.
- [ ] Promote or reject changes through local gates, baseline comparisons, and replay evidence before next live candidate submission.

### Live Feedback Intake Cycle 0: V0 Live Results Intake

Status: complete.

- [x] Capture current Kaggle status, score, and rough placement signal for submission ref `53862054`.
- [x] Wait long enough for V0 to accumulate useful live games before drawing conclusions.
- [x] Download available games/replays for submission ref `53862054` in a separate replay-analysis workflow.
- [x] Produce a compact weakness report before changing the agent.
- [x] Track concrete leak categories such as no-op turns, target choice, over-sending, under-defending, 2p/4p mode behavior, and timing errors.
- [x] Replay analysis report: `docs/submission_replay_analyses/ashxudev_orbit_wars_v0_submission/analysis.md`.
- [x] Replay sample: 20 public episodes, public score `426.8`, sample record `4-16`, 4P record `0-10`, 2P record `4-6`.
- [x] Primary finding: all `10/10` sampled 4P games emitted `0` actions.

### Live Feedback Intake Cycle 1: Local Historical-Agent Comparison

Status: planned; may run after the first replay-leak fixes if needed.

- [ ] Run the current V0 against existing viable historical agents using the legacy-opponent smoke benchmark surface.
- [ ] Compare local weaknesses against the live replay weakness report.
- [ ] Decide whether local/historical failures are representative enough to drive the first tuning cycle.

### Live Feedback Intake Cycle 2: First Competitive Tuning Candidate

Status: moved into Segment 13 evidence-backed leak-fix cycles.

- [ ] Choose one improvement surface only after evidence review.
- [ ] Candidate surfaces include planner scoring weights, mission evaluation terms, commitment thresholds, 2p/4p selectors, target prioritization, reserve behavior, and anti-no-op fallback behavior.
- [ ] Run local gates, baseline comparison, and replay inspection.
- [ ] Promote/reject the change with evidence recorded.

### Live Feedback Intake Cycle 3: Next Live Candidate Submission

Status: planned behind a promoted tuning candidate.

- [ ] Build and hash the next candidate artifact.
- [ ] Rerun local readiness checks immediately before upload.
- [ ] Spend one additional Kaggle submission slot only when the candidate has an evidence-backed reason to improve over V0.
- [ ] Record submission metadata and hand off to replay analysis.

## Segment 13: V0 Replay Leak Fix

Status: complete. Planner/reviewer emitted `V0_REPLAY_LEAK_FIX_SEGMENT_COMPLETE` after Cycle 9 commit `3641021 Record V1 replay leak readiness`.

Purpose: convert V0 live replay failures into local regression fixtures, fix the mechanical no-action leaks first, then proceed through targeted policy fixes before preparing a V1 candidate.

Segment completion sentinel: `V0_REPLAY_LEAK_FIX_SEGMENT_COMPLETE`.

Replay-analysis inputs:

- [x] Submission ref `53862054`, public score `426.8`.
- [x] Replay report found sample record `4-16`; 4P record `0-10`; 2P record `4-6`.
- [x] Main 4P failure: all sampled 4P games emitted zero actions.
- [x] Main 2P failures: pressure/retention collapse after good openings, insufficient reinforcement, passive low-candidate behavior, and capture-hold failures.

### V0 Replay Leak Fix Cycle 0: Replay Regression Fixtures

Status: complete and committed.

- [x] Add compact single-observation fixtures under `tests/fixtures/v0_replay_leaks/`.
- [x] Add focused characterization test `tests/test_v0_replay_leak_fixtures.py`.
- [x] Add docs note `docs/v0-replay-leak-fix.md`.
- [x] Cover 4P no-action/candidate starvation from episodes `80766287` and `80761836`.
- [x] Cover 2P pressure collapse from `80756891` and `80760443`.
- [x] Cover 2P idle/near-idle from `80768833`.
- [x] Cover capture-hold windows from `80763852`.
- [x] Confirm behavior is characterized without runtime, planner, scoring, simulator, gate, or action-conversion changes.
- Commit: `560b26d Add V0 replay leak characterization fixtures`.

### V0 Replay Leak Fix Cycle 1: Candidate Starvation Fix

Status: complete and committed.

- [x] Prevent `max_candidates` from starving validation by slicing only the first ordered source-target estimates before affordable/valid opportunities are reached.
- [x] Preserve bounded runtime work with an explicit validation/search bound: `max_validation_attempts`.
- [x] Ensure 4P fixture `four_p_no_action_80761836_t100_p2.json` no longer fails as `runtime_diagnostic_no_action_reason == "no_candidates_generated"`.
- [x] Keep true no-action t0 fixture precise if no affordable capture exists.
- [x] Restore missing replay `step` on the two 4P fixtures so moving-planet validation has the correct time anchor.
- [x] Reviewer confirmed no scoring, strategy-selection, defense, capture-hold, simulator, action-conversion, gate threshold, or Kaggle submission changes.
- [x] Reviewer reran focused checks, full discovery, `scripts/evaluation_gate.py`, `scripts/submission_preflight.py`, and `git diff --check`; sequential rerun handled a non-reproduced parity/preflight mismatch.
- [x] Known post-cycle state: t100 4P fixture now has candidates but still returns no action due to `strategy_selection_no_action`.
- Commit: `258932f Fix candidate validation starvation`.

### V0 Replay Leak Fix Cycle 2: Four-Player Strategy Selection Action Fix

Status: complete and committed.

- [x] Continue from commit `258932f Fix candidate validation starvation`.
- [x] Fix the remaining 4P replay leak where candidate generation produces candidates but the selector returns no action.
- [x] Make `tests/fixtures/v0_replay_leaks/four_p_no_action_80761836_t100_p2.json` emit at least one legal runtime action.
- [x] Ensure the t100 4P fixture no longer reports `strategy_selection_no_action`.
- [x] Candidate generation remains bounded and reports 10 generated candidates for the t100 fixture.
- [x] 4P selector now treats `CandidateOutcome.VALIDATED` as eligible rather than requiring zero-horizon facts to show target ownership.
- [x] `FourPlayerSelectionConfig.minimum_total_score` default aligned with runtime default `-100.0`.
- [x] t100 fixture now emits `[[14, 0.9921420246533353, 44]]` with `runtime_diagnostic_status=actions` and `runtime_diagnostic_no_action_reason=actions_emitted`.
- [x] Reviewer confirmed no defense/reinforcement policy, capture-hold policy, source reserve policy, broad scoring churn, 2P pressure fix, simulator mechanics, gate threshold, or Kaggle submission changes.
- [x] Reviewer reran focused tests, full discovery, `scripts/evaluation_gate.py`, `scripts/submission_preflight.py`, and `git diff --check`.
- Commit: `125d1c5 Fix four-player strategy no-action leak`.

### V0 Replay Leak Fix Cycle 3: Opening Idle Fallback

Status: complete and committed.

- [x] Continue from commit `125d1c5 Fix four-player strategy no-action leak`.
- [x] Implementer added a deterministic, bounded fallback for parseable opening/low-owned states where normal planner/action conversion returns no action.
- [x] Implementer kept fallback opening-only with `state.step == 0`.
- [x] Implementer fixture behavior: `four_p_no_action_80766287_t000_p2.json` emits `[[2, 1.8209839426200924, 1]]`.
- [x] Implementer fixture behavior: `two_p_idle_80768833_t000_p1.json` emits `[[3, -1.1909779141417376, 1]]`.
- [x] Implementer reported `four_p_no_action_80761836_t100_p2.json` remains fixed and emits action(s).
- [x] Focused runtime/replay, planner/config/selector, and submission/evaluation focused tests passed in review.
- [x] Follow-up implementer work attempted to harden generated-submission module isolation in `ow_eval/agent_loading.py` so returned `submission_file` callables execute with bundled `agents`, `ow_planner`, and `ow_sim` modules during every call.
- [x] Follow-up implementer added `tests/test_evaluation_agent_loading.py` coverage for lazy bundled imports and `_BundledFinder` cleanup.
- [x] Follow-up focused checks passed, including `tests.test_evaluation_agent_loading tests.test_evaluation_parity`.
- [x] Second follow-up implementer work kept opening fallback behavior unchanged and added generated-submission diagnostic isolation across `ow_eval/agent_loading.py` and `ow_eval/official_runner.py`.
- [x] Generated submission callables reportedly retain captured bundled module namespaces and expose `isolated_modules()` for each call.
- [x] Official-runner runtime diagnostic extraction reportedly runs under submission isolation, including through parity's bounded wrapper.
- [x] Second follow-up regression coverage added in `tests/test_evaluation_agent_loading.py` and `tests/test_evaluation_official_runner.py`.
- [x] Implementer reported full discovery, `scripts/evaluation_gate.py`, `scripts/submission_preflight.py`, and `git diff --check` passed after the second follow-up.
- [x] Reviewer re-review accepted the second isolation/diagnostic follow-up.
- [x] Reviewer committed Cycle 3 as `06db0f3 Fix opening idle fallback and submission isolation`.
- [x] Original review blocker: full discovery failed in generated-submission parity at `tests/test_evaluation_parity.py:402`; first run also failed at `:422`.
- [x] Prior blocker after first isolation follow-up: full discovery still failed in generated-submission parity at `tests/test_evaluation_parity.py:422`, specifically `test_real_parity_check_uses_provided_submission_path`.
- [x] Acceptance required reviewer full discovery, gate, preflight, diff check, and commit.
- [x] Did not add defense/reinforcement, capture-hold, 2P pressure-collapse, scoring, simulator, gate, or Kaggle submission changes in this cycle.
- Commit: `06db0f3 Fix opening idle fallback and submission isolation`.

### V0 Replay Leak Fix Cycle 4: Two-Player Pressure Retention Selector

Status: complete and committed.

- [x] Continue from commit `06db0f3 Fix opening idle fallback and submission isolation`.
- [x] Implementer added a narrow pressure-retention facts surface in `ow_planner/two_player_pressure.py`.
- [x] Implementer adjusted `ow_planner/two_player_selection.py` so visible 2P response pressure prefers validated `reserve_preserving` commitments when available.
- [x] Implementer exported pressure facts through `ow_planner/__init__.py`.
- [x] Added direct selector/fact tests in `tests/test_planner_two_player_selection.py`.
- [x] Added replay pressure checks in `tests/test_v0_replay_leak_fixtures.py`.
- [x] Live-entrypoint pressure probe matched expected behavior: `two_p_pressure_80756891_t060_p0.json` emits `[[12, -2.5306591719605933, 8]]` with `selected_commitment_type=reserve_preserving`.
- [x] Preserved budget guard for `two_p_pressure_80760443_t100_p0.json`: committed replay observation has negative `remainingOverageTime` and returns no action with `budget_guard_budget_exhausted`.
- [x] Positive-time in-memory variant reportedly emits `[[8, -2.759992696416082, 19]]` with `selected_commitment_type=reserve_preserving`.
- [x] Focused pressure/runtime/planner/evaluation checks and `git diff --check` passed in review.
- [x] Review blocker: full `.venv/bin/python -m unittest discover -s tests` failed at `tests/test_evaluation_parity.py:435`, `test_real_parity_artifacts_are_written_under_temp_directory`, where `result.passed` was `False`.
- [x] The failing parity artifact test and the full `tests.test_evaluation_parity` module pass in isolation, so reviewer suspected order-dependent generated-submission parity/state contamination under full discovery.
- [x] Blocker-fix prompt was issued and implementer completed a narrow follow-up without changing pressure-retention behavior.
- [x] Follow-up added bundler coverage so `ow_planner.two_player_pressure` is included in discovered bundle modules and generated `_BUNDLED_SOURCES`.
- [x] Follow-up extended generated-submission lazy-import isolation coverage so `ow_planner.two_player_pressure` resolves to the bundled module even when a repo module is preloaded.
- [x] Follow-up changed `ow_eval/parity.py` so parity-loaded runtime agents use a deterministic clock through the existing `RuntimeDefaultConfig` path, aimed at removing modular-vs-submission wall-clock variance in parity only.
- [x] Follow-up added `tests/test_evaluation_parity.py` regression coverage proving parity uses the deterministic runtime clock.
- [x] Implementer reported post-fix full discovery, parity/bundler/loading/official-runner group, planner/replay focused tests, evaluation gate, submission preflight, and `git diff --check` all passed.
- [x] Reviewer accepted the pressure-retention work and deterministic-clock blocker fix.
- [x] Reviewer committed Cycle 4 as `ea96f24 Add two-player pressure retention selection`.
- [x] Preserved Cycle 4 pressure-retention behavior while fixing the review blocker.
- [x] Did not broaden into capture-hold, broad reinforcement/defense missions, simulator mechanics, gate threshold, opening fallback, 4P behavior, or live submission changes.
- Commit: `ea96f24 Add two-player pressure retention selection`.

### V0 Replay Leak Fix Cycle 5: Capture-Hold Candidate Recovery

Status: complete and committed.

- [x] Continue from commit `ea96f24 Add two-player pressure retention selection`.
- [x] Target remaining capture-hold fixtures:
  - `tests/fixtures/v0_replay_leaks/two_p_capture_hold_80763852_t125_p1.json`
  - `tests/fixtures/v0_replay_leaks/two_p_capture_hold_80763852_t131_p1.json`
- [x] Implementer added owned-target reinforcement enumeration in `ow_planner/enumeration.py`, ordered after neutral captures but before enemy attacks to avoid validation-attempt starvation.
- [x] Implementer added one-ship owned-target reinforcement estimates in `ow_planner/estimation.py`.
- [x] Implementer mapped owned-target validated reports to `MissionType.REINFORCE` in `ow_planner/candidates.py`.
- [x] Added/updated owned-target coverage in `tests/test_planner_enumeration.py`, `tests/test_planner_estimation.py`, `tests/test_planner_outcomes.py`, and `tests/test_planner_generation.py`.
- [x] Updated capture-hold regression coverage and fixture expectations in `tests/test_v0_replay_leak_fixtures.py` and the two capture-hold fixture JSON files.
- [x] Implementer reported `two_p_capture_hold_80763852_t125_p1.json` emits `[[7, 0.3314511455663926, 1]]` through agent and budgetless runtime, with `candidate_count=8` and `selected_commitment_type=reserve_preserving`.
- [x] Implementer reported `two_p_capture_hold_80763852_t131_p1.json` emits `[[11, 1.6355606646675733, 1]]` through agent and budgetless runtime, with `candidate_count=8` and `selected_commitment_type=reserve_preserving`.
- [x] Implementer reported focused runtime/replay/planner/evaluation/parity checks, full discovery, evaluation gate, submission preflight, and `git diff --check` passed.
- [x] Reviewer accepted the owned-target reinforcement candidate recovery work.
- [x] Reviewer committed Cycle 5 as `c8982df Add capture-hold reinforcement candidates`.
- [x] Preserved simulator mechanics, budget guards, generated-submission parity, evaluation gate, submission preflight, 4P behavior, opening fallback behavior, and Cycle 4 pressure-retention behavior.
- [x] Did not broaden into full defense/reinforcement strategy or live-only runtime fallback.
- Commit: `c8982df Add capture-hold reinforcement candidates`.

### V0 Replay Leak Fix Cycle 6: Pressure-Aware Selection And Reserve Policy

Status: complete and committed.

- [x] Goal prompt issued after Cycle 5 commit `c8982df Add capture-hold reinforcement candidates`.
- [x] Scope: make two-player selection more conservative under visible owned-production pressure without runtime-only fallback or broad scoring-weight tuning.
- [x] Implementer baseline probe found all four relevant fixtures already use reserve-preserving commitments; the remaining policy gap is that pressure filtering only considers commitment type, so an attack/capture can still beat owned-target reinforcement.
- [x] Implementer changed `ow_planner/two_player_selection.py` so, under active pressure with reserve-preserving options, owned-retention missions (`MissionType.REINFORCE` / `MissionType.DEFEND_OWN`) become the selection pool before expansion attacks.
- [x] Implementer added direct selector tests in `tests/test_planner_two_player_selection.py` for pressure-owned-retention preference and no-pressure direct-advantage control.
- [x] Focused selector/replay, broader planner/runtime, submission/evaluation/parity group, full discovery, evaluation gate, and `git diff --check` reportedly passed in the implementation thread.
- [x] Reviewer accepted the pressure-aware retention selection work.
- [x] Reviewer verified pressure fixtures still select reserve-preserving behavior, negative-overage remains budget-guarded, capture-hold fixtures still select reserve-preserving reinforcement, full discovery passed, gate passed, preflight passed, and diff checks passed.
- [x] Reviewer committed Cycle 6 as `e3209d0 Add pressure-aware retention selection`.
- [x] Preserved pressure fixture behavior, capture-hold fixtures, 4P action recovery, opening fallback, generated-submission parity, gate, and preflight.
- Commit: `e3209d0 Add pressure-aware retention selection`.

### V0 Replay Leak Fix Cycle 7: Capture-Hold Gate

Status: complete and committed.

- [x] Goal prompt issued after Cycle 6 commit `e3209d0 Add pressure-aware retention selection`.
- [x] Scope: prevent risky capture missions from being selected when response facts indicate likely reinforcement/race/recapture unless a stronger hold-sized commitment is available.
- [x] Intended policy: risky `CAPTURE_NEUTRAL` / `ATTACK_ENEMY` bundles with labels such as `target_reinforcement_feasible` or `target_race_risk` should prefer validated `capture_and_hold` over thinner sends when available.
- [x] Intended policy: if a risky capture has no validated hold-sized option and a safer validated owned-retention option exists, prefer `REINFORCE` / `DEFEND_OWN`.
- [x] Implementer changed `ow_planner/two_player_selection.py` with capture-hold risk labels and risk-aware commitment preference ordering.
- [x] Added direct selector tests for hold-sized risky capture, risky thin capture yielding to retention, no-risk ordering control, and preserving validated reserve behavior.
- [x] Initial version changed pressure fixtures to `capture_and_hold`; implementer narrowed the gate so risky captures prefer hold-sized commitment only when no validated reserve-preserving option exists.
- [x] Reviewer accepted the capture-hold risk gate after fixture probes, focused selector/replay checks, broader planner/runtime checks, submission/evaluation/parity checks, full discovery, evaluation gate, submission preflight, and `git diff --check`.
- [x] Preserved capture-hold replay fixtures, pressure fixture behavior, Cycle 6 pressure-aware retention behavior, 4P action recovery, opening fallback, generated-submission parity, gate, and preflight.
- Commit: `739ca12 Add capture-hold risk gate`.

### V0 Replay Leak Fix Cycle 8: Replay Regression Harness

Status: complete and committed.

- [x] Goal prompt issued after Cycle 7 commit `739ca12 Add capture-hold risk gate`.
- [x] Scope: add measurement infrastructure only; do not change runtime, planner, simulator, gate, or submission behavior.
- [x] Implementer added `ow_eval/v0_replay_regression.py` to run committed V0 replay leak fixtures through current runtime and a budgetless probe.
- [x] Implementer exported the harness API from `ow_eval/__init__.py`.
- [x] Implementer added `tests/test_v0_replay_regression.py` for report coverage, metrics, and stability.
- [x] Harness reports case-level results plus aggregate metrics for action rate, no-action count/streak, pressure/retention action rate, budget-guarded no-actions, and risky thin-capture proxy counts.
- [x] Report summary: `v0_replay_regression cases=7 live_actions=5 live_no_actions=2 budget_guarded=1 budgetless_actions=7 pressure_actions=4 risky_thin_captures=0 unresolved_planner_no_actions=0`.
- [x] Reviewer accepted the measurement-only harness after direct probe, focused fixture/harness tests, lazy import sanity, full discovery, evaluation gate, submission preflight, and `git diff --check`.
- [x] Preserved runtime, planner, simulator, gate, and submission behavior exactly.
- Commit: `e3d0cde Add V0 replay regression harness`.

### V0 Replay Leak Fix Cycle 9: V1 Candidate Evaluation And Submit Prep

Status: complete and committed.

- [x] Goal prompt issued after Cycle 8 commit `e3d0cde Add V0 replay regression harness`.
- [x] Scope: no-submit V1 candidate readiness note; do not change planner/runtime/simulator behavior or make a live Kaggle submission.
- [x] Implementer updated `docs/v0-replay-leak-fix.md` with replay-regression summary, local readiness results, benchmark summaries, V1 artifact hash, and optional V1-vs-V0 smoke comparison.
- [x] Replay regression still reports `unresolved_planner_no_actions=0` and one separately counted budget-guarded case.
- [x] Implementer reports full discovery passed with 1249 tests, `scripts/evaluation_gate.py` passed, and `scripts/submission_preflight.py` passed.
- [x] Implementer reports legacy opponent smoke and competitive baseline smoke completed without harness errors.
- [x] V1 candidate artifact built under `/tmp`: size `316055`, SHA256 `b05984e62d14190cf937c0b749862304e4a67a28e822c901fd47a7fbc57cc514`.
- [x] Optional temporary V1-vs-V0 smoke comparison completed under `/tmp` with no harness errors.
- [x] Readiness note conclusion: V1 is ready to proceed to the next live-submission segment, subject to rebuilding a fresh final `/tmp` artifact and rerunning local readiness checks.
- [x] Reviewer accepted the no-submit readiness note after focused replay checks, harness summary, full discovery, evaluation gate, submission preflight, benchmark reruns, rebuilt artifact hash check, optional V1-vs-V0 smoke report verification, and `git diff --check`.
- [x] Preserved no-submit boundary and kept generated artifacts/reports out of source control.
- Commit: `3641021 Record V1 replay leak readiness`.

## Segment 14: Live Submission V1

Status: complete. Planner/reviewer confirmed V1 was submitted once and committed the live record as `313c0c4 Record V1 live submission`; runbook includes `LIVE_SUBMISSION_V1_SEGMENT_COMPLETE`. Later non-upload score check showed current V1 public score `429.2`.

Purpose: make exactly one live Kaggle submission of the V1 agent that passed replay-leak readiness, then verify Kaggle accepted it and record non-secret submission metadata.

Segment completion sentinel: `LIVE_SUBMISSION_V1_SEGMENT_COMPLETE`.

### Live Submission V1 Cycle 0: Final No-Submit Mechanism Check

Status: complete and committed.

- [x] Planner/reviewer created the Live Submission V1 segment plan after V0 Replay Leak Fix completion.
- [x] Scope: non-upload Kaggle mechanism check only; do not build final artifact or submit.
- [x] Implementer added `docs/live-submission-v1.md` with competition slug, checked HEAD, Kaggle CLI status, non-upload submissions-list status, credential/config status without secrets, and explicit no-submit confirmation.
- [x] Checked HEAD: `3641021 Record V1 replay leak readiness`.
- [x] Kaggle CLI path/version recorded: `.venv/bin/kaggle`, `Kaggle CLI 2.2.2`.
- [x] Non-upload access check `.venv/bin/kaggle competitions submissions -c orbit-wars` succeeded and listed existing submissions.
- [x] Credential status recorded without secrets: `~/.kaggle/kaggle.json` absent, but local access-token configuration authenticates the venv Kaggle CLI.
- [x] `git diff --check` passed.
- [x] Reviewer accepted the no-submit mechanism check after rerunning non-upload Kaggle version/submissions-list checks with network escalation, credential-presence checks without secrets, cached diff hygiene, and scope verification.
- [x] Preserved no-submit boundary: no `.venv/bin/kaggle competitions submit`, no artifact build, no behavior changes.
- Commit: `519e1a2 Add V1 live submission mechanism check`.

### Live Submission V1 Cycle 1: Final Artifact Freeze And Local Readiness

Status: complete and committed.

- [x] Goal prompt issued after Cycle 0 commit `519e1a2 Add V1 live submission mechanism check`.
- [x] Rebuilt fresh V1 artifact under `/tmp/orbit_wars_v1_submission.py`.
- [x] Recorded artifact size `316055` bytes and SHA256 `b05984e62d14190cf937c0b749862304e4a67a28e822c901fd47a7fbc57cc514`.
- [x] Reran replay regression with `unresolved_planner_no_actions=0`.
- [x] Reran `scripts/evaluation_gate.py` and `scripts/submission_preflight.py`; both passed.
- [x] Reran bounded smoke benchmarks; `legacy-opponent-smoke 4 0.0 True` and `competitive-baseline-smoke 6 0.0 True`.
- [x] Updated `docs/live-submission-v1.md` with final local readiness evidence and explicit confirmation that no Kaggle upload command was run.
- [x] Confirmed generated artifact and reports were not committed.
- [x] Reviewer accepted the final artifact readiness note after fresh replay regression, artifact rebuild/hash, evaluation gate, submission preflight, smoke benchmark verification, scope check, and `git diff --check`.
- Commit: `4e66048 Record V1 final artifact readiness`.

### Live Submission V1 Cycle 2: One Live Kaggle Submission

Status: complete and committed.

- [x] Goal prompt issued after Cycle 1 commit `4e66048 Record V1 final artifact readiness`.
- [x] Before upload, implementer reran non-upload Kaggle access, replay regression, evaluation gate, submission preflight, fresh artifact rebuild/hash, and recorded results.
- [x] Exactly one live upload command was run for `/tmp/orbit_wars_v1_submission.py` with message `serious-v1 local readiness passed 4e66048`.
- [x] Kaggle accepted the upload with `Successfully submitted to Orbit Wars`.
- [x] Submission row verified: ref `53894832`, file `orbit_wars_v1_submission.py`, message `serious-v1 local readiness passed 4e66048`.
- [x] Reviewer verified the row via non-upload submissions list and observed it had progressed to `SubmissionStatus.COMPLETE` with public score `569.1`; a later non-upload score check showed current public score `429.2`.
- [x] Recorded final artifact size `316055` bytes and SHA256 `b05984e62d14190cf937c0b749862304e4a67a28e822c901fd47a7fbc57cc514`.
- [x] Updated `docs/live-submission-v1.md` with the live record and `LIVE_SUBMISSION_V1_SEGMENT_COMPLETE`.
- [x] Reviewer confirmed no second upload occurred and committed only `docs/live-submission-v1.md`.
- Commit: `313c0c4 Record V1 live submission`.

### Live Submission V1 Cycle 3: Post-Submit Verification Commit

Status: folded into Cycle 2 review/commit.

- [x] Reviewer reviewed and committed only the V1 live-submission runbook/status update during Cycle 2 review.
- [x] No credentials, generated artifacts, reports, logs, or `/tmp` files were staged.
- [x] `LIVE_SUBMISSION_V1_SEGMENT_COMPLETE` was recorded in the runbook after accepted submission and doc commit.

## Segment 15: Live Feedback Intake V1

Status: paused by user instruction. Do not continue replay/result intake unless the user explicitly reopens this segment.

Purpose: capture V1 live Kaggle status/replays, compare against V0 replay findings, and identify evidence-backed next improvement candidates without tuning or submitting again.

Segment completion sentinel: `LIVE_FEEDBACK_INTAKE_V1_SEGMENT_COMPLETE`.

### Live Feedback Intake V1 Cycle 0: V1 Live Results And Replay Intake

Status: paused/cancelled before implementation.

- [x] Goal prompt issued after Live Submission V1 completion commit `313c0c4 Record V1 live submission`.
- [x] Target submission ref: `53894832`.
- [x] Initial post-upload V1 live row was `SubmissionStatus.COMPLETE`, public score `569.1`; later score check reported current V1 score `429.2` and V0 score `419.2`.
- [x] Expected report path: `docs/submission_replay_analyses/ashxudev_orbit_wars_v1_submission/analysis.md`.
- [x] User explicitly instructed: do not do live feedback.
- [x] Implementation thread was interrupted and paused before replay/result intake work continued.
- [ ] Do not gather replay samples, write feedback reports, or commit feedback-intake artifacts unless the user explicitly reopens this segment.
- [ ] Do not make a live Kaggle submission or change planner/runtime/simulator/scoring/candidate-generation/action-conversion behavior.

## Segment 16: V1 Deterministic Leak Fix

Status: complete and committed through Cycle 12; segment readiness recorded.

Purpose: plug V1 replay leaks with deterministic fixtures, facts, candidate surfaces, and hard gates before autoresearch/scoring tuning.

Segment completion sentinel: `V1_DETERMINISTIC_LEAK_FIX_SEGMENT_COMPLETE`.

### V1 Deterministic Leak Fix Cycle 0: V1 Replay Regression Fixtures

Status: complete and committed.

- [x] Goal prompt issued after V1 deterministic leak-fix planning.
- [x] Kept scope characterization-only; no agent/planner/runtime/scoring/gate/submission behavior changed.
- [x] Added 10 compact single-observation fixtures under `tests/fixtures/v1_replay_leaks/`, not full replay dumps.
- [x] Added `tests/test_v1_replay_leak_fixtures.py`.
- [x] Added `docs/v1-deterministic-leak-fix.md`.
- [x] Covered 2P production-retention collapse episodes `80999800`, `80979989`, and `80987824`.
- [x] Covered own-transfer spam episodes `80991772` and `80986331`.
- [x] Covered enemy-denial absence episode `80989880`.
- [x] Covered 4P midgame plateau episodes `80984201`, `80981260`, and `80982912`.
- [x] Covered 4P capture-hold failure episode `80979440`.
- [x] Leak classes include `owned_production_threat_unanswered`, `own_transfer_spam`, `enemy_denial_absent`, `four_player_plateau`, and `thin_capture_recaptured`.
- [x] Reviewer verified focused V1/V0/runtime tests, compactness sanity, full discovery (`1257` tests), evaluation gate, `git diff --check`, and staged diff hygiene.
- Commit: `74a5791 Add V1 replay leak characterization fixtures`.

### V1 Deterministic Leak Fix Cycle 1: Owned Production Threat Facts

Status: complete and committed.

- [x] Goal prompt issued after Cycle 0 commit `74a5791 Add V1 replay leak characterization fixtures`.
- [x] Added deterministic owned-production threat facts without action selection or agent behavior changes.
- [x] Added fact API for owned planet id, owner/player id, current ships, production, incoming enemy/friendly pressure, earliest hostile ETA where available, projected balance, likely-flip/at-risk labels, production-bearing status, and source-drain context.
- [x] Recognized V1 production-retention fixtures as owned-production pressure/threat cases.
- [x] Preserved non-threat/control behavior so controls are not mislabeled as urgent flip cases.
- [x] Added/updated `ow_planner/owned_threats.py`, `ow_planner/__init__.py`, `tests/test_planner_owned_threats.py`, `tests/test_v1_replay_leak_fixtures.py`, and `docs/v1-deterministic-leak-fix.md`.
- [x] Reviewer verified focused validators, `scripts/evaluation_gate.py`, full discovery (`1267` tests), `git diff --check`, and import sanity that `ow_planner.owned_threats` does not import `kaggle_environments`.
- Commit: `1b968dd Add owned production threat facts`.

### V1 Deterministic Leak Fix Cycle 2: Owned Production Retention Selection

Status: complete and committed.

- [x] Goal prompt issued after Cycle 1 commit `1b968dd Add owned production threat facts`.
- [x] Used `owned_production_threat_facts(...)` so 2P selection protects visibly threatened owned production before ordinary expansion/attack options.
- [x] Preferred validated owned-retention actions such as `MissionType.REINFORCE` / `MissionType.DEFEND_OWN` and conservative `reserve_preserving` commitments when available.
- [x] Avoided expansion/attack/capture choices that drain or ignore threatened production when a safer validated retention option exists.
- [x] Updated V1 fixture expectations only where intended: `two_p_production_retention_80979989_t084_p1.json` and `two_p_own_transfer_spam_80991772_t160_p0.json` now emit reserve-preserving retention actions under owned-production pressure.
- [x] Updated one V0 fixture/regression expectation in scope: `two_p_capture_hold_80763852_t131_p1.json` now emits a reserve-preserving retention action under the same owned-production pressure signal; the reviewer confirmed the negative-overage budget-blocked case remains separate.
- [x] Preserved no-pressure direct-advantage ordering, 4P behavior, opening fallback behavior, generated-submission parity, evaluation gate, and submission preflight.
- [x] Reviewer verified focused owned-threat/selector/runtime/V1 fixture tests, planner support tests, runtime support tests, submission/regression/official/parity tests, full discovery (`1272` tests), `scripts/evaluation_gate.py`, `scripts/submission_preflight.py`, `git diff --check`, and cached diff hygiene.
- Commit: `8a86f33 Add owned production retention selection`.

### V1 Deterministic Leak Fix Cycle 3: Own-Transfer Intent Facts

Status: complete and committed.

- [x] Goal prompt issued after Cycle 2 commit `8a86f33 Add owned production retention selection`.
- [x] Added deterministic own-transfer fact surface `ow_planner/own_transfers.py`.
- [x] Exported the new fact surface from `ow_planner/__init__.py`.
- [x] Identified in-flight friendly own-to-own transfers with source/target context, owner, ships, ETA/distance, production, current ships, pressure flags, and production-bearing labels.
- [x] Classified purposeful retention/reinforcement transfers separately from potentially spammy/wasteful own-to-own movement.
- [x] Kept the cycle observability-only: no runtime behavior/action expectation, selector, scoring, candidate, action-conversion, preflight, gate, bundling, or Kaggle behavior changed.
- [x] Added `tests/test_planner_own_transfers.py` and V1 fixture fact assertions in `tests/test_v1_replay_leak_fixtures.py`.
- [x] Added Cycle 3 note in `docs/v1-deterministic-leak-fix.md`.
- [x] Reviewer verified focused own-transfer/V1 fixture/supporting planner/runtime tests (`88` tests), full discovery (`1281` tests), import sanity (`kaggle_loaded False`), `scripts/evaluation_gate.py`, `scripts/submission_preflight.py`, `git diff --check`, and cached diff hygiene.
- Commit: `44b6372 Add own transfer intent facts`.

### V1 Deterministic Leak Fix Cycle 4: Own-Transfer Spam Reduction Selection

Status: complete and committed.

- [x] Goal prompt issued after Cycle 3 commit `44b6372 Add own transfer intent facts`.
- [x] Threaded `own_transfer_intent_facts(state)` into the two-player selector path alongside owned-production threat facts.
- [x] Added pressure-safe spam suppression that only runs when own-transfer facts show spammy activity and a productive non-transfer alternative exists.
- [x] Preserved Cycle 2 owned-production pressure behavior: purposeful `REINFORCE` / `DEFEND_OWN` or reserve-preserving retention remains possible under visible pressure.
- [x] Added direct selector coverage for spam suppression, no-spam control behavior, and owned-production pressure preservation.
- [x] Added runtime pipeline coverage proving both fact reports are injected.
- [x] Kept live own-transfer fixture behavior unchanged: `80991772` remains pressure-protected and `80986331` exposes no validated productive non-transfer alternative in its current bundle set.
- [x] Added Cycle 4 note in `docs/v1-deterministic-leak-fix.md`.
- [x] Reviewer verified focused planner/runtime tests (`226` tests), submission/regression/official/parity tests (`49` tests), full discovery (`1284` tests), `scripts/evaluation_gate.py`, `scripts/submission_preflight.py`, `git diff --check`, and cached diff hygiene.
- Commit: `fdb201c Add own transfer spam selection guard`.

### V1 Deterministic Leak Fix Cycle 5: Enemy Production Denial Opportunity Facts

Status: complete and committed.

- [x] Goal prompt issued after Cycle 4 commit `fdb201c Add own transfer spam selection guard`.
- [x] Added deterministic enemy-denial fact surface `ow_planner/enemy_denial.py`.
- [x] Exported `enemy_denial_opportunity_facts(...)` from `ow_planner/__init__.py`.
- [x] Identified opponent-owned production planets that are plausible denial targets.
- [x] Reported player/opponent ids, target id/owner/ships/production, owned source count/capacity, nearest owned source, distance/ETA, production-bearing flag, production/ship balance, plausible labels, and high-value labels.
- [x] Distinguished real denial opportunities from controls with no meaningful opponent production or no plausible source capacity.
- [x] Kept this cycle observability-only: no selection, candidate generation, scoring, commitment, runtime conversion, simulator, gate, preflight, bundling, or Kaggle behavior changed.
- [x] Added `tests/test_planner_enemy_denial.py` and V1 fixture characterization for `two_p_enemy_denial_absent_80989880_t200_p0.json`.
- [x] Added Cycle 5 note in `docs/v1-deterministic-leak-fix.md`.
- [x] Reviewer verified focused planner/V1/runtime tests, full discovery (`1293` tests), `scripts/evaluation_gate.py`, `scripts/submission_preflight.py`, Kaggle import sanity (`kaggle_loaded False`), `git diff --check`, and cached diff hygiene.
- Commit: `39a0416 Add enemy production denial facts`.

### V1 Deterministic Leak Fix Cycle 6: Enemy Production Denial Selection

Status: complete and committed.

- [x] Goal prompt issued after Cycle 5 commit `39a0416 Add enemy production denial facts`.
- [x] Threaded `EnemyDenialOpportunityReport` / `enemy_denial_opportunity_facts(...)` into the two-player selection path via `TwoPlayerSelectionConfig` and runtime planner.
- [x] Added denial-aware selection for validated high-value/plausible `MissionType.ATTACK_ENEMY` / opponent-production denial bundles.
- [x] Preserved safety ordering: owned-production retention, own-transfer spam filtering, and pressure/capture-hold safety stay ahead of enemy denial.
- [x] Own-transfer spam suppression can treat high-value enemy denial as a productive alternative where appropriate.
- [x] Live fixture `80989880` remains retention-selected because active likely-flip owned-production pressure legitimately blocks denial; safety precedence is tested and characterized.
- [x] Added direct selector tests, runtime pipeline tests, V1 fixture characterization, and docs note.
- [x] Reviewer verified focused selector/fact/V1 fixture tests, runtime planner/action/state tests, submission/evaluation parity group, full discovery (`1297` tests), `scripts/evaluation_gate.py`, `scripts/submission_preflight.py`, import sanity (`kaggle_loaded False`), `git diff --check`, and cached diff hygiene.
- Commit: `d5339c3 Add enemy production denial selection`.

### V1 Deterministic Leak Fix Cycle 7: Four-Player Plateau Opportunity Facts

Status: complete and committed.

- [x] Goal prompt issued after Cycle 6 commit `d5339c3 Add enemy production denial selection`.
- [x] Planner superseded the earlier tentative 2P denial-gate slot with a facts-only 4P plateau opportunity cycle.
- [x] Added planned fact surface `ow_planner/four_player_plateau.py` with frozen/slotted, JSON-safe plateau fact dataclasses and `four_player_plateau_facts(...)`.
- [x] Exported the new facts from `ow_planner/__init__.py`.
- [x] Characterized 4P player/opponent ids, owned planet count, owned production/ships, neutral/enemy production target counts, nearest plausible expansion/denial targets, plateau/underexpanded labels, and no-action versus action-emitting plateau distinctions.
- [x] Covered V1 plateau fixtures `80984201`, `80981260`, and `80982912`, including candidate-backed no-action plateau windows and an action-emitting plateau window.
- [x] Added direct fact tests, V1 fixture assertions, and Cycle 7 docs note.
- [x] Reviewer verified focused plateau/V1 fixture tests, 4P strategy/selection/runtime groups, runtime action/state tests, full discovery (`1305` tests), `scripts/evaluation_gate.py`, `scripts/submission_preflight.py`, import sanity (`kaggle_loaded False`), `git diff --check`, and cached diff hygiene.
- Commit: `6fa0fe2 Add four-player plateau opportunity facts`.

### V1 Deterministic Leak Fix Cycle 8: Four-Player Plateau No-Action Recovery

Status: complete and committed.

- [x] Goal prompt issued after Cycle 7 commit `6fa0fe2 Add four-player plateau opportunity facts`.
- [x] Use `four_player_plateau_facts(...)` to recover safe normal planner actions in true 4P candidate-backed plateau windows.
- [x] Thread planned `FourPlayerPlateauReport` through `FourPlayerSelectionConfig` and `agents/runtime_planner.py`.
- [x] Target `four_p_plateau_80981260_t060_p2.json` so it no longer reports `strategy_selection_no_action` and emits a legal runtime action through the normal pipeline.
- [x] Preserve action-emitting plateau fixture `four_p_plateau_80982912_t250_p0.json`.
- [x] Explicitly characterize `four_p_plateau_80984201_t240_p0.json` if it remains no-action because current live runtime dispatches it through 2P mode due only two active owners.
- [x] Implementation changed the target fixture to emit action `[[14, -0.1300173607969723, 1]]` through the normal planner path.
- [x] Reviewer verified focused 4P/runtime/V1 fixture tests, generated-submission/parity group (`49` tests), full discovery (`1308` tests), `scripts/evaluation_gate.py`, `scripts/submission_preflight.py`, import sanity (`kaggle_loaded False`), `git diff --check`, and staged diff hygiene.
- Commit: `f06299a Add four-player plateau recovery selection`.

### V1 Deterministic Leak Fix Cycle 9: 4P Rank / Leader / Swing Facts

Status: complete and committed.

- [x] Goal prompt issued after Cycle 8 commit `f06299a Add four-player plateau recovery selection`.
- [x] Add an observability-only deterministic planner fact surface for four-player rank, leader pressure, and swing-risk context.
- [x] Prefer new module `ow_planner/four_player_rank.py`, public exports, focused tests, V1 fixture characterization, and Cycle 9 docs note.
- [x] Facts should report owned planet count, production, ships/fleet ships, production/ship/planet rank, leader ids, deltas to leaders/rivals, and labels for leader pressure, rank-preservation pressure, underexpanded trailing, or swing opportunity.
- [x] Characterize V1 4P fixtures: `80982912` as action-emitting plateau needing rank/leader/swing context, `80984201` as declared-4P but live 2P-dispatched due active owners, and `80979440` as 4P swing/capture-risk context.
- [x] Added facts-only `ow_planner/four_player_rank.py`, exports, focused tests, V1 fixture characterization, and Cycle 9 docs note.
- [x] Reviewer verified focused rank/V1 fixture tests, 4P plateau/selection tests, runtime turn/actions/state adapter tests, full discovery (`1316` tests), `scripts/evaluation_gate.py`, `scripts/submission_preflight.py`, import sanity (`kaggle_loaded False`), `git diff --check`, and staged diff hygiene.
- Commit: `24ee4e0 Add four-player rank swing facts`.

### V1 Deterministic Leak Fix Cycle 10: 4P Continuation / Rank-Aware Selector Gate

Status: complete and committed.

- [x] Goal prompt issued after Cycle 9 commit `24ee4e0 Add four-player rank swing facts`.
- [x] Thread `FourPlayerRankReport` into the 4P runtime/selector path without changing 2P behavior.
- [x] Use Cycle 7 `FourPlayerPlateauReport` and Cycle 9 rank facts to avoid passive 4P plateau behavior.
- [x] Preserve normal 4P selection precedence when clearly eligible safe candidates exist.
- [x] Prefer validated productive continuation/swing/leader-pressure candidates over passive low-impact retention when plateau/rank facts show continuation pressure, leader pressure, underexpanded trailing, or swing opportunity.
- [x] Preserve conservative rank-preservation and catastrophic-risk behavior; do not force risky attacks past existing source-counterattack, third-party benefit, or commitment validation rules.
- [x] Keep `four_p_plateau_80981260_t060_p2.json` fixed from Cycle 8 and do not force `80984201` through fake live 4P dispatch.
- [x] Added selector/runtime patches, rank-aware selector tests, runtime pipeline tests, fixture note updates for `80982912` and `80979440`, and Cycle 10 docs note.
- [x] V1 fixture action counts and commitments remain unchanged; only rank-aware selection-note characterization changed for the active-4P cases.
- [x] Reviewer verified focused 4P rank/plateau/selection/V1 fixture tests, runtime planner/turn/actions/state tests, submission/evaluation/parity group (`49` tests), full discovery (`1319` tests), `scripts/evaluation_gate.py`, `scripts/submission_preflight.py`, import sanity (`kaggle_loaded False`), `git diff --check`, and staged diff hygiene.
- Commit: `2a59bbe Add rank-aware four-player continuation gate`.

### V1 Deterministic Leak Fix Cycle 11: V1 Replay Regression Harness

Status: complete and committed.

- [x] Goal prompt issued after Cycle 10 commit `2a59bbe Add rank-aware four-player continuation gate`.
- [x] Add deterministic local measurement infrastructure for the committed V1 replay leak fixtures.
- [x] Added planned `ow_eval/v1_replay_regression.py` harness with frozen/slotted report dataclasses, JSON-safe `to_dict()`, stable `summary_text`, fixture loading from `tests/fixtures/v1_replay_leaks/`, runtime execution through current agent path, and aggregate metrics.
- [x] Exported public API from `ow_eval/__init__.py`.
- [x] Added focused `tests/test_v1_replay_regression.py`.
- [x] Added Cycle 11 docs note.
- [x] Harness loads all 10 V1 compact fixtures and reports fixture/case/leak metadata, action/candidate/diagnostic/commitment/selection-note fields and leak-specific flags.
- [x] Aggregate metrics include total cases, live action/no-action counts, unresolved planner no-action count, reduced-active-owner caveat count, owned-pressure/own-transfer/enemy-denial/4P plateau/rank-aware/thin-capture counts.
- [x] Implementer reports summary: `v1_replay_regression cases=10 live_actions=9 live_no_actions=1 unresolved_planner_no_actions=0 reduced_active_owner_caveats=1 owned_pressure=8 own_transfer_spam=3 enemy_denial_safety_blocked=1 four_player_plateau_actions=3 four_player_plateau_no_actions=1 rank_aware_continuations=2 thin_capture_risks=2`.
- [x] Implementer verified focused V1 fixture/regression tests, four-player fact/selector tests, runtime tests, full discovery (`1328` tests), evaluation gate, submission preflight, import sanity (`kaggle_loaded False`), and `git diff --check`.
- [x] Planner/reviewer verified focused V1 replay/runtime/planner test groups, full discovery (`1328` tests), `scripts/evaluation_gate.py`, `scripts/submission_preflight.py`, import sanity (`kaggle_loaded False`), `git diff --check`, and staged diff hygiene.
- Commit: `411f6e0 Add V1 replay regression harness`.

### V1 Deterministic Leak Fix Cycle 12: Segment Readiness Report

Status: complete and committed.

- [x] Goal prompt issued after Cycle 11 commit `411f6e0 Add V1 replay regression harness`.
- [x] Kept scope docs-only/readiness-only with no behavior, planner, simulator, scoring, candidate-generation, action-conversion, gate, preflight, bundling, or Kaggle submission changes.
- [x] Updated `docs/v1-deterministic-leak-fix.md` with current checked HEAD, completed Cycles 0-11, V1 replay regression summary, remaining caveats, verifier results, smoke benchmarks, and next-work recommendation.
- [x] Direct V1 replay regression probe reports `v1_replay_regression cases=10 live_actions=9 live_no_actions=1 unresolved_planner_no_actions=0 reduced_active_owner_caveats=1 owned_pressure=8 own_transfer_spam=3 enemy_denial_safety_blocked=1 four_player_plateau_actions=3 four_player_plateau_no_actions=1 rank_aware_continuations=2 thin_capture_risks=2`.
- [x] Remaining known caveat recorded as declared-4P reduced-active-owner/live-2P-dispatch case, not a generic unresolved 4P selector leak.
- [x] Implementer recorded focused V1 fixture/regression tests (`22` tests), full discovery (`1328` tests), `scripts/evaluation_gate.py`, `scripts/submission_preflight.py`, `legacy-opponent-smoke` (`4` matches), `competitive-baseline-smoke` (`6` matches), and `git diff --check` as passing.
- [x] Implementer recommendation: V1 deterministic leak-fix segment is complete; next work should be live-submission readiness or a separate autoresearch/tuning segment.
- [x] Planner/reviewer verified replay summary, focused tests (`22` tests), full discovery (`1328` tests), evaluation gate, submission preflight, both smoke benchmark workflows under `/tmp`, `git diff --check`, and staged diff hygiene.
- [x] Segment completion sentinel recorded: `V1_DETERMINISTIC_LEAK_FIX_SEGMENT_COMPLETE`.
- Commit: `fd80611 Record V1 deterministic readiness`.

## Segment 17: Live Submission V2

Status: complete and committed through Cycle 1; V2 live submission accepted and scored.

Purpose: verify Kaggle submission mechanism, freeze a final V2 artifact after deterministic readiness, perform exactly one live upload, and record the result without committing generated artifacts or secrets.

Segment completion sentinel: `LIVE_SUBMISSION_V2_SEGMENT_COMPLETE`.

### Live Submission V2 Cycle 0: Final No-Submit Mechanism Check

Status: complete and committed.

- [x] Goal prompt issued after V1 deterministic readiness commit `fd80611 Record V1 deterministic readiness`.
- [x] Created/updated `docs/live-submission-v2.md` with a no-submit mechanism check.
- [x] Verified current HEAD, worktree status, Kaggle CLI path/version, non-upload competition access, credential/config presence without exposing secrets, and latest visible submissions list.
- [x] Confirmed no `.venv/bin/kaggle competitions submit` command was run.
- [x] Reviewer verified `.venv/bin/kaggle --version` as `Kaggle CLI 2.2.2`, read-only submissions-list access, latest serious row still V1 ref `53894832` with status `COMPLETE` and score `435.8`, no V2 row present, credential-presence check printed only booleans, `git diff --check`, and staged diff hygiene.
- Commit: `75867e3 Add V2 live submission mechanism check`.

### Live Submission V2 Cycle 1: Final Artifact Freeze, Readiness, And Exactly One Live Kaggle Upload

Status: complete and committed.

- [x] Goal prompt issued after Cycle 0 commit `75867e3 Add V2 live submission mechanism check`.
- [x] Required pre-submit checks passed before upload: read-only Kaggle submissions list, V1 replay fixture/regression tests (`22` tests), full discovery (`1328` tests), `scripts/evaluation_gate.py`, `scripts/submission_preflight.py`, direct V1 replay regression probe, and `git diff --check`.
- [x] Built fresh final artifact at `/tmp/orbit_wars_v2_submission.py` immediately before upload.
- [x] Recorded artifact metadata: `411942` bytes, SHA256 `1cc8143dbb06719c2a2cb858f4630b344746c5478b1a51aed99cd2f44d07a940`.
- [x] Invoked exactly one live upload command: `.venv/bin/kaggle competitions submit -c orbit-wars -f /tmp/orbit_wars_v2_submission.py -m "serious-v2 deterministic readiness passed 75867e3"`.
- [x] Kaggle accepted the upload as V2 submission ref `53925932`.
- [x] Implementer initially recorded post-submit status as `SubmissionStatus.PENDING`.
- [x] Reviewer read-only verification observed V2 ref `53925932` advanced to `SubmissionStatus.COMPLETE` with public score `600.0` and updated the runbook.
- [x] No generated artifact, secrets, credentials, reports, or unrelated files were committed.
- [x] Segment completion sentinel recorded: `LIVE_SUBMISSION_V2_SEGMENT_COMPLETE`.
- Commit: `8fccb48 Record V2 live submission`.

## Segment 18: Distributed Historical Champion Gauntlet

Status: complete and committed through `09158df Complete historical gauntlet handoff`; final sentinel `HISTORICAL_CHAMPION_GAUNTLET_COMPLETE` recorded. A cross-cutting artifact-capture-by-default change remains in progress so future local/Daytona sim matches retain replay/result artifacts automatically.

Purpose: run current V2 against strong historical 800+ agents in full 500-step official-environment matches, sharded across Daytona, then merge results and extract deterministic leak evidence.

Segment completion sentinel: `HISTORICAL_CHAMPION_GAUNTLET_SEGMENT_COMPLETE`.

Planning assessment:

- [x] Planner agrees that a serious historical-agent gauntlet would likely have surfaced many V1 deterministic leaks earlier.
- [x] User clarified the gauntlet should use Daytona sandboxes for parallelism and full 500-step matches; local runs should be tiny probes only.
- [x] Historical agents are adversarial evaluators, not source material or design templates.
- [x] Evidence collection is separate from fixing/tuning; deterministic fixture extraction and autoresearch decisions happen in later cycles/segments.

### Distributed Historical Champion Gauntlet Cycle 0: Champion Opponent Registry

Status: complete and committed.

- [x] Goal prompt issued after Live Submission V2 completion.
- [x] Inventory historical candidates from `orbit-wars-claude`, `orbit-wars`, and `orbit-wars-2`.
- [x] Add source-controlled registry at `experiments/historical_champions/registry.json`.
- [x] Record stable opponent name, source repo, absolute `python_file` path, callable name, historical submission ref/public score where known, intended modes, loadability status, and skip reason for unusable candidates.
- [x] Add docs in `docs/historical-champion-gauntlet.md` and focused registry tests.
- [x] Reviewer verified the registry has `11` loadable historical opponents and `3` skipped candidates with explicit skip reasons.
- [x] No historical source code was copied; no matches or Daytona jobs were run.
- Commit: `f97e335 Add historical champion registry`.

### Distributed Historical Champion Gauntlet Cycle 1: Full-Horizon Gauntlet Scenario Matrix

Status: complete and committed.

- [x] Goal prompt issued after Cycle 0 commit `f97e335 Add historical champion registry`.
- [x] Add full-horizon source-controlled manifests:
  - `experiments/manifests/historical-champion-gauntlet-2p-500.json`
  - `experiments/manifests/historical-champion-gauntlet-4p-500.json`
- [x] Include only loadable registry entries as external `python_file` opponents.
- [x] Set every scenario `metadata.episode_steps` to `"500"`.
- [x] Cover 2P scenarios across both candidate seats and deterministic 4P champion pools.
- [x] Add manifest tests and docs updates.
- [x] Reviewer verified `22` two-player scenarios and `8` four-player scenarios, `30` total full-500 scenarios, and `11` unique loadable opponents via no-match parse/loadability probe.
- [x] No matches, Daytona jobs, Kaggle commands, reports, or generated results were run/created.
- Commit: `0ac3e2d Add historical champion gauntlet manifests`.

### Distributed Historical Champion Gauntlet Cycle 2: Local Full-500 Micro-Probe

Status: complete and committed.

- [x] Goal prompt issued after Cycle 1 commit `0ac3e2d Add historical champion gauntlet manifests`.
- [x] Run a tightly bounded local official-environment probe against selected committed 500-step gauntlet scenarios.
- [x] Use temporary one-scenario manifests under `/tmp`; preserve `episode_steps="500"`.
- [x] Run one 2P full-500 scenario: `historical-gauntlet-2p-500-seat-0-vs-claude-v3-wide-search-forecast`, seed `7210`, seat `0`, opponent `claude-v3-wide-search-forecast`.
- [x] Run one 4P full-500 scenario: `historical-gauntlet-4p-500-top-score-seat-0`, seed `8100`, seat `0`, opponents `claude-v3-wide-search-forecast`, `claude-v28-mode-split-champion`, and `claude-v37-race-fix-mode-split`.
- [x] Both probes completed with `normal_loss`, `error_count=0`; reported runtimes were `21.21s` for 2P and `31.16s` for 4P.
- [x] Generated probe manifests/reports were written only under `/tmp`.
- [x] Implementer updated `docs/historical-champion-gauntlet.md`; no full gauntlet, Daytona job, Kaggle command, or behavior change was made.
- [x] Planner/reviewer verified selected probes preserved `episode_steps="500"`, `/tmp` reports completed with `error_count=0`, generated artifacts stayed under `/tmp`, and only docs were committed.
- Commit: `76cdd7f Record historical champion micro-probe`.

### Distributed Historical Champion Gauntlet Cycle 3: Daytona Shard Plan Generation

Status: complete and committed.

- [x] Goal prompt issued after Cycle 2 commit `76cdd7f Record historical champion micro-probe`.
- [x] Added deterministic shard planning for the two full-500 historical champion manifests.
- [x] Assigned all `30` scenarios exactly once across `6` shards.
- [x] Preserved every planned scenario at `episode_steps="500"`.
- [x] Added JSON-safe deterministic shard records with shard ids, manifest names, scenario labels, seeds, seats, player counts, opponent names, and intended output paths.
- [x] Added/updated `ow_eval/historical_gauntlet_shards.py`, `tests/test_historical_champion_gauntlet_shards.py`, and `docs/historical-champion-gauntlet.md`.
- [x] Reviewer verified direct generation probe: `6` shards, `30` total scenarios, `30` unique labels, all `episode_steps == "500"`.
- [x] No gauntlet matches, Daytona jobs, Kaggle commands, or generated result artifacts were run or created.
- Commit: `f7be3c6 Add historical champion shard plan`.

### Distributed Historical Champion Gauntlet Cycle 4: Daytona Package Compatibility

Status: complete and committed.

- [x] Goal prompt issued after Cycle 3 commit `f7be3c6 Add historical champion shard plan`.
- [x] Added package/materialization support so the recommended probe shard `historical-gauntlet-shard-000` can become a package-ready local structure.
- [x] Package-ready structure includes shard id, source manifest references, selected scenario labels/seeds, planned manifest path, planned report/result paths, and command template.
- [x] Independent `/tmp` materialization probe confirmed exactly `5` assigned shard-000 scenarios, all with `episode_steps=500`.
- [x] No report/shard-result files were created by the materialization probe.
- [x] Added/updated `ow_eval/historical_gauntlet_shards.py`, `tests/test_evaluation_shard_manifest_materializer.py`, `tests/test_historical_champion_gauntlet_packages.py`, and docs.
- [x] No match execution, Daytona launch, Kaggle command, replay, or live result artifact was created/committed.
- Commit: `e410748 Add historical champion package adapter`.

### Distributed Historical Champion Gauntlet Cycle 5: Daytona Single-Shard Full-500 Probe

Status: complete and committed; real execution path dry-validated, real Daytona blocked by readiness.

- [x] Goal prompt issued after Cycle 4 commit `e410748 Add historical champion package adapter`.
- [x] Materialized only `historical-gauntlet-shard-000` under `/tmp`.
- [x] Package contained exactly one job for the five shard-000 scenarios, all with `episode_steps=500`.
- [x] Converted package index to a Daytona job plan with exactly one job/spec for shard-000.
- [x] Daytona preflight/plan validation passed.
- [x] Fake/dry Daytona executor passed.
- [x] Real Daytona readiness was documented as blocked by `allow_real_daytona=False` and missing `DAYTONA_API_KEY`; no guarded real command was run.
- [x] Generated package/plan/dry-run files stayed under `/tmp`.
- [x] No full gauntlet, multi-shard pilot, Kaggle command, live submission, or unrelated evaluation run occurred.
- Commit: `e8eaa35 Record historical champion Daytona probe path`.

### Distributed Historical Champion Gauntlet Cycle 6: Guarded Real Daytona Single-Shard Probe

Status: complete and committed; confirmed blocker remains environment readiness.

- [x] Planner re-scoped Cycle 6 as `Guarded Real Daytona Single-Shard Probe`, not multi-shard pilot, because Cycle 5 established the dry path but real readiness was blocked.
- [x] Rebuilt only `historical-gauntlet-shard-000` under `/tmp/ow-historical-gauntlet-cycle6-real-shard-000/`.
- [x] Confirmed exactly `5` selected scenarios, all with `episode_steps=500`.
- [x] Generated and validated exactly one Daytona job/spec for shard-000.
- [x] Fake/dry Daytona validation passed before any real attempt.
- [x] Real Daytona readiness remained blocked by `allow_real_daytona=False` and missing `DAYTONA_API_KEY`; no real Daytona command was run.
- [x] Reviewer independently rebuilt the package/plan, verified one spec covering five shard-000 scenarios, dry-run pass, readiness block, focused tests, and docs-only committed scope.
- Commit: `0a64dd1 Record guarded Daytona readiness`.

### Distributed Historical Champion Gauntlet Prerequisite: Daytona Environment / SDK Setup

Status: complete and committed as part of Cycle 7 setup consolidation.

- [x] User paused gauntlet progression to set up Daytona before continuing.
- [x] Planner confirmed current repo already has `python-dotenv` but not an importable `daytona` package.
- [x] Official Daytona docs confirmed Python SDK config reads `DAYTONA_API_KEY`, `DAYTONA_API_URL`, and `DAYTONA_TARGET`; old project pattern also used `GITHUB_TOKEN` for private-repo clone bootstrap.
- [x] Current setup decision: `DAYTONA_API_KEY` and explicit allow flag remain the hard real-execution gate; `GITHUB_TOKEN` is required only for clone/bootstrap mode, not snapshot/image mode.
- [x] Snapshot/image path chosen over private-repo clone bootstrap for the gauntlet; `GITHUB_TOKEN` remains optional for clone/bootstrap mode only.
- [x] Installed official Daytona SDK locally as `daytona==0.189.0`.
- [x] Added `.env` loading, `.env.example`, `.gitignore` `.env` ignore, docs, and tests; planner reported full discovery green at `1367` tests during setup.
- [x] Created Daytona runtime snapshot `ow-serious-runtime-0a64dd17d867` with `277` source files and `153` requirements.
- [x] User added `DAYTONA_SNAPSHOT_ID=ow-serious-runtime-0a64dd17d867` to `.env`.
- [x] Added and verified official SDK adapter and snapshot sandbox creation path; planner reported `Daytona auth: OK`, snapshot readiness `READY`, and full discovery green at `1376` tests.
- [x] Historical gauntlet shard package is now self-contained: copies historical `python_file` opponents into the `/tmp` package and rewrites manifest paths.
- [x] Generated real probe plan at `/tmp/ow-historical-gauntlet-real-probe/daytona-shard-jobs.json` for `historical-gauntlet-shard-000`, five full-500 scenarios, and eight uploads.
- [x] Probe plan validation passed and fake Daytona dry-run passed before real execution.
- [x] User explicitly approved exporting the one-shard package and historical agent files to Daytona and executing the remote shard probe.
- [x] Real Daytona one-shard probe initially exposed a long synchronous `process.exec` proxy disconnect during full-500 work.
- [x] Added a guarded real-Daytona smoke diagnostic to distinguish auth/snapshot/process-start failures from long-worker transport failures.
- [x] Real smoke passed, proving Daytona auth, snapshot creation, working directory, `.venv`, `ow_eval` import, sandbox open, process execution, and cleanup for a tiny command.
- [x] Diagnosed the long-run failure as the official SDK adapter holding a synchronous HTTP request open via `sandbox.process.exec(...)`.
- [x] Switched long commands to Daytona sessions: create session, start command with `run_async=True`, poll status, fetch logs, and delete session.
- [x] Session-based real smoke passed.
- [x] Session-based real single-shard full-500 probe completed and downloaded results.
- [x] Captured real Daytona probe report at `/tmp/ow-historical-gauntlet-real-probe/daytona-real-report-session.json`.
- [x] Captured shard result at `/tmp/ow-historical-gauntlet-real-probe/historical-gauntlet-shard-000/historical-gauntlet-shard-000.shard-result.json`.
- [x] Planner reported focused Daytona tests, `git diff --check`, and full discovery `1386` tests passing after the session adapter change.
- [x] Reviewed and committed setup/probe/tooling changes as `2721538 Consolidate Daytona gauntlet setup`.
- [x] Planner decided the next cycle should prepare the full six-shard package and Daytona dry-run plan before any real full-gauntlet execution.

### Distributed Historical Champion Gauntlet Cycle 7: Real Daytona Single-Shard Probe Completion

Status: complete and committed as `2721538 Consolidate Daytona gauntlet setup`.

- [x] User approved remote export and execution.
- [x] Run exactly one shard: `historical-gauntlet-shard-000`.
- [x] Scope is five full-500 scenarios, not the full gauntlet.
- [x] Upload package includes job JSON, manifest JSON, and six copied historical agent files.
- [x] Synchronous full-shard run failed with a Daytona proxy disconnect while waiting on long `process.exec`.
- [x] Session-based Daytona runner completed `daytona_real_cli=COMPLETE`.
- [x] Exactly one job/spec executed with `jobs=1`, `events=24`, `operation_plans=1`, and `exit_code=0`.
- [x] Daytona sandbox result downloaded to `/tmp`.
- [x] Shard result completed five full-500 matches with `errors=0`.
- [x] Competitive outcome: current V2 lost all five shard-000 matches; mean final rank `2.0`, mean final score `-1.0`.
- [x] Outcome recorded in planner-thread summary and Daytona runbook notes.
- [x] Commit or blocker decision recorded.
- Commit: `2721538 Consolidate Daytona gauntlet setup`.

### Distributed Historical Champion Gauntlet Cycle 8: Full-Gauntlet Package Materialization And Daytona Plan Dry-Run

Status: complete and committed as `6fd0d2e Add full historical gauntlet package prep`.

- [x] Goal prompt issued after Cycle 7 commit `2721538 Consolidate Daytona gauntlet setup`.
- [x] Extend historical gauntlet packaging from the single probe shard to the full six-shard, 30-scenario package.
- [x] Add/extend full package APIs in `ow_eval/historical_gauntlet_shards.py`.
- [x] Add CLI wrapper `scripts/prepare_historical_champion_gauntlet_package.py`.
- [x] Keep old single-shard probe API intact.
- [x] Export new full-package helpers from `ow_eval.__init__`.
- [x] Add focused package tests for six shards, 30 scenarios, package-local opponent files, and Daytona upload expectations.
- [x] Document Cycle 8 full-package/dry-run workflow and no-real-execution boundary.
- [x] Materialized full package under `/tmp/ow-historical-gauntlet-full-package`.
- [x] Verified package contains `6` shards and `30` scenarios; each shard has `5` scenarios; every packaged scenario keeps `episode_steps=500`.
- [x] Verified historical `python_file` opponents are copied into package-local `agent_files/` paths under `/tmp`, not the repo.
- [x] Generated Daytona plan with `6` jobs.
- [x] Daytona validation passed with no missing upload paths or duplicate sandbox names.
- [x] Fake/dry Daytona executor passed with `jobs=6`, `exit_code=0`.
- [x] Focused package/shard tests passed: `16` tests.
- [x] Focused Daytona/shard infrastructure tests passed: `66` tests.
- [x] Optional parallel full local confidence passed: `111` modules, `0` failures.
- [x] `git diff --check` passed.
- [x] No real Daytona command, local full-gauntlet matches, Kaggle command, or live submission was run.
- [x] Narrow blocker fix included: remove/guard the broken `--no-materialize-manifests` path so old reproduction fails cleanly at argparse instead of `FileNotFoundError`.
- [x] Planner/reviewer reviewed and committed Cycle 8 as `6fd0d2e Add full historical gauntlet package prep`.
- Commit: `6fd0d2e Add full historical gauntlet package prep`.

### Distributed Historical Champion Gauntlet Cycle 9: Guarded Real Daytona Full-Gauntlet Run

Status: complete as environment-blocked and committed as `2c8bca1 Record historical gauntlet Daytona block`; no full real gauntlet results exist from this cycle.

- [x] Goal prompt issued after Cycle 8 commit `6fd0d2e Add full historical gauntlet package prep`.
- [x] HEAD confirmed: `6fd0d2e Add full historical gauntlet package prep`.
- [x] Full package materialized under `/tmp/ow-historical-gauntlet-cycle9-full-real`.
- [x] Package contained `6` jobs and `30` unique scenarios, all `episode_steps=500`.
- [x] Daytona plan generated with `jobs=6`.
- [x] Daytona validation passed: `specs=6`, `missing_upload_paths=0`, `duplicate_sandbox_names=0`.
- [x] Local dry-run passed: `jobs=6`, `exit_code=0`.
- [x] Guarded real Daytona smoke passed with readiness `READY`, `diagnosis=smoke_passed`, and `daytona_smoke=OK`.
- [x] Full six-shard real Daytona run did not execute because the environment approval layer rejected the command before OS execution due to external upload/transfer risk for repo-derived manifests, job specs, and packaged historical agent source files.
- [x] No shard results were downloaded and no full-gauntlet match results exist from Cycle 9.
- [x] No Kaggle command or live submission was run.
- [x] Raw generated package, plans, reports, logs, scoreboards, replays, and client reports remained `/tmp` artifacts and were not committed.
- [x] Docs-only status update reviewed and committed.
- Commit: `2c8bca1 Record historical gauntlet Daytona block`.

### Distributed Historical Champion Gauntlet Cycle 10: Real Run Completion Audit

Status: complete and committed as `3f5474f Record historical gauntlet real run completion`.

- [x] Confirmed `/tmp/ow-historical-gauntlet-cycle9-full-real/daytona-shard-jobs.json` exists.
- [x] Confirmed Daytona plan validation passes with `6` specs, no missing uploads, and no duplicate sandbox names.
- [x] Confirmed real Daytona readiness is `READY`.
- [x] Confirmed `GITHUB_TOKEN` is not required for this path.
- [x] User ran the guarded full-gauntlet Daytona command locally:
  `.venv/bin/python scripts/run_daytona_real_shard_jobs.py /tmp/ow-historical-gauntlet-cycle9-full-real/daytona-shard-jobs.json --allow-real-daytona --json-output /tmp/ow-historical-gauntlet-cycle9-full-real/daytona-real-report.json`
- [x] Planner issued Cycle 10 as Real Run Completion Audit after detached Daytona gauntlet completion.
- [x] Implementation thread is auditing `/tmp/ow-historical-gauntlet-cycle9-full-real/daytona-real-report.json` read-only.
- [x] Known report facts: `passed=True`, `exit_code=0`, summary includes `jobs=6`, `events=144`, `operation_plans=6`, `exit_code=0`.
- [x] Confirmed `batch_result.execution_results` count is `6`.
- [x] Confirmed `batch_result.shard_result_paths` count is `6`.
- [x] Confirmed shard result files exist for `historical-gauntlet-shard-000` through `historical-gauntlet-shard-005`.
- [x] Implementation read-only audit confirms `6/6` shard results, `30/30` matches, and `0` shard execution errors.
- [x] Updated `docs/historical-champion-gauntlet.md` with Cycle 10 real-run completion note.
- [x] Planner/reviewer reviewed and committed docs-only audit.
- [x] Raw generated artifacts stayed out of git.
- Commit: `3f5474f Record historical gauntlet real run completion`.

### Distributed Historical Champion Gauntlet Cycle 11: Merge, Scoreboard, And Per-Opponent Report

Status: complete and committed as `1af3bc9 Summarize historical gauntlet merged results`.

- [x] Merge shard outputs into aggregate scoreboard/report artifacts under `/tmp`.
- [x] Summarize completed historical gauntlet results in docs.
- [x] Result coverage: `30/30` scenarios completed.
- [x] Execution quality: `0` errors, `0` invalid actions, `0` timeouts.
- [x] Aggregate competitive result: win rate `0.0`, mean final rank `2.0`, rank distribution `{"2": 30}`.
- [x] Behavioral pressure signal: no-action count `2569`, mean turns survived `153.7`.
- [x] Reported result splits and per-opponent/per-family surfaces for triage.
- Commit: `1af3bc9 Summarize historical gauntlet merged results`.

### Distributed Historical Champion Gauntlet Cycle 12: Loss And Leak Triage

Status: complete and committed as `9a57e94 Triage historical gauntlet losses`.

- [x] Analyze completed 30-match historical champion gauntlet results without changing agent behavior.
- [x] Recompute triage values from `/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-merged-report.json`.
- [x] Verify aggregate metrics, split tables, shortest-loss rows, highest no-action rows, and diagnostic reason counts.
- [x] Classify recurring loss patterns into deterministic leak candidates versus autoresearch/tuning surfaces.
- [x] Identify concrete Cycle 13 candidate cases for fixture extraction, all present in the merged report and retaining `episode_steps=500`.
- [x] Commit intended docs-only triage update.
- Commit: `9a57e94 Triage historical gauntlet losses`.

### Distributed Historical Champion Gauntlet Cycle 13: Compact Failure Fixture Extraction

Status: complete and committed as `6007b96 Add historical gauntlet leak fixtures`.

- [x] Goal prompt issued after Cycle 12 commit `9a57e94 Triage historical gauntlet losses`.
- [x] Initial implementation found a real blocker: merged gauntlet outputs had only match-level summaries, with `artifact_path=null` and `replay_path=null` for all six candidate cases.
- [x] Planner diagnosed cause: artifact capture was opt-in, and the historical Daytona shard path ran without `EvaluationArtifactConfig`, so compact fixtures could not be derived from real source observations.
- [x] Planner instructed a fix plan: rerun exactly six selected full-500 scenarios locally with replay/result artifacts enabled under `/tmp`, then extract compact fixtures from real replay payloads.
- [x] Implementation reran exactly the six selected scenarios locally with artifact capture under `/tmp/ow-historical-gauntlet-cycle13-artifacts`.
- [x] Local artifact rerun completed successfully.
- [x] Replay artifacts contain standard Kaggle `steps` payloads.
- [x] Compact fixture candidates selected: three 2P no-candidate collapse cases, one 4P candidate-backed strategy no-action case, and two 4P late pressure/collapse cases tied to budget-heavy and OW2-reference scenarios.
- [x] Compact fixture JSON generated under `tests/fixtures/historical_gauntlet_leaks/`.
- [x] Fixture metadata patched to map source cases back to concrete `historical-gauntlet-shard-00N` records.
- [x] Added focused test module `tests/test_historical_gauntlet_leak_fixtures.py`.
- [x] Docs updated to replace earlier blocker note with artifact-enabled local rerun and fixture extraction coverage.
- [x] New fixture test, `/tmp` source verification, runtime smoke tests, and V1 replay fixture/regression group passed.
- [x] `git diff --check` and compact-fixture sanity probe passed.
- [x] `scripts/evaluation_gate.py` completed before review/commit.
- [x] Planner/reviewer reviewed and committed fixtures/docs/tests.
- Commit: `6007b96 Add historical gauntlet leak fixtures`.

### Distributed Historical Champion Gauntlet Cycle 14: Segment Decision Report

Status: complete and committed as `09158df Complete historical gauntlet handoff`.

- [x] Added final segment completion section to `docs/historical-champion-gauntlet.md`.
- [x] Recorded sentinel `HISTORICAL_CHAMPION_GAUNTLET_COMPLETE`.
- [x] Recorded Daytona full-gauntlet completion evidence.
- [x] Recorded Cycle 10-13 completion chain.
- [x] Recorded committed compact fixture evidence under `tests/fixtures/historical_gauntlet_leaks/`.
- [x] Added prioritized deterministic fix queue for 2P collapse, 2P control pressure, 4P plateau/rank pressure, and 4P budget-heavy windows.
- [x] Focused fixture test passed: `7` tests.
- [x] Docs diff check passed.
- [x] Only `docs/historical-champion-gauntlet.md` was committed.
- Commit: `09158df Complete historical gauntlet handoff`.

## Segment 19: Historical Gauntlet Deterministic Leak Fix

Status: Cycle 0 complete and committed as `54b0974 Record historical leak baseline`; Cycle 1 implemented in the implementation thread and under planner/reviewer review, with no Cycle 1 commit observed yet.

Objective: fix deterministic 2P and 4P leak classes exposed by the historical champion gauntlet, then verify with exactly one full-500 2P Daytona match and one full-500 4P Daytona match against historical agents.

Segment completion sentinel: `HISTORICAL_LEAK_FIX_DAYTONA_PROBE_COMPLETE`.

### Historical Gauntlet Deterministic Leak Fix Cycle 0: Baseline Characterization

Status: complete and committed.

- [x] Planner issued Cycle 0 as baseline characterization, scoped to docs/characterization only.
- [x] Added baseline note in `docs/historical-gauntlet-deterministic-leak-fix.md`.
- [x] Re-ran committed compact historical gauntlet leak fixtures locally.
- [x] Recorded current diagnostics for each fixture: action count, emitted action summary, runtime diagnostic/no-action reason, candidate count, budget guard status, and selected strategy/commitment/mission details where exposed.
- [x] Classified fixture failure classes, including 2P candidate starvation and 4P candidate-backed plateau/rank-pressure cases.
- [x] Made no behavior changes.
- [x] Produced before/after baseline for later 2P early collapse and 4P plateau fixes.
- [x] Commit: `54b0974 Record historical leak baseline`.

### Historical Gauntlet Deterministic Leak Fix Cycle 1: 2P Early Collapse Candidate Recovery

Status: implemented in the implementation thread and under planner/reviewer review; no commit observed yet.

- [x] Goal prompt issued after baseline commit `54b0974 Record historical leak baseline`.
- [x] Added bounded early 2P pressure-recovery candidate generation in `ow_planner/candidates.py`.
- [x] Gated recovery to cases where normal validated candidates are empty, `state.step <= 10`, active owners are 2P-like, and the player has at most one owned planet.
- [x] Uses existing ordered source-target pairs and simulator-backed outcome validation; no runtime-only fallback or fixture-specific hardcoding.
- [x] Keeps validation bounded through existing `max_candidates`, `max_validation_attempts`, and affordability/reserve-preserving checks.
- [x] Tightened implementation during verification for `step=None` synthetic states and late reduced-active-owner 4P fixtures.
- [x] Updated focused historical fixture expectations and planner-generation tests.
- [x] Updated `docs/historical-gauntlet-deterministic-leak-fix.md` with Cycle 1 before/after results.
- [x] Target fixture `two_p_collapse_claude_v31_t002_p1.json` now emits runtime action `[[23, 2.3330067382197486, 5]]`, with `8` runtime-capped candidates and `reserve_preserving` status.
- [x] Target fixture `two_p_collapse_claude_v9_t001_p1.json` now emits runtime action `[[7, 2.8808254788103143, 4]]`, with `8` runtime-capped candidates and `reserve_preserving` status.
- [x] Focused historical fixture tests passed.
- [x] Focused planner generation/enumeration/estimation tests passed.
- [x] Focused runtime state/turn/actions tests passed.
- [x] `scripts/evaluation_gate.py` passed in implementation thread.
- [x] `scripts/submission_preflight.py` passed in implementation thread.
- [x] `git diff --check` passed.
- [ ] Planner/reviewer readiness scripts completion and final review.
- [ ] Cycle 1 commit or blocker decision.

Known Cycle 1 review note:

- [ ] Full discovery reported two Daytona/client-report assertion failures about event trace/download counts. Current evidence points to unrelated dirty artifact-default work, not the planner candidate-recovery change.

### Historical Gauntlet Deterministic Leak Fix Cycle 2: 2P Control-Pressure Selection

Status: planned.

- [ ] Ensure selector chooses a conservative legal response once candidates exist under early pressure.
- [ ] Prefer retention/defense/production-preserving moves over low-value expansion when pressure facts indicate collapse risk.
- [ ] Targeted 2P historical fixtures should emit legal actions with pressure-aware diagnostics.

### Historical Gauntlet Deterministic Leak Fix Cycle 3: 4P Plateau Selector Recovery

Status: planned.

- [ ] Fix 4P candidate-backed `strategy_selection_no_action`.
- [ ] Add rank/leader/swing continuation logic where candidates exist but selection currently rejects all.
- [ ] 4P plateau fixture with existing candidates should emit at least one legal action without weakening 2P behavior.

### Historical Gauntlet Deterministic Leak Fix Cycle 4: 4P Budget-Pressure Split

Status: planned.

- [ ] Separate true budget exhaustion from avoidable 4P selection failure.
- [ ] Add diagnostics/tests proving whether no-action is due to budget guard, no candidates, or selector rejection.
- [ ] Only fix avoidable selector rejection; preserve real budget guard safety.

### Historical Gauntlet Deterministic Leak Fix Cycle 5: Regression Harness Update

Status: planned.

- [ ] Extend historical gauntlet fixture harness to summarize fixed/not-fixed status.
- [ ] Track action rate, unresolved planner no-actions, budget-blocked no-actions, candidate-backed no-actions, and fixture class outcomes.

### Historical Gauntlet Deterministic Leak Fix Cycle 6: Daytona 2P Probe

Status: planned.

- [ ] Materialize one full-500 Daytona 2P scenario against a representative historical champion.
- [ ] Run exactly one 2P match with artifact capture enabled.
- [ ] Success is no recurrence of fixed deterministic leak class, not necessarily a win.

### Historical Gauntlet Deterministic Leak Fix Cycle 7: Daytona 4P Probe

Status: planned.

- [ ] Materialize one full-500 Daytona 4P scenario using a representative plateau/rank-pressure setup.
- [ ] Run exactly one 4P match with artifact capture enabled.
- [ ] Success is no candidate-backed no-action plateau and no unexplained budget-heavy strategy failure.

### Historical Gauntlet Deterministic Leak Fix Cycle 8: Probe Analysis And Handoff

Status: planned.

- [ ] Summarize local fixture results plus both Daytona probe outcomes.
- [ ] If both probe matches are clean, mark segment complete.
- [ ] If either probe exposes a new deterministic leak, extract compact fixtures and plan the next focused fix segment.
- [ ] Commit only docs/fixtures/tests, not raw Daytona artifacts.

### Autoresearch Deferred Until Deterministic Surfaces Exist

- [ ] Tune scoring weights in `ow_planner/scoring.py`.
- [ ] Tune 2P strategy and selection in `ow_planner/two_player_strategy.py` and `ow_planner/two_player_selection.py`.
- [ ] Tune 4P strategy, selection, and mission generation in `ow_planner/four_player_strategy.py`, `ow_planner/four_player_selection.py`, and `ow_planner/four_player_missions.py`.
- [ ] Tune configurable surfaces in `ow_planner/commitment.py` and `ow_planner/response.py`.

## Cross-Cutting Tooling / Test Throughput

Status: complete and committed as part of `2721538 Consolidate Daytona gauntlet setup`.

- [x] Planner recommended against using Daytona as the default full-discovery test runner.
- [x] Recommended local timing/profiling, test tiers, and a local parallel unittest runner first.
- [x] Added local unittest helper tooling in `ow_eval/local_tests.py`.
- [x] Added `scripts/run_tests_parallel.py` and `scripts/profile_tests.py`.
- [x] Added tests and evaluation-harness docs updates.
- [x] Full local parallel module run passed: `111` modules, `0` failures, `293.176s`.
- [x] Main remaining local-test bottleneck identified: `tests.test_evaluation_parity` at about `289s`.
- [x] Reviewed and committed with the scoped Cycle 7 Daytona setup consolidation.

## Cross-Cutting Evaluation Artifact Capture

Status: in progress in the planner thread; changes affect default artifact behavior for local and Daytona sim-match runs.

- [x] User requested artifact capture be on by default whenever sim matches run, including Daytona sims.
- [x] Planner chose to implement this at the harness boundary rather than only one script.
- [x] New intended default: no explicit artifact config means write replay and result artifacts under `/tmp/ow-eval-artifacts`.
- [x] Preserve explicit caller overrides for output directory/prefix.
- [x] Daytona-specific requirement added: remote shard replay/result artifacts must be planned as deterministic download paths, not only written inside the sandbox.
- [x] Patched default artifact behavior in `ow_eval/artifacts.py`, `ow_eval/official_runner.py`, `ow_eval/batch_runner.py`, `ow_eval/experiment_runner.py`, `ow_eval/shard_runner.py`, `ow_eval/parity.py`, `ow_eval/regression_gate.py`, `ow_eval/daytona_jobs.py`, and exports.
- [x] Updated focused runner, artifact, shard, experiment, parity/gate, Daytona operation/client/report/real-CLI tests to expect artifact downloads and deterministic prefixes.
- [x] Updated evaluation and Daytona docs to state artifacts are captured by default under `/tmp` and still not committed.
- [x] Focused runner and Daytona tests passed.
- [x] Broader affected Daytona/evaluation test groups passed after making expected download operations data-driven.
- [x] `git diff --check` passed.
- [ ] Regression gate completion.
- [ ] Submission preflight completion.
- [ ] Planner-thread final status/review/commit decision.

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
- 2026-06-17: Poll found Mission Evaluation Cycles 10-13 complete and committed. Planner confirmed `MISSION_EVALUATION_SEGMENT_COMPLETE`; Opponent Response is next.
- 2026-06-17: Poll found planner/reviewer actively preparing Opponent Response Model Cycle 0 as the API boundary cycle.
- 2026-06-17: Poll found Opponent Response Cycles 0-3 complete and committed. Cycle 4 FFA third-party benefit facts is implemented in the implementation thread and pending review/commit.
- 2026-06-17: Poll found Opponent Response Cycles 4-7 complete and committed. Opponent Response is complete; Commitment Policy is next.
- 2026-06-17: Poll found Commitment Policy Cycles 0-3 complete and committed. Cycle 4 reserve-preserving commitment option is implemented in the implementation thread and pending planner/reviewer review/commit.
- 2026-06-17: Poll found Commitment Policy Cycles 4-7 complete and committed; planner confirmed `COMMITMENT_POLICY_SEGMENT_COMPLETE`. Strategy Modes is next.
- 2026-06-17: Poll found Strategy Modes Cycle 0 complete and committed as `78fe13d Add planner strategy mode boundary`; Cycle 1 planner decision bundle boundary is in progress in the implementation thread.
- 2026-06-17: Poll found Strategy Modes Cycles 1-4 complete and committed through `183a3d2 Add planner two-player direct selector`; Cycle 5 four-player rank/survival facts remains next.
- 2026-06-18: Poll found Strategy Modes Cycles 5-7 complete and committed through `ca43b35 Add planner four-player selector`; planner/reviewer is preparing the next Cycle 8 prompt.
- 2026-06-18: Poll found Strategy Modes Cycles 8-9 complete and committed through `58e8fe5 Add planner strategy mode fixture tests`; planner/reviewer confirmed `STRATEGY_MODES_SEGMENT_COMPLETE`. Runtime / Submission is next.
- 2026-06-18: Poll found Runtime / Submission Cycles 0-3 complete and committed through `32e881d Add runtime action conversion`; Cycle 4 safe turn orchestration is implemented in the implementation thread and pending planner/reviewer review/commit.
- 2026-06-18: Poll found Runtime / Submission Cycles 4-7 complete and committed through `0949f95 Add submission bundler`; planner/reviewer confirmed `RUNTIME_SUBMISSION_SEGMENT_COMPLETE`. Evaluation Harness / Match Testing is next and should use local official Kaggle environments, not live submissions.
- 2026-06-18: Poll found Evaluation Harness Cycles 0-1 complete and committed through `c0f0385 Add official evaluation smoke runner`; Cycle 2 agent loading modes is implemented in the implementation thread and pending planner/reviewer review/commit.
- 2026-06-18: Poll found Evaluation Harness Cycles 2-5 complete and committed through `ef16d96 Add evaluation metrics extraction`; Cycle 6 batch evaluation runner is next.
- 2026-06-18: Poll found Evaluation Harness Cycles 6-8 complete and committed through `d21f817 Add evaluation failure triage reports`; Cycle 9 deterministic baseline scoreboard records is in progress in the implementation thread.
- 2026-06-18: Poll found Evaluation Harness Cycle 9 implementation in progress: scoreboard module, exports, and tests have been added, with focused, grouped, and full discovery checks reported green so far. Final verifier completion, planner/reviewer review, and commit are still pending.
- 2026-06-18: Poll found Evaluation Harness Cycles 9-11 complete and committed through `7431618 Add evaluation planner analysis packs`. Planner issued Cycle 12 as Experiment Manifest Contracts And Match Expansion; implementation has not yet been observed.
- 2026-06-18: Poll found Evaluation Harness Cycles 12-15 complete and committed through `8dee2f2 Add evaluation experiment reports`. Cycle 16 end-to-end local experiment command layer is implemented in the implementation thread and under planner/reviewer review; no Cycle 16 commit observed yet.
- 2026-06-18: Poll found Evaluation Harness Cycle 16 complete and committed as `03539f5 Add evaluation experiment CLI`. No next-cycle prompt observed yet.
- 2026-06-19: Poll found Evaluation Harness Cycles 17-20 complete and committed through `cba9efd Add evaluation harness runbook`. Planner/reviewer is currently preparing the next-cycle prompt; no Cycle 21 scope observed yet.
- 2026-06-19: Planner/reviewer chose the next high-level segment instead of Evaluation Harness Cycle 21: Distributed Evaluation / Daytona Sharding. Segment Cycle 0 is deterministic shard-plan contracts; implementation has not yet been observed.
- 2026-06-19: Poll found Distributed Evaluation Cycle 0 complete and committed as `ea4ab49 Add evaluation shard plan contracts`; Cycle 1 complete and committed as `e53812a Add evaluation shard runner`; Cycle 2 shard run result persistence is in progress in the implementation thread.
- 2026-06-19: Poll found Distributed Evaluation Cycles 2-5 complete and committed through `57227d8 Add evaluation shard manifest materialization`. Cycle 6 deterministic shard job package/index contracts are implemented in the implementation thread and under planner/reviewer review; no Cycle 6 commit observed yet.
- 2026-06-19: Poll found Distributed Evaluation Cycles 6-10 complete and committed through `80e660d Add evaluation Daytona job specs`. Planner/reviewer is currently generating the next-cycle prompt; Cycle 11 scope is not available yet.
- 2026-06-19: Poll found Distributed Evaluation Cycle 11 complete and committed as `dbdeabc Add evaluation Daytona plan CLI`. Cycle 12 Daytona job plan reader/preflight validator prompt is issued, but implementation has not progressed yet because the implementer thread hit repeated system errors and was retried.
- 2026-06-19: Poll found Distributed Evaluation Cycle 12 complete and committed as `66ca026 Add evaluation Daytona preflight` after the implementer retry succeeded and planner/reviewer found no issues.
- 2026-06-19: Poll found Distributed Evaluation Cycles 13-15 complete and committed through `4b244c6 Add evaluation Daytona operation plans`. Cycle 16 injected Daytona client executor adapter is implemented in the implementation thread and under planner/reviewer review; no Cycle 16 commit observed yet.
- 2026-06-19: Poll found Distributed Evaluation Cycles 16-18 complete and committed through `4672c56 Add evaluation Daytona client report CLI`. Cycle 19 real-Daytona safety gate / SDK adapter skeleton is implemented but had a reviewer blocker; the requested readiness-gate fix is now implemented in the implementation thread and awaits re-review/commit.
- 2026-06-19: Poll found Distributed Evaluation Cycles 19-22 complete and committed through `22c68d9 Add evaluation Daytona real execution CLI`. Cycle 23 operational runbook and safety guardrails is now in progress in the implementation thread; the runbook doc has been added and docs guardrail tests are still in progress.
- 2026-06-19: Poll found Distributed Evaluation Cycles 23-24 complete and committed through `b113207 Add distributed evaluation preflight`; Distributed Evaluation is complete. Competitive Improvement Cycle 0 baseline measurement pack is complete and committed as `1055e57 Add competitive baseline measurement pack` with local result `competitive-baseline-smoke 6 True`. Planner/reviewer is actively reviewing path-forward/live-readiness and has preliminarily found stricter submission gates failing with `invalid_or_noop_heavy_behavior`.
- 2026-06-19: Planner/reviewer completed the path-forward review: broad deterministic build is done, but serious live submission is deferred until no-op-heavy behavior and runtime-heavy candidate validation are fixed and `scripts/submission_preflight.py` returns cleanly. Recorded Competitive Improvement Cycle 1 as planned submission-readiness/no-op reduction, with a legacy-opponent benchmark pack as a candidate follow-up surface.
- 2026-06-19: Poll found Competitive Readiness / Submit V0 Cycle 0 gate diagnostics complete and committed as `ae5ee3c Add competitive readiness gate diagnostics`; Cycle 1 runtime candidate budget fix complete and committed as `e31a2bc Bound runtime candidate validation work`. Cycle 2 no-op reduction pass is in progress in the implementation thread; initial runtime-default changes improved action production, but the gate still has one parity match dominated by `no_candidates_generated`.
- 2026-06-19: Poll found Competitive Readiness / Submit V0 Cycle 2 complete and committed as `3386c8f Reduce runtime no-op behavior`; `scripts/evaluation_gate.py` now exits `0` with parity pass and no failures. Cycle 3 submission-preflight-green work is in progress in the implementation thread; current issue is preflight/suite runtime, with cap 6 keeping the gate green while full preflight is still running.
- 2026-06-20: Poll found Competitive Readiness / Submit V0 Cycle 3 complete and committed as `94d4f80 Bound submission preflight smoke suite`; submission preflight and default suite are now green/bounded. Cycle 4 legacy opponent benchmark pack is in progress in the implementation thread; initial legacy benchmark reports `legacy-opponent-smoke 4 0.0 True`, gate and preflight remain green, and final full discovery is still running.
- 2026-06-20: Poll found Competitive Readiness / Submit V0 Cycle 4 complete and committed as `4fd15ba Add legacy opponent smoke benchmark`; planner/reviewer marked Competitive Readiness complete. Live Submission V0 started and Cycle 0 mechanism preflight was committed as `c558a30 Add live submission mechanism preflight`; live submission is blocked because Kaggle CLI/package and `~/.kaggle/kaggle.json` are missing.
- 2026-06-20: Poll found Live Submission V0 Cycle 1 complete and committed as `80fca70 Record live V0 Kaggle submission`. The V0 artifact was rebuilt/hash-checked, local readiness passed, one Kaggle upload was made with ref `53862054`, reviewer verified `SubmissionStatus.COMPLETE` with public score `600.0`, and planner/reviewer reported `LIVE_SUBMISSION_V0_SEGMENT_COMPLETE`.
- 2026-06-20: Planner/reviewer identified the next high-level segment as Live Feedback Intake + Competitive Improvement Loop. The first practical cycle is V0 Live Results Intake for submission ref `53862054`: capture live status/score, download/analyze available replays in a separate replay-analysis workflow, and produce a compact weakness report before changing the agent.
- 2026-06-20: Poll found V0 live feedback intake complete. Replay analysis for submission `53862054` recorded public score `426.8`, 20 analyzed public episodes, sample record `4-16`, 4P record `0-10`, 2P record `4-6`, and a severe 4P leak where all sampled 4P games emitted zero actions.
- 2026-06-20: Planner/reviewer opened the V0 Replay Leak Fix segment. Cycle 0 replay regression fixtures was reviewed and committed as `560b26d Add V0 replay leak characterization fixtures`; Cycle 1 Candidate Starvation Fix has been prompted and is currently in progress in the implementation thread.
- 2026-06-20: Poll found V0 Replay Leak Fix Cycle 1 complete and committed as `258932f Fix candidate validation starvation`. Planner/reviewer selected Cycle 2 as Four-Player Strategy Selection Action Fix: make the t100 4P replay fixture emit a legal action now that candidate generation is no longer starved, without starting 2P defense/capture-hold work yet.
- 2026-06-20: Poll found V0 Replay Leak Fix Cycle 2 complete and committed as `125d1c5 Fix four-player strategy no-action leak`. Planner/reviewer selected Cycle 3 as Opening Idle Fallback for parseable opening/low-owned states; implementation is active, with `scripts/submission_preflight.py` still running in the implementation thread.
- 2026-06-20: Poll found V0 Replay Leak Fix Cycle 3 blocked in review and not committed. The opening fallback worked in focused checks and emitted actions for the two opening fixtures, but reviewer found full `unittest discover` failing in generated-submission parity at `tests/test_evaluation_parity.py:402` despite isolated parity tests passing; the cycle needs a fix or acceptable guardrail before commit.
- 2026-06-20: Poll found Cycle 3 still blocked after a generated-submission isolation follow-up. The implementer hardened `submission_file` callable isolation and focused parity/agent-loading checks passed, but reviewer reran full discovery and it still failed at `tests/test_evaluation_parity.py:422`; no commit was made.
- 2026-06-20: Poll found a second Cycle 3 generated-submission isolation/diagnostic follow-up under reviewer re-review. Implementer reports `ow_eval/agent_loading.py` and `ow_eval/official_runner.py` now preserve bundled module isolation for generated-agent calls and diagnostics, with full discovery/gate/preflight passing locally; planner/reviewer is actively rerunning parity verification and has not committed yet.
- 2026-06-20: Poll found Cycle 3 accepted and committed as `06db0f3 Fix opening idle fallback and submission isolation`. Planner/reviewer opened Cycle 4 as Two-Player Pressure Retention Selector; implementer added pressure facts/selection tests and preserved the negative-time budget guard, but review blocked commit because full discovery failed in generated-submission parity artifact coverage at `tests/test_evaluation_parity.py:435` while the parity module passes in isolation. Planner/reviewer is preparing a scoped blocker-fix plan.
- 2026-06-20: Poll found Cycle 4 blocker fix implemented and under reviewer re-review. Follow-up covers `ow_planner.two_player_pressure` bundling/lazy-import isolation and adds a parity-only deterministic runtime clock in `ow_eval/parity.py`; implementer reports full discovery/gate/preflight green, while reviewer has confirmed pressure probes and focused checks and is still running parity verification. No Cycle 4 commit observed yet.
- 2026-06-20: Poll found Cycle 4 complete and committed as `ea96f24 Add two-player pressure retention selection`. Planner/reviewer opened Cycle 5 as Capture-Hold Candidate Recovery; implementer added owned-target reinforcement candidate generation, reported both capture-hold fixtures now emit reserve-preserving actions with 8 candidates, and reviewer has started review. No Cycle 5 commit or finding observed yet.
- 2026-06-20: Poll found Cycle 5 complete and committed as `c8982df Add capture-hold reinforcement candidates`. Planner/reviewer opened Cycle 6 as Pressure-Aware Selection And Reserve Policy; implementation is active, with selector changes preferring owned-retention missions under pressure and all verifiers through evaluation gate/diff check reportedly passed, while `scripts/submission_preflight.py` was still running at latest poll.
- 2026-06-20: Poll found Cycle 6 complete and committed as `e3209d0 Add pressure-aware retention selection`. Planner/reviewer opened Cycle 7 as Capture-Hold Gate; implementation is active in `ow_planner/two_player_selection.py`, with risk-aware capture-and-hold selection being narrowed after an initial version changed pressure fixture behavior in violation of preservation criteria.
- 2026-06-20: Poll found Cycle 7 complete and committed as `739ca12 Add capture-hold risk gate`. Planner/reviewer opened Cycle 8 Replay Regression Harness; implementer added measurement-only `ow_eval/v0_replay_regression.py` plus tests, with all 7 V0 fixtures covered and unresolved budgetless planner no-actions at 0. Cycle 8 is awaiting review and commit.
- 2026-06-20: Poll found Cycle 8 complete and committed as `e3d0cde Add V0 replay regression harness`. Planner/reviewer opened Cycle 9 V1 Candidate Evaluation And Submit Prep; implementer updated `docs/v0-replay-leak-fix.md` with no-submit readiness evidence, V1 artifact hash, smoke benchmarks, and a temporary V1-vs-V0 comparison. Cycle 9 is awaiting review and commit.
- 2026-06-21: Poll found Cycle 9 complete and committed as `3641021 Record V1 replay leak readiness`; planner/reviewer emitted `V0_REPLAY_LEAK_FIX_SEGMENT_COMPLETE`. New Live Submission V1 segment planned with Cycles 0-3. Cycle 0 Final No-Submit Mechanism Check is implemented in the implementation thread via `docs/live-submission-v1.md`, with Kaggle CLI/non-upload access verified and no submission made; it is awaiting review and commit.
- 2026-06-21: Poll found Live Submission V1 Cycle 0 complete and committed as `519e1a2 Add V1 live submission mechanism check`; Cycle 1 complete and committed as `4e66048 Record V1 final artifact readiness`. Planner/reviewer issued Cycle 2 Exactly One Live Kaggle Upload; implementation has not yet been observed.
- 2026-06-21: Poll found Live Submission V1 complete and committed as `313c0c4 Record V1 live submission`. V1 submission ref `53894832` was uploaded exactly once, later verified `SubmissionStatus.COMPLETE` with public score `569.1`; the runbook records `LIVE_SUBMISSION_V1_SEGMENT_COMPLETE`. Planner/reviewer issued Live Feedback Intake V1 Cycle 0 for V1 live results and replay intake.
- 2026-06-21: Poll found user explicitly paused Live Feedback Intake V1 Cycle 0; implementation thread confirmed it will not continue replay/result intake or commit anything for that prompt. Planner/reviewer later checked the current score: V1 ref `53894832` is `SubmissionStatus.COMPLETE` with public score `429.2`; V0 is `419.2`.
- 2026-06-21: User chose a new V1 Deterministic Leak Fix segment after reviewing V1 weaknesses. Planner broke it into Cycles 0-12, deferring autoresearch until deterministic fixtures/facts/candidates/gates exist. Cycle 0 V1 Replay Regression Fixtures was implemented and committed as `74a5791 Add V1 replay leak characterization fixtures`, adding 10 compact V1 fixtures plus characterization tests/docs.
- 2026-06-21: Poll found V1 Deterministic Leak Fix Cycle 1 complete and committed as `1b968dd Add owned production threat facts`. Planner issued Cycle 2 as Owned Production Retention Selection, using the new `ow_planner.owned_threats` facts to prefer validated 2P owned-retention actions under visible owned-production pressure; implementation is active and not yet reviewed/committed.
- 2026-06-21: Poll found V1 Deterministic Leak Fix Cycle 2 complete and committed as `8a86f33 Add owned production retention selection`. Reviewer accepted the V1 and one V0 fixture expectation updates as in-scope owned-production pressure-retention behavior. Planner issued Cycle 3 as Own-Transfer Intent Facts, a facts-only surface for classifying purposeful versus spammy own-to-own transfers; implementation has started but is not yet reviewed/committed.
- 2026-06-21: Poll found V1 Deterministic Leak Fix Cycle 3 complete and committed as `44b6372 Add own transfer intent facts`. Planner issued Cycle 4 as Own-Transfer Spam Reduction Selection, threading `ow_planner.own_transfers` facts into 2P selection to suppress spammy own-transfer choices when productive alternatives exist while preserving Cycle 2 pressured-retention behavior; implementation is active and not yet reviewed/committed.
- 2026-06-21: Poll found V1 Deterministic Leak Fix Cycle 4 complete and committed as `fdb201c Add own transfer spam selection guard`. Planner issued Cycle 5 as Enemy Production Denial Opportunity Facts, a facts-only `ow_planner.enemy_denial` surface for identifying two-player ahead-state opponent-production denial opportunities; implementation is active and not yet reviewed/committed.
- 2026-06-21: Poll found V1 Deterministic Leak Fix Cycle 5 complete and committed as `39a0416 Add enemy production denial facts`. The change remained facts-only, added `ow_planner.enemy_denial`, exports, tests, V1 fixture characterization, and docs; no Cycle 6 prompt was observed yet.
- 2026-06-21: Poll found V1 Deterministic Leak Fix Cycle 6 complete and committed as `d5339c3 Add enemy production denial selection`. It threads `EnemyDenialOpportunityReport` into two-player selection while preserving retention/safety priority; live fixture `80989880` remains safety-blocked by owned-production pressure. No Cycle 7 prompt was observed yet.
- 2026-06-21: Poll found planner issued V1 Deterministic Leak Fix Cycle 7 as Four-Player Plateau Opportunity Facts, superseding the earlier tentative 2P denial-gate slot. Implementation thread has completed a facts-only `ow_planner.four_player_plateau` surface plus exports, direct tests, V1 fixture assertions, and docs; focused tests, full discovery (`1305` tests), gate, preflight, import sanity, and `git diff --check` reportedly passed. Awaiting planner/reviewer review and commit.
- 2026-06-21: Poll found V1 Deterministic Leak Fix Cycle 7 reviewed and committed as `6fa0fe2 Add four-player plateau opportunity facts`. Planner issued Cycle 8 as Four-Player Plateau No-Action Recovery, a narrow behavior cycle to thread `FourPlayerPlateauReport` into 4P selection and recover legal actions for true 4P candidate-backed plateau windows. Implementation is active; current visible progress has target fixture `80981260` emitting action `[[14, -0.1300173607969723, 1]]`, focused groups/submission-evaluation group/full discovery (`1308` tests)/import sanity/`git diff --check` passing, and final gate/preflight/review still pending at latest poll.
- 2026-06-21: Poll found V1 Deterministic Leak Fix Cycle 8 reviewed and committed as `f06299a Add four-player plateau recovery selection`. Planner issued Cycle 9 as 4P Rank / Leader / Swing Facts, an observability-only `ow_planner.four_player_rank` surface for rank/leader/swing-risk context. Implementation is active with the new module, exports, focused tests, V1 fixture characterization, and docs patched; focused rank/fixture/plateau/selection/runtime tests and import sanity have passed, while full discovery/gate/preflight/review are still pending at latest poll.
- 2026-06-21: Poll found V1 Deterministic Leak Fix Cycle 9 reviewed and committed as `24ee4e0 Add four-player rank swing facts`. Planner issued Cycle 10 as 4P Continuation / Rank-Aware Selector Gate, a narrow selector/runtime behavior cycle threading `FourPlayerRankReport` into 4P selection alongside plateau facts. Implementation is active; current visible work has selector/runtime patches, direct and pipeline tests, fixture selection-note updates for `80982912` and `80979440`, and unchanged V1 fixture actions, with verification/review still pending.
- 2026-06-22: Poll found V1 Deterministic Leak Fix Cycle 10 reviewed and committed as `2a59bbe Add rank-aware four-player continuation gate`. The change threads `FourPlayerRankReport` into 4P selection after existing validation/safety checks, updates rank-aware fixture notes for `80982912` and `80979440` without changing action counts/commitments, and preserves Cycle 8 plateau recovery. No Cycle 11 prompt was observed yet.
- 2026-06-22: Poll found planner issued V1 Deterministic Leak Fix Cycle 11 as V1 Replay Regression Harness. Implementation thread completed measurement-only `ow_eval.v1_replay_regression` plus exports/tests/docs and reported stable harness summary `v1_replay_regression cases=10 live_actions=9 live_no_actions=1 unresolved_planner_no_actions=0 reduced_active_owner_caveats=1 owned_pressure=8 own_transfer_spam=3 enemy_denial_safety_blocked=1 four_player_plateau_actions=3 four_player_plateau_no_actions=1 rank_aware_continuations=2 thin_capture_risks=2`; reviewer has scope-reviewed it as measurement-only and full discovery passed `1328` tests, with gate/preflight/review still in progress and no commit observed yet.
- 2026-06-22: Poll found V1 Deterministic Leak Fix Cycle 11 reviewed and committed as `411f6e0 Add V1 replay regression harness`. Planner issued Cycle 12 as Segment Readiness Report; implementation thread completed a docs-only readiness section with replay-regression summary, focused/full/gate/preflight/smoke results, remaining reduced-active-owner caveat, and recommendation that the V1 deterministic leak-fix segment is complete. Planner/reviewer is actively verifying Cycle 12; no Cycle 12 commit observed yet.
- 2026-06-22: Poll found V1 Deterministic Leak Fix Cycle 12 reviewed and committed as `fd80611 Record V1 deterministic readiness`, with sentinel `V1_DETERMINISTIC_LEAK_FIX_SEGMENT_COMPLETE`. Planner then opened Live Submission V2; Cycle 0 no-submit mechanism check was reviewed and committed as `75867e3 Add V2 live submission mechanism check`.
- 2026-06-22: Poll found Live Submission V2 Cycle 1 completed and committed as `8fccb48 Record V2 live submission`. Exactly one upload command was invoked, Kaggle accepted V2 ref `53925932`, reviewer observed final status `SubmissionStatus.COMPLETE` with public score `600.0`, and sentinel `LIVE_SUBMISSION_V2_SEGMENT_COMPLETE` was recorded.
- 2026-06-22: Planner assessed the proposed old-agent gauntlet and agreed a serious historical-agent gauntlet would likely have caught many V1 deterministic leaks earlier. Proposed next segment: Historical Champion Gauntlet / Deterministic Leak Discovery, with cycles for opponent inventory, gauntlet manifests, replay/diagnostic capture, first V2 gauntlet run, loss/weak-win triage, fixture extraction, and next-work decision. No implementer prompt observed yet.
- 2026-06-22: User refined the gauntlet plan to use Daytona sandboxes and full 500-step matches. Planner expanded it into the Distributed Historical Champion Gauntlet segment with Cycles 0-12, keeping local runs as tiny probes and Daytona for real parallel volume.
- 2026-06-22: Poll found Distributed Historical Champion Gauntlet Cycle 0 reviewed and committed as `f97e335 Add historical champion registry`. The registry records 11 loadable historical opponents and 3 skipped candidates with reasons, without copying historical source code or running matches/Daytona jobs.
- 2026-06-22: Poll found Distributed Historical Champion Gauntlet Cycle 1 reviewed and committed as `0ac3e2d Add historical champion gauntlet manifests`. The committed full-horizon manifests contain 22 2P scenarios and 8 4P scenarios, all with `metadata.episode_steps == "500"`, only loadable registry entries, and no match/Daytona/Kaggle execution.
- 2026-06-22: Planner issued Distributed Historical Champion Gauntlet Cycle 2 as Local Full-500 Micro-Probe. Implementation thread completed a docs-only probe record after running one 2P and one 4P full-500 local official-environment scenario from the committed manifests; both completed with `normal_loss`, `error_count=0`, generated artifacts only under `/tmp`, and no Daytona/Kaggle/behavior changes. Awaiting planner/reviewer review and commit.
- 2026-06-22: Poll found Distributed Historical Champion Gauntlet Cycle 2 reviewed and committed as `76cdd7f Record historical champion micro-probe`. Planner issued Cycle 3 as Daytona Shard Plan Generation.
- 2026-06-22: Poll found Distributed Historical Champion Gauntlet Cycle 3 reviewed and committed as `f7be3c6 Add historical champion shard plan`. The shard plan assigns all 30 full-500 scenarios exactly once across 6 deterministic JSON-safe shards and identifies shard-000 as the next probe shard, without running matches or Daytona jobs.
- 2026-06-22: Poll found Distributed Historical Champion Gauntlet Cycle 4 reviewed and committed as `e410748 Add historical champion package adapter`. The package adapter materializes shard-000 into a package-ready `/tmp` structure with exactly five full-500 scenarios and no match/report/result execution.
- 2026-06-22: Poll found Distributed Historical Champion Gauntlet Cycle 5 reviewed and committed as `e8eaa35 Record historical champion Daytona probe path`. The single-shard Daytona plan and fake/dry executor passed for shard-000, but real Daytona readiness was blocked by `allow_real_daytona=False` and missing `DAYTONA_API_KEY`; no real command was run.
- 2026-06-22: Poll found Distributed Historical Champion Gauntlet Cycle 6 reviewed and committed as `0a64dd1 Record guarded Daytona readiness`. It independently confirmed the shard-000 real-Daytona path is ready up to the guarded execution boundary, still blocked by the same real-Daytona readiness environment, with generated files only under `/tmp`.
- 2026-06-22: User paused gauntlet progression to set up Daytona first. Planner is actively implementing Daytona environment/SDK setup after checking official Daytona docs: `.env` loading, `DAYTONA_API_KEY`/`DAYTONA_TARGET`, conditional `GITHUB_TOKEN` for clone-bootstrap mode, and real SDK alignment are in progress; no commit observed yet.
- 2026-06-22: Poll found Daytona setup progressed inside the planner thread: `.env` loading, official SDK `daytona==0.189.0`, snapshot path over clone-bootstrap, snapshot `ow-serious-runtime-0a64dd17d867`, official SDK adapter, self-contained historical opponent package upload path, plan validation, fake dry-run, and full discovery checks are green; no commit observed yet.
- 2026-06-22: User explicitly approved exporting the generated one-shard gauntlet package and historical agent files to Daytona. Planner started exactly one real remote probe for `historical-gauntlet-shard-000` with five full-500 scenarios; it was still running at latest poll, with no result or commit observed yet.
- 2026-06-22: Poll found the real shard probe diagnosed and fixed. The original full-shard Daytona command hit a long synchronous `process.exec` proxy disconnect, so the planner added a guarded smoke diagnostic and changed the official SDK adapter to use Daytona sessions with async command polling/log fetch. Session-based real smoke passed, the single shard completed, results downloaded to `/tmp`, focused Daytona checks and full discovery `1386` tests passed, and no commit was observed.
- 2026-06-22: The real `historical-gauntlet-shard-000` result completed five full-500 matches with no execution errors, but V2 lost all five: mean final rank `2.0`, mean final score `-1.0`, errors `0`. Next gauntlet decision is whether to proceed to a multi-shard pilot or triage shard-000 losses first.
- 2026-06-22: Planner later recommended local test parallelization over Daytona for ordinary full discovery and implemented uncommitted local test-throughput tooling: `ow_eval/local_tests.py`, `scripts/run_tests_parallel.py`, `scripts/profile_tests.py`, tests, and docs. Full parallel module run passed `111` modules in `293.176s`, with `tests.test_evaluation_parity` still the dominant bottleneck at about `289s`.
- 2026-06-22: Poll found Distributed Historical Champion Gauntlet Completion Cycle 7 reviewed cleanly and committed as `2721538 Consolidate Daytona gauntlet setup`. The commit includes Daytona `.env` setup docs/example, runtime snapshot prep tooling, real smoke diagnostic, official SDK session-command path for long shard runs, historical opponent package/upload support, local parallel test/profile tooling, and docs recording successful shard-000 setup evidence. Review checks: focused Cycle 7 tests `93` OK, full parallel local run `111` modules OK in `92.339s`, and `git diff --check` clean.
- 2026-06-22: Planner issued Distributed Historical Champion Gauntlet Completion Cycle 8 as Full-Gauntlet Package Materialization And Daytona Plan Dry-Run, starting from `2721538`, with no real Daytona jobs or matches allowed. Implementation thread completed the cycle: full package under `/tmp/ow-historical-gauntlet-full-package`, `6` shards, `30` scenarios, `5` scenarios per shard, all `episode_steps=500`, package-local historical agent files, six-job Daytona plan, validation pass, fake/dry executor `jobs=6 exit_code=0`, focused tests/diff check/parallel confidence green. Awaiting planner/reviewer review and commit.
- 2026-06-22: Poll found Distributed Historical Champion Gauntlet Completion Cycle 8 reviewed cleanly and committed as `6fd0d2e Add full historical gauntlet package prep`. The review included the `--no-materialize-manifests` blocker fix: the old command now fails cleanly at argparse rather than `FileNotFoundError`. Verification included focused gauntlet package tests `18` OK, Daytona package/plan/preflight/dry-run tests `66` OK, full package materialization `6` shards / `30` unique full-500 scenarios, local dry-run pass, full parallel test run `111` modules OK, and `git diff --check` clean.
- 2026-06-22: Planner issued Cycle 9 as Guarded Real Daytona Full-Gauntlet Run. Implementation validated the fresh `/tmp/ow-historical-gauntlet-cycle9-full-real` package and plan (`6` jobs, `30` unique full-500 scenarios), passed local dry-run, and passed guarded real Daytona smoke with readiness `READY`, but the full six-shard real Daytona command did not execute because the environment approval layer rejected external upload/transfer of repo-derived manifests, job specs, and packaged historical agent source files to Daytona.
- 2026-06-22: Poll found Cycle 9 docs-only blocked-status update reviewed cleanly and committed as `2c8bca1 Record historical gauntlet Daytona block`. The runbook records that no shard results were downloaded, no full-gauntlet match results exist from Cycle 9, no Kaggle command was run, and raw generated artifacts remain under `/tmp`.
- 2026-06-22: Planner explained the blocker is not Daytona auth/config: package generation, plan validation, dry-run, smoke, and readiness all passed. The blocker is this chat's execution policy for uploading local source-derived files to Daytona. Planner gave the user the guarded terminal command for local execution if `/tmp/ow-historical-gauntlet-cycle9-full-real/daytona-shard-jobs.json` still exists, plus rebuild commands if not.
- 2026-06-22: Planner then confirmed the existing `/tmp/ow-historical-gauntlet-cycle9-full-real/daytona-shard-jobs.json` plan exists, validates with `6` specs/no missing uploads/no duplicate sandbox names, real Daytona readiness is `READY`, and `GITHUB_TOKEN` is not required. Current Cycle 10 state is waiting for the user to run the guarded full-gauntlet Daytona command locally and return results.
- 2026-06-22: Poll found the detached Daytona gauntlet completed successfully after manual user launch. Planner issued Cycle 10 as Real Run Completion Audit. Known report facts: `/tmp/ow-historical-gauntlet-cycle9-full-real/daytona-real-report.json`, `passed=True`, `exit_code=0`, summary includes `jobs=6 events=144 operation_plans=6 exit_code=0`, execution result count `6`, shard result path count `6`, shard result files for `000` through `005`.
- 2026-06-22: Implementation thread started Cycle 10 read-only audit and confirmed the actual shard-result schema. Audit now confirms `6/6` shard results, `30/30` matches, and `0` shard execution errors. Docs-only runbook update is in progress; no Daytona rerun, Kaggle command, behavior change, or raw artifact commit observed.
- 2026-06-22: Planner later reported Cycle 10 committed as `3f5474f Record historical gauntlet real run completion`, Cycle 11 committed as `1af3bc9 Summarize historical gauntlet merged results`, and Cycle 12 committed as `9a57e94 Triage historical gauntlet losses`. Known Cycle 11 aggregate: `30/30` scenarios completed, `0` errors, `0` invalid actions, `0` timeouts, win rate `0.0`, mean final rank `2.0`, rank distribution `{"2": 30}`, no-action count `2569`, mean turns survived `153.7`.
- 2026-06-22: Planner issued Cycle 13 as Compact Failure Fixture Extraction from the Cycle 12 candidate cases. Initial implementation found a real blocker: all six candidates had `artifact_path=null` and `replay_path=null`, with no replay/observation payloads under the completed Daytona run root, because artifact capture was opt-in and the historical Daytona path only saved match summaries.
- 2026-06-22: Planner diagnosed the Cycle 13 blocker and provided a fix plan: locally rerun exactly the six selected full-500 scenarios with `EvaluationArtifactConfig(write_replay=True, write_result=True)` under `/tmp`, then extract compact fixtures only from real replay payloads. Implementation thread reran the six scenarios under `/tmp/ow-historical-gauntlet-cycle13-artifacts`, extracted compact fixtures under `tests/fixtures/historical_gauntlet_leaks/`, added `tests/test_historical_gauntlet_leak_fixtures.py`, updated docs, and passed focused fixture/source/runtime/V1 regression checks; `scripts/evaluation_gate.py` was still running at latest poll.
- 2026-06-22: User requested artifact capture be default for all sim matches, including Daytona sims. Planner thread began a cross-cutting harness change: default artifacts under `/tmp/ow-eval-artifacts`, shard-local prefixes, Daytona planned download paths for replay/result artifacts, updated tests/docs, focused and broader affected tests green, `git diff --check` green, with regression gate and submission preflight still running.
- 2026-06-22: Poll found Distributed Historical Champion Gauntlet Completion Cycle 13 reviewed/committed as `6007b96 Add historical gauntlet leak fixtures`. Cycle 13 produced compact fixtures under `tests/fixtures/historical_gauntlet_leaks/`, `tests/test_historical_gauntlet_leak_fixtures.py`, and docs mapping fixture evidence to source gauntlet cases.
- 2026-06-22: Poll found Cycle 14 docs-only completion handoff reviewed/committed as `09158df Complete historical gauntlet handoff`. The segment now records `HISTORICAL_CHAMPION_GAUNTLET_COMPLETE`, full Daytona gauntlet completion evidence, committed compact fixture evidence, and a prioritized deterministic fix queue.
- 2026-06-22: User asked for a plan to fix deterministic leaks and verify with one full-500 2P Daytona historical match and one full-500 4P Daytona historical match. Planner created new segment `Historical Gauntlet Deterministic Leak Fix` with sentinel `HISTORICAL_LEAK_FIX_DAYTONA_PROBE_COMPLETE`, cycles 0-8: baseline characterization, 2P candidate recovery, 2P pressure selection, 4P plateau recovery, 4P budget-pressure split, regression harness update, Daytona 2P probe, Daytona 4P probe, and probe analysis/handoff.
- 2026-06-22: Planner issued Historical Gauntlet Deterministic Leak Fix Cycle 0 as Baseline Characterization. Expected output is a source-controlled baseline note, likely `docs/historical-gauntlet-deterministic-leak-fix.md`, covering every committed historical leak fixture with current action/diagnostic/candidate/budget/strategy details and no behavior changes.
- 2026-06-22: Poll found Historical Gauntlet Deterministic Leak Fix Cycle 0 complete and committed as `54b0974 Record historical leak baseline`; the baseline note is `docs/historical-gauntlet-deterministic-leak-fix.md`, covering committed compact fixtures without behavior changes.
- 2026-06-22: Poll found Cycle 1 2P Early Collapse Candidate Recovery implemented in the implementation thread and under planner/reviewer review. The implementation adds bounded early 2P pressure-recovery candidate generation in `ow_planner/candidates.py`, fixes the two target `no_candidates_generated` fixtures through normal planner generation, reports legal reserve-preserving runtime actions with `8` runtime-capped candidates for both target fixtures, and has focused historical/planner/runtime, gate, preflight, and diff-check results green. Full discovery still reports two Daytona/client-report failures attributed to unrelated artifact-default dirty work; no Cycle 1 commit observed yet.
