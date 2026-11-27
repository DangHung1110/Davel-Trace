"""Fit nonnegative Bradley–Terry weights with a fixed value anchor.

The renderer key is discovered beside labels/pairs, or supplied with --key.
"""
import argparse
import json
import math
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from BE.app.services import objective
from BE.ml.objective.gen_pairs import COEFS, SCHEMA_VERSION, file_hash, weights_hash
from BE.ml.objective.render_pairs import pair_hash


def rows(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s.strip()]


def validate_dataset(path, pairs, base):
    """Reject old/mixed pilots and changed objective/data before fitting any label."""
    sidecar = Path(str(path) + '.manifest.json')
    if not sidecar.is_file():
        raise ValueError('Missing dataset manifest; generate pairs with the current pipeline')
    meta = json.loads(sidecar.read_text(encoding='utf-8'))
    expected = {'schema_version': SCHEMA_VERSION, 'feature_schema': objective.FEATURE_SCHEMA,
                'a2_rule': objective.A2_RULE, 'features': list(objective.FEATURES),
                'baseline_weights_sha256': weights_hash(base)}
    if any(meta.get(k) != v for k, v in expected.items()):
        raise ValueError('Incompatible dataset schema/objective/weights; regenerate this pilot')
    if not meta.get('complete') or meta.get('pairs_sha256') != file_hash(path):
        raise ValueError('Dataset is incomplete or its contents do not match the manifest')
    root = Path(__file__).resolve().parents[3]
    source_root = Path(meta['repo_root'])
    for source, digest in meta['hashes'].items():
        original = Path(source)
        if original.is_relative_to(source_root):
            current = root / original.relative_to(source_root)
            if not current.is_file() or file_hash(current) != digest:
                raise ValueError(f'Dataset code/data changed: {current}; regenerate this pilot')
    provenance = {k: meta[k] for k in ('feature_schema', 'a2_rule',
                                      'baseline_weights_sha256', 'dataset_sha256')}
    for pair in pairs:
        if (pair.get('schema_version') != SCHEMA_VERSION
                or any((pair.get('context') or {}).get(k) != v for k, v in provenance.items())
                or pair.get('id') not in meta['request_ids']):
            raise ValueError('Pair provenance does not match its dataset manifest')
        design(pair, 'base', base)
    return meta


def consistent(pairs, labels, key):
    votes = {}
    for label in labels:
        k, attempt = int(label['pair']), int(label['pass'])
        if not 1 <= k <= len(pairs) or attempt not in (1, 2):
            raise ValueError('Invalid pair/pass')
        winner = label['winner']
        if winner not in ('left', 'right', 'tie'):
            raise ValueError('Invalid winner')
        mapping = key[f'P{k}-{attempt}']
        if mapping['id'] != pairs[k - 1]['id']:
            raise ValueError('Key does not match pair request id')
        if mapping.get('pair_sha256') != pair_hash(pairs[k - 1]):
            raise ValueError('Key does not match pair contents')
        if mapping.get('left') not in ('base', 'perturbed'):
            raise ValueError('Invalid left mapping in renderer key')
        vote = mapping['left'] if winner == 'left' else ('perturbed' if mapping['left'] == 'base' else 'base')
        if winner == 'tie':
            vote = 'tie'
        if attempt in votes.setdefault(k, {}):
            raise ValueError('Duplicate pair/pass label')
        votes[k][attempt] = vote
    kept = [(pairs[k - 1], v[1]) for k, v in sorted(votes.items())
            if len(v) == 2 and v[1] == v[2] and v[1] != 'tie']
    ties = sum(any(w == 'tie' for w in v.values()) for v in votes.values())
    contradictions = sum(len(v) == 2 and 'tie' not in v.values() and v[1] != v[2]
                         for v in votes.values())
    missing = len(pairs) - sum(len(v) == 2 for v in votes.values())
    print(f'Consistency: {len(kept)}/{len(pairs)} ({len(kept) / max(1, len(pairs)):.1%}); '
          f'ties={ties}, contradictions={contradictions}, incomplete={missing}')
    return kept


def design(pair, winner, base):
    # Taking objective_value differences keeps food-tour and profile overrides exact.
    for side in ('fA', 'fB'):
        if (set(pair[side]) != set(objective.FEATURES)
                or any(not math.isfinite(v) for v in pair[side].values())):
            raise ValueError('Incompatible/nonfinite features; regenerate with the current schema')
    spec = objective.build_spec(pair['trip'], w=base, profile='balanced')
    delta = {k: pair['fA'][k] - pair['fB'][k] for k in objective.FEATURES}
    baseline = objective.objective_value(delta, spec)
    x = []
    for name in COEFS:
        from dataclasses import replace
        bumped = replace(spec, w={**spec.w, name: spec.w[name] + 1})
        x.append(objective.objective_value(delta, bumped) - baseline)
    offset = baseline - sum(base[k] * v for k, v in zip(COEFS, x))
    sign = 1 if winner == 'base' else -1
    return sign * offset, [sign * v for v in x]


