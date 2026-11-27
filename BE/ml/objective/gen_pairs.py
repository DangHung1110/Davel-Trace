"""Generate reproducible preference pairs and audit every attempted request.

python gen_pairs.py <repo> <teacher_data_dir> <test_ids.json> <out.jsonl> [n] [workers]
"""
import glob
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from BE.app.services import objective, trip_ctx
from reports.objective_v1.scripts import eval_objective as ev

COEFS = ('w_state', 'repeat_scale', 'gamma', 'meal_scale', 'meal_crowd',
         'rest_scale', 'pace_scale', 'tau', 'tau_long', 'zeta', 'w_edge',
         'dup_same_site', 'dup_umbrella', 'dup_market', 'dup_dish')
SEED = 42
RAW_TOLERANCE = .03
SCHEMA_VERSION = 4


def weights_hash(weights):
    return hashlib.sha256(json.dumps(weights, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def records(data_dir, test_ids, count):
    held = set(json.loads(Path(test_ids).read_text(encoding='utf-8')))
    found = {}
    for filename in sorted(glob.glob(str(Path(data_dir) / '**/teacher_*.jsonl'), recursive=True)):
        for line in Path(filename).read_text(encoding='utf-8').splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (r.get('id', '').startswith('gv2-') and r['id'] not in held
                    and 'error' not in r and r.get('solution')):
                found[r['id']] = r
    return [found[k] for k in sorted(found)[:count]]


def solve_plan(rec):
    from BE.common import merged_into
    g = ev._G
    trip = {**rec['trip'], 'profile': rec['profile'], 'meals': True}
    trip['must_visit'] = [merged_into(g['by_id'].get(p)) or p for p in trip.get('must_visit') or []]
    # Offline prior only: no live forecast or machine-clock-dependent network data.
    ctx = trip_ctx.build(trip, trip['profile'], fetch_weather=False)
    found = g['retrieval'].retrieve(trip, g['pois'])
    ranked = g['rank'].rank([g['by_id'][c['poi_id']] for c in found['candidates']],
                            {'budget': trip['budget']}, ctx)
    plan = g['profiles'].build_plan('balanced', trip, ranked, g['by_id'], g['cells'], ctx=ctx,
                                   workers=1, timeout_s=60, deterministic_time=5, diagnose=False)
    return trip, plan


def view(plan):
    from BE.common import hhmm, party_size, to_min
    ctx = plan['_context']
    stops = []
    previous = ctx.get('origin_id')
    for a in plan.get('activities') or []:
        pid = a['poi_id']
        p, stub = ev._G['by_id'][pid], ctx['stubs'][pid]
        stops.append({**{k: a[k] for k in ('poi_id', 'start', 'end')},
                      'name': p.get('name'), 'category': stub.category,
                      'group': stub.group, 'zone': stub.zone, 'fee': stub.fee,
                      'ride_min_from_prev': ctx['travel'].get((previous, pid), 0)})
        previous = pid
    f = objective.plan_features(plan)
    rest = None
    if f['rest']:
        lunch = next(s for s in stops if objective.is_lunch(ctx['stubs'][s['poi_id']],
                     to_min(s['start']), to_min(s['end']) - to_min(s['start'])))
        rest = {'start': lunch['end'], 'end': hhmm(to_min(lunch['end']) + ctx['rest_minutes']),
                'minutes': ctx['rest_minutes']}
    fees = sum(s['fee'] for s in stops)
    return {'stops': stops, 'rest': rest,
            'totals': {'ride_min': f['ride'], 'stops': len(stops),
                       'return_ride_min': ctx['travel'].get((previous, ctx.get('origin_id')), 0),
                       'wait_min': f['wait'],
                       'meals': sum(ctx['stubs'][s['poi_id']].restaurant for s in stops),
                       'fee_per_person': fees, 'fee_party': fees * party_size(ctx['trip'])}}


def audit_plan(plan):
    ctx = plan.get('_context') or {}
    snapshot = plan.get('_features') or {}
    if not plan.get('activities'):
        return {'has_plan': False, 'solver_status': snapshot.get('status')}
    raw = objective.plan_features(plan, raw=True)
    final = objective.plan_features(plan)
    raw_j = objective.objective_value(raw, ctx['spec'])
    gate = ev._G['gate'].report({'activities': plan['activities']}, ctx['trip'],
                                ev._G['by_id'], ev._G['cells'])
    return {'has_plan': True, 'solver_status': snapshot['status'],
            'solver_j': snapshot['solver_j'], 'raw_j': raw_j,
            'raw_error': raw_j - snapshot['solver_j'],
            'final_j': objective.objective_value(final, ctx['spec']),
            'raw_features': raw, 'final_features': final,
            'gate_passed': gate['passed'], 'gate_failed': gate['failed']}


def generate(job):
    rec, data_dir, provenance = job
    started = time.monotonic()
    rng = random.Random(f'objective-v1:{SEED}:' + rec['id'])
    changed = {k: rng.choice((.4, 2.5)) for k in rng.sample(COEFS, rng.randint(1, 2))}
    w = objective.weights('v1')
    for k, factor in changed.items():
        w[k] *= factor
    content = json.dumps(w, sort_keys=True)
    weights_dir = Path(data_dir) / 'weights'
    weights_dir.mkdir(exist_ok=True)
    path = weights_dir / (rec['id'] + '-' + hashlib.sha256(content.encode()).hexdigest()[:16] + '.json')
    if not path.exists():
        path.write_text(content, encoding='utf-8')
    previous = os.environ.get('DAVEL_OBJECTIVE')
    try:
        os.environ['DAVEL_OBJECTIVE'] = 'v1'
        trip, a = solve_plan(rec)
        os.environ['DAVEL_OBJECTIVE'] = str(path)
        _, b = solve_plan(rec)
    finally:
        if previous is None:
            os.environ.pop('DAVEL_OBJECTIVE', None)
        else:
            os.environ['DAVEL_OBJECTIVE'] = previous
    audit = {'id': rec['id'], 'perturbed': changed, 'A': audit_plan(a), 'B': audit_plan(b),
             'elapsed_s': round(time.monotonic() - started, 3)}
    if not all(audit[s]['has_plan'] for s in ('A', 'B')):
        audit['status'] = 'no_plan'
    elif not all(audit[s]['gate_passed'] for s in ('A', 'B')):
        audit['status'] = 'gate_failed'
    elif any(abs(audit[s]['raw_error']) > RAW_TOLERANCE for s in ('A', 'B')):
        audit['status'] = 'formula_mismatch'
    elif any(audit[s]['final_j'] < audit[s]['raw_j'] - 1e-6 for s in ('A', 'B')):
        audit['status'] = 'polish_decreased_j'
    elif [s['poi_id'] for s in a['activities']] == [s['poi_id'] for s in b['activities']]:
        audit['status'] = 'same_stops'
    else:
        audit['status'] = 'kept'
    pair = None
    if audit['status'] == 'kept':
        pair = {'schema_version': SCHEMA_VERSION, 'id': rec['id'],
                'trip': trip,
                'context': {'weather': 'offline_prior_no_forecast', 'dynamic_state': bool(trip['profile']),
                            **provenance},
                'perturbed': changed, 'A': view(a), 'B': view(b),
                'fA': audit['A']['final_features'], 'fB': audit['B']['final_features']}
    return audit, pair


def manifest(repo, data, test_ids, todo, workers):
    root = Path(repo)
    sources = [root / 'BE/common.py', *sorted((root / 'BE/app/services').glob('*.py')),
               *sorted((root / 'BE/ml/objective').glob('*.py'))]
    snapshot = root / 'BE/data/snapshots/danang-v2'
    data_files = [snapshot / 'pois.json', snapshot / 'matrix.json',
                  root / 'BE/app/services/objective_weights/v1.json', Path(test_ids)]
    teachers = sorted(Path(data).rglob('teacher_*.jsonl'))
    meta = {'schema_version': SCHEMA_VERSION, 'a2_rule': objective.A2_RULE,
            'feature_schema': objective.FEATURE_SCHEMA, 'features': list(objective.FEATURES),
            'baseline_weights_sha256': weights_hash(objective.weights('v1')),
            'repo_root': str(root.resolve()),
            'seed': SEED, 'profile': 'balanced', 'cap': 40,
            'deterministic_time': 5, 'search_scale': objective.weights('v1')['search_scale'],
            'workers': workers, 'solver_workers': 1, 'timeout_s': 60,
            'weather': 'offline_prior_no_forecast', 'raw_tolerance': RAW_TOLERANCE,
            'purpose': 'pilot_development_only_not_final_test',
            'request_ids': [r['id'] for r in todo],
            'hashes': {str(p): file_hash(p) for p in sources + data_files + teachers}}
    meta['dataset_sha256'] = hashlib.sha256(json.dumps(meta, sort_keys=True).encode()).hexdigest()
    return meta


def main():
    repo, data, test_ids, out = map(os.path.abspath, sys.argv[1:5])
    count = int(sys.argv[5]) if len(sys.argv) > 5 else 40
    workers = int(sys.argv[6]) if len(sys.argv) > 6 else 1
    if count < 1 or workers < 1:
        raise ValueError('n_requests and workers must be positive')
    output = Path(out)
    output.parent.mkdir(parents=True, exist_ok=True)
    todo = records(data, test_ids, count)
    if not todo:
        raise ValueError('No eligible requests')
    meta = manifest(repo, data, test_ids, todo, workers)
    provenance = {k: meta[k] for k in ('feature_schema', 'a2_rule',
                                      'baseline_weights_sha256', 'dataset_sha256')}
    meta_path, audit_path = Path(str(output) + '.manifest.json'), Path(str(output) + '.audit.jsonl')
    if any(p.exists() for p in (output, meta_path, audit_path)):
        raise FileExistsError('Use a fresh output path; pilot artifacts must not be overwritten')
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    counts = {}
    with mp.get_context('spawn').Pool(workers, initializer=ev.init,
            initargs=(repo, 'v1:balanced', str(output.parent))) as pool, \
            output.open('x', encoding='utf-8') as fh, audit_path.open('x', encoding='utf-8') as ah:
        for i, (audit, pair) in enumerate(pool.imap(generate,
                [(r, str(output.parent), provenance) for r in todo]), 1):
            ah.write(json.dumps(audit, ensure_ascii=False) + '\n')
            ah.flush()
            status = audit['status']
            counts[status] = counts.get(status, 0) + 1
            if pair:
                fh.write(json.dumps(pair, ensure_ascii=False) + '\n')
                fh.flush()
            print(f'[{i}/{len(todo)}] {audit["id"]}: {status} ({audit["elapsed_s"]}s)', flush=True)
    meta.update(counts=counts, complete=True, pairs_sha256=file_hash(output), audit_sha256=file_hash(audit_path))
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(todo)} requests, {counts.get("kept", 0)} differing valid pairs -> {output}')


if __name__ == '__main__':
    main()
