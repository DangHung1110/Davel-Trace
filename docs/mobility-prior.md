# M1 mobility prior (T062, lane A) — PARTIAL, no tick

Source: Foursquare TSMC2014 NYC (227,428) + Tokyo (573,703) check-ins.
Page alive 2026-09-28; original mirror it-sudparis.eu DEAD (DNS) →
mirror used: HuggingFace `Davidham3/FourSquare_NYC_TKY`
(dataset_tsmc2014.zip, 25.5MB). Raw TSVs stay in TEMP, never committed.

## Crosswalk (`BE/ml/patm/crosswalk.json`)

251 venue categories → 10 DN canonicals (mirror `estimate_duration.py`).
Commute/work/home/civic (train stations, offices, homes, hotels, gyms…)
are EXCLUDED — trajectories split on them (tourist transitions only).
Tail via ordered keyword rules; file also fixes a real encoding trap
(TSVs are latin-1: "Café" mangles under utf-8).

## Prior (`transition_prior.json`)

P(next_cat | prev_cat, bucket), buckets sang/trua/chieu/toi (local hour),
consecutive same-user check-ins gap ≤12h, add-1 smoothing, user-level
80/20 split (train users ≠ held users, no leakage).

## Eval (REAL numbers, seed 7)

Held-out n=85,077 transitions:
- accuracy@1: prior **0.4835** vs unigram **0.4563** → **+6.0% relative** (bar +10%: SHORT)
- perplexity: prior **4.24** vs unigram **4.76** → **−10.9% relative** (bar +10%: MET)

Ablation (hermetic `foursquare_sample.json`, 600 held-out directions,
fixed w=0.1, actual hour): rule **0.510** vs +prior **0.520** →
**+1.0pp** (bar +5pp: SHORT). w-sweep landscape flat (best +1.0pp at
w=0.1; larger w hurts; prior-alone 0.497 < rule). Direction on symmetric
tourist pairs (restaurant↔cafe both ways common) is inherently ~coin-flip;
the prior's value is distributional (perplexity), not directional.

Seed-pairs ablation declared INVALID (ceiling artifact): rule labels are
rule-generated (38/38 perfect), so any perturbation can only hurt
(measured −23.7pp). Documented in test, not used as a bar.

## Verdict

PARTIAL — feature wired (`prior_logp` #17 in features.py, train hook
dynamic, tests green) but bars not fully met → **NO T062 tick**.
Revisit when: full-snapshot pairs (T028) give a real ablation ground,
or a bigger w-study with nested validation.