def loss_gradient(ratios, examples, base_values, regularization):
    loss = regularization * sum((r - 1) ** 2 for r in ratios)
    grad = [2 * regularization * (r - 1) for r in ratios]
    for offset, x in examples:
        z = offset + sum(r * c * v for r, c, v in zip(ratios, base_values, x))
        loss += max(0, -z) + math.log1p(math.exp(-abs(z)))
        p = math.exp(-abs(z))
        wrong = p / (1 + p) if z >= 0 else 1 / (1 + p)
        for j, (c, v) in enumerate(zip(base_values, x)):
            grad[j] -= wrong * c * v
    return loss, grad


def fit(examples, base, regularization=1.0):
    if not examples:
        raise ValueError('No consistent training pairs')
    values = [base[k] for k in COEFS]
    try:
        from scipy.optimize import minimize
    except ImportError:
        minimize = None
    ratios = [1.0] * len(COEFS)
    if minimize:
        result = minimize(lambda r: loss_gradient(r, examples, values, regularization), ratios,
                          jac=True, method='L-BFGS-B', bounds=[(0, None)] * len(ratios),
                          options={'maxiter': 2000})
        if not result.success:
            raise RuntimeError(result.message)
        ratios = result.x
    else:
        # Projected gradient with backtracking requires only the standard library.
        for _ in range(5000):
            loss, grad = loss_gradient(ratios, examples, values, regularization)
            step = 1.0
            for _ in range(60):
                trial = [max(0, r - step * g) for r, g in zip(ratios, grad)]
                new_loss, _ = loss_gradient(trial, examples, values, regularization)
                if new_loss <= loss:
                    break
                step *= 0.5
            if max(abs(a - b) for a, b in zip(trial, ratios)) < 1e-9:
                break
            ratios = trial
    return {**base, **{k: max(0.0, float(r * c)) for k, r, c in zip(COEFS, ratios, values)}}


def split(data, holdout):
    ids = sorted({pair['id'] for pair, _ in data})
    if len(ids) < 2:
        raise ValueError('Need at least two request ids for train/holdout')
    random.Random(42).shuffle(ids)
    held = set(ids[:max(1, min(len(ids) - 1, round(len(ids) * holdout)) )])
    return ([p for p in data if p[0]['id'] not in held], [p for p in data if p[0]['id'] in held])


def accuracy(examples, weights):
    return sum(offset + sum(weights[k] * v for k, v in zip(COEFS, x)) > 0
               for offset, x in examples) / len(examples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('pairs', 'labels', 'out_weights'):
        parser.add_argument(name)
    parser.add_argument('--lambda', dest='regularization', type=float, default=1.0)
    parser.add_argument('--holdout', type=float, default=0.25)
    parser.add_argument('--key', help='Renderer .md.key.json; otherwise auto-discover a unique sidecar')
    args = parser.parse_args()
    if args.regularization < 0 or not 0 < args.holdout < 1:
        parser.error('lambda must be nonnegative; holdout must be between zero and one')
    keys = sorted({p.resolve() for directory in (Path(args.labels).parent, Path(args.pairs).parent)
                   for p in directory.glob('*.md.key.json')})
    if not args.key and len(keys) != 1:
        parser.error('Supply --key when there is not exactly one renderer key beside labels/pairs')
    key = json.loads(Path(args.key or keys[0]).read_text(encoding='utf-8'))
    pairs = rows(args.pairs)
    base = objective.weights('v1')
    validate_dataset(args.pairs, pairs, base)
    data = consistent(pairs, rows(args.labels), key)
    train, held = split(data, args.holdout)
    learned = fit([design(p, w, base) for p, w in train], base, args.regularization)
    examples = [design(p, w, base) for p, w in held]
    print(f'Train {len(train)}, holdout {len(held)}; accuracy v1={accuracy(examples, base):.3f}, learned={accuracy(examples, learned):.3f}')
    for k in COEFS:
        print(f'{k}: {base[k]:.6g} -> {learned[k]:.6g} ({(learned[k] / base[k] - 1):+.1%})')
    learned['note'] = f'Bradley-Terry learned from {len(train)} consistent preference pairs; seed 42; lambda={args.regularization}; value anchor=1. Profile overrides unchanged.'
    Path(args.out_weights).write_text(json.dumps(learned, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
