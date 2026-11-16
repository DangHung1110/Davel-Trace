# Research: Stable Planning Roadmap MVP

## Decision 1: Wrap the detailed gate registry in five families

- **Decision**: Keep every existing deterministic check and add a family summary: temporal, financial, movement, safety/data validity, and explicit traveler constraints.
- **Rationale**: The detailed checks are already shared by selection and evaluation and have broad regression coverage. Grouping them provides the simpler product contract requested by the roadmap without deleting evidence or weakening feasibility.
- **Alternatives considered**: Deleting overlapping checks would risk optimizer/validator drift; displaying all check names as top-level policy would preserve the current correction-cascade problem.

## Decision 2: Extend the existing CP-SAT pool and MMR path to five results

- **Decision**: Keep the existing solution-pool enumeration, gate validation, Jaccard evidence, and MMR selection; raise the returned diverse target from three to five while returning an explicit shortage reason.
- **Rationale**: The repository already implements feasible pool enumeration and deterministic diversity. Reusing it avoids a second optimizer and satisfies the roadmap's complete-candidate principle.
- **Alternatives considered**: Generating candidates with an LLM violates feasibility-first; creating five profile names would conflate objective labels with true solution diversity.

## Decision 3: Use stdlib SQLite for local evidence persistence

- **Decision**: Store acceptance records and shadow observations in an append-only SQLite database configured by `ACCEPTANCE_DB_PATH`, with a runtime default under `BE/data/` and schema initialization on first use.
- **Rationale**: SQLite supports code-first local setup, transactions, idempotency uniqueness, inspection in DBeaver, and export without a new dependency or database service.
- **Alternatives considered**: In-memory state loses demo evidence on restart; JSON append files make idempotency and concurrent writes fragile; PostgreSQL would add installation/operations work not justified for this local MVP.

## Decision 4: Make shadow judging opt-in, deterministic in sampling, and non-authoritative

- **Decision**: Add a shadow service that receives only hard-gate-passing plans, anonymizes the first-pass facts, compares forward and reverse order, treats disagreement as a tie, records observations, and never changes the response order. A stable trip-id hash controls an environment-configured canary rate capped at 10%; default is off.
- **Rationale**: This measures position/verbosity behavior without risking user-visible feasibility or introducing response nondeterminism.
- **Alternatives considered**: Always invoking a local LLM would make offline demo and tests unreliable; letting judge rank control the response before calibration contradicts roadmap promotion gates.

## Decision 5: Separate readiness evidence from later training

- **Decision**: Expose counts and threshold booleans for pairwise judgments, complete accepted days, retrieval-ready days, and judge calibration; do not train or retrieve in this feature.
- **Rationale**: The roadmap explicitly requires 150 pairwise samples, 40 accepted days, and 50–200 retrieval-ready days. Reporting progress is honest and creates a stable future integration seam.
- **Alternatives considered**: Training on seeded or synthetic demo choices would make evaluation claims invalid; implementing RAG with an empty library would add complexity without user value.

## Decision 6: Restore the existing Flutter kit, not a second HTML application

- **Decision**: Reuse the tracked Flutter shell/theme/map assets from `origin/feat/002-trip-management-mvp`, preserve the newer HTML harness files, and replace the older management repository assumptions with current planner, selection, acceptance, readiness, and expense contracts plus seeded fallback state.
- **Rationale**: The project constitution names Flutter as primary, the existing shell already implements the requested 390×844 laptop frame and PMTiles web map, and the declared packages are already approved.
- **Alternatives considered**: A new responsive HTML mock would duplicate UI technology; merging the older backend would overwrite newer planner work and create major conflicts.

## Decision 7: Preserve root prototype independently

- **Decision**: Keep `index.html`, `server.py`, root PMTiles, search/routing and vehicle controls untouched except for documentation or test commands.
- **Rationale**: They are explicit Definition-of-Done regressions and a useful low-level map/routing demo separate from the Flutter experience.
- **Alternatives considered**: Moving all root behavior into Flutter is too large for this roadmap slice and would risk existing offline map behavior.
