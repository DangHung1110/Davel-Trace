"""Audit feature coverage and raw/final drift of a generated pilot."""
import json
from collections import Counter
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from BE.app.services import objective
from BE.ml.objective.gen_pairs import COEFS, file_hash
from BE.ml.objective.train_bt import design, rows, validate_dataset


def load_audit(path, meta):
    audit_path = str(path) + '.audit.jsonl'
    if meta.get('audit_sha256') != file_hash(audit_path):
        raise ValueError('Audit contents do not match the completed dataset manifest')
    audit = rows(audit_path)
    if (len(audit) != len(meta['request_ids'])
            or {r['id'] for r in audit} != set(meta['request_ids'])):
        raise ValueError('Audit request IDs/count do not match the completed manifest')
    return audit


def analyze(path):
    pairs = rows(path)
    base = objective.weights('v1')
    meta = validate_dataset(path, pairs, base)
    audit = load_audit(path, meta)
    features = {}
    for name in objective.FEATURES:
        values = [p[s].get(name, 0) for p in pairs for s in ('fA', 'fB')]
        deltas = [p['fA'].get(name, 0) - p['fB'].get(name, 0) for p in pairs]
        features[name] = {'min': min(values, default=0), 'max': max(values, default=0),
                          'nonzero_pair_deltas': sum(abs(d) > 1e-8 for d in deltas)}
    xs = [design(p, 'base', base)[1] for p in pairs]
    signal = {k: sum(abs(x[j]) > 1e-8 for x in xs) for j, k in enumerate(COEFS)}
    sides = [r[s] for r in audit for s in ('A', 'B') if r[s]['has_plan']]
    drifts = [abs(s['raw_j'] - s['final_j']) for s in sides]
    return {'a2_rule': meta.get('a2_rule', 'legacy_or_all_pairs'),
            'requests': len(audit), 'kept_pairs': len(pairs),
            'retention_rate': len(pairs) / max(1, len(audit)),
            'statuses': {k: sum(r['status'] == k for r in audit)
                         for k in sorted({r['status'] for r in audit})},
            'solved_sides': len(sides), 'gate_failed_sides': sum(not s['gate_passed'] for s in sides),
            'max_raw_formula_error': max((abs(s['raw_error']) for s in sides), default=0),
            'polish_changed_j_sides': sum(d > .03 for d in drifts),
            'polish_decreased_j_sides': sum(s['final_j'] < s['raw_j'] - 1e-6 for s in sides),
            'max_polish_j_drift': max(drifts, default=0),
            'median_request_seconds': statistics.median([r['elapsed_s'] for r in audit]) if audit else None,
            'features': features, 'coefficient_nonzero_pair_deltas': signal,
            'coefficients_to_keep_at_prior': [k for k, count in signal.items() if count == 0],
            'limitations': ['Pilot is development data, not a final model evaluation.',
                           'Nonzero deltas do not prove coefficients are independently identifiable.',
                           'No live forecast: offline state prior only.',
                           'Do not mix pairs generated under different a2_rule/code versions.']}


def compare_pilots(before, after):
    """Compare base plans on identical requests/data; do not compare changed J."""
    manifests = [json.loads(Path(str(p) + '.manifest.json').read_text(encoding='utf-8'))
                 for p in (before, after)]
    protected = ('request_ids', 'seed', 'profile', 'cap', 'deterministic_time',
                 'search_scale', 'workers', 'solver_workers', 'timeout_s', 'weather')
    if any(manifests[0].get(k) != manifests[1].get(k) for k in protected):
        raise ValueError('Pilot requests/config differ; comparison is not paired')
    hashes = [{k: v for k, v in m['hashes'].items() if not k.endswith('.py')}
              for m in manifests]
    if hashes[0] != hashes[1]:
        raise ValueError('Pilot input data/weights differ')
    audits = [{r['id']: r for r in load_audit(p, m)}
              for p, m in zip((before, after), manifests)]
    if (not all(m.get('complete') for m in manifests)
            or any(set(a) != set(manifests[0]['request_ids']) for a in audits)):
        raise ValueError('Pilot audit is incomplete')

    def summarize(audit):
        sides = [r['A'] for r in audit.values() if r['A']['has_plan']]
        fs = [s['final_features'] for s in sides]
        return {'plans': len(sides), 'gate_passed': sum(s['gate_passed'] for s in sides),
                'median_ride_min': statistics.median(f['ride'] for f in fs) if fs else None,
                'mean_zone_changes': statistics.mean(f['zone'] for f in fs) if fs else None,
                'mean_meal_bonus': statistics.mean(f['meal'] for f in fs) if fs else None,
                'plans_with_rest': sum(f['rest'] > 0 for f in fs),
                'duplicates': {k: sum(f[k] > 0 for f in fs)
                               for k in ('same_site', 'umbrella', 'market', 'dish')},
                'solver_statuses': dict(Counter(s['solver_status'] for s in sides)),
                'median_request_seconds': statistics.median(r['elapsed_s'] for r in audit.values())}

    changes = []
    for pid in manifests[0]['request_ids']:
        old, new = audits[0][pid]['A'], audits[1][pid]['A']
        if old['has_plan'] and new['has_plan']:
            changes.append({'id': pid, **{
                k: new['final_features'][k] - old['final_features'][k]
                for k in ('ride', 'zone', 'meal', 'rest')}})
    return {'requests': len(audits[0]), 'scope': 'base A only, paired same inputs',
            'before': summarize(audits[0]), 'after': summarize(audits[1]),
            'ride_lower_equal_higher': {name: sum(test(r['ride']) for r in changes)
                for name, test in (('lower', lambda x: x < -1e-8),
                                   ('equal', lambda x: abs(x) <= 1e-8),
                                   ('higher', lambda x: x > 1e-8))},
            'meal_bonus_higher': sum(r['meal'] > 1e-8 for r in changes),
            'meal_bonus_lower': sum(r['meal'] < -1e-8 for r in changes),
            'per_request_changes': changes,
            'note': 'J and meal_crowd are not compared across different A2 formulas; timings are observational.'}


if __name__ == '__main__':
    report = analyze(sys.argv[1])
    if len(sys.argv) > 3:
        report['comparison'] = compare_pilots(sys.argv[3], sys.argv[1])
    Path(sys.argv[2]).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('features', 'limitations')}, indent=2))
