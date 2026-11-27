"""Checks for objective extraction, blind labels and bounded ranking learning."""
import json
import random
from tempfile import TemporaryDirectory
from pathlib import Path

from BE.app.services import objective
from BE.ml.objective import gen_pairs, render_pairs, train_bt
from BE.tests.unit.test_objective_v1 import _day, _spec, _solve


def _snapshot_plan(activities, stubs, travel, spec, out=None, **ctx):
    from BE.app.services.profiles import _plan_features
    out = out or {'itinerary': {'activities': activities}}
    trip = {'start_time': '08:00', 'end_time': '18:00'}
    limits = {'rest_minutes': ctx.get('rest_minutes'), 'rest_after_lunch': True}
    return {'activities': activities, '_features': _plan_features(
        out, activities, stubs, travel, trip, spec, None, ctx.get('state_bands'),
        ctx.get('state_scores'), ctx.get('state_costs'), limits)}


def test_objective_plan_features():
    pois, travel = _day()
    spec = _spec(k0=4)
    out = _solve(pois, travel, spec)
    plan = _snapshot_plan(out['itinerary']['activities'], pois, travel, spec, out)
    assert abs(objective.objective_value(objective.plan_features(plan), spec)
               - out['objective'] / (1000 * out['unit'])) < .01
    assert objective.plan_features({}) is None


def test_objective_training_recovers_ranking():
    rng = random.Random(12)
    base = objective.weights('v1')
    known = {**base, 'tau': .12, 'repeat_scale': .2, 'w_state': 2.0}
    data = []
    for i in range(500):
        fa = {k: rng.uniform(0, 3) for k in objective.FEATURES}
        fb = {k: rng.uniform(0, 3) for k in objective.FEATURES}
        fa['ride'], fb['ride'] = rng.uniform(0, 100), rng.uniform(0, 100)
        p = {'id': str(i), 'trip': {}, 'fA': fa, 'fB': fb}
        spec = objective.build_spec({}, w=known, profile='balanced')
        winner = 'base' if objective.objective_value(fa, spec) > objective.objective_value(fb, spec) else 'perturbed'
        data.append((p, winner))
    train, held = train_bt.split(data, .25)
    learned = train_bt.fit([train_bt.design(p, w, base) for p, w in train], base, .001)
    assert train_bt.accuracy([train_bt.design(p, w, base) for p, w in held], learned) > .9
    assert all(learned[k] >= 0 for k in gen_pairs.COEFS)
    assert learned['profiles'] == base['profiles']


def test_objective_blind_swaps_and_consistency():
    with TemporaryDirectory() as tmp:
        p = {'id': 'gv2-1', 'trip': {}, 'A': {'stops': [], 'totals': {}},
             'B': {'stops': [], 'totals': {}}}
        out = Path(tmp) / 'sheet.md'
        render_pairs.render([p], out)
        key = json.loads(Path(str(out) + '.key.json').read_text())
        import pytest
        with pytest.raises(FileExistsError):
            render_pairs.render([p], out, seed=999)
        assert json.loads(Path(str(out) + '.key.json').read_text()) == key
        assert 'P1-2' not in out.with_suffix('.pass1.md').read_text(encoding='utf-8')
        assert 'P1-1' not in out.with_suffix('.pass2.md').read_text(encoding='utf-8')
        assert key['P1-1']['left'] != key['P1-2']['left']
        labels = [{'pair': 1, 'pass': n, 'winner': 'left' if key[f'P1-{n}']['left'] == 'base' else 'right'} for n in (1, 2)]
        assert train_bt.consistent([p], labels, key) == [(p, 'base')]
        labels[1]['winner'] = 'right' if labels[1]['winner'] == 'left' else 'left'
        assert train_bt.consistent([p], labels, key) == []
        labels[1]['winner'] = 'tie'
        assert train_bt.consistent([p], labels, key) == []
        digest = key['P1-1'].pop('pair_sha256')
        with pytest.raises(ValueError, match='contents'):
            train_bt.consistent([p], labels, key)
        key['P1-1'].update(pair_sha256=digest, left='unknown')
        with pytest.raises(ValueError, match='left mapping'):
            train_bt.consistent([p], labels, key)


def test_objective_training_design_matches_food_tour():
    base = objective.weights('v1')
    for trip in ({}, {'activities': ['food tour']}):
        pair = {'trip': trip, 'fA': {k: 2.0 for k in objective.FEATURES},
                'fB': {k: .5 for k in objective.FEATURES}}
        offset, x = train_bt.design(pair, 'base', base)
        spec = objective.build_spec(trip, w=base, profile='balanced')
        expected = objective.objective_value(pair['fA'], spec) - objective.objective_value(pair['fB'], spec)
        assert abs(offset + sum(base[k] * v for k, v in zip(gen_pairs.COEFS, x)) - expected) < 1e-9


def test_objective_records_exclude_heldout():
    with TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / 'teacher_sample.jsonl').write_text('\n'.join(json.dumps({'id': k, 'solution': [1]}) for k in ('gv2-2', 'gv2-1', 'other')))
        (folder / 'ids.json').write_text('["gv2-1"]')
        assert [r['id'] for r in gen_pairs.records(folder, folder / 'ids.json', 4)] == ['gv2-2']

def test_objective_build_plan_exposes_solve_context():
    from unittest.mock import patch
    from BE.app.services.profiles import build_plan
    from BE.tests.unit.test_profile_objectives import COST_TRIP, COST_RANKED, COST_BY_ID, COST_CELLS
    with patch.dict('os.environ', {'DAVEL_OBJECTIVE': 'v1'}):
        plan = build_plan('balanced', COST_TRIP, COST_RANKED, COST_BY_ID, COST_CELLS,
                          template='', workers=1, deterministic_time=1)
    ctx = plan['_context']
    assert ctx['start_min'] == 480 and ctx['end_min'] == 1080
    assert ctx['origin_id'] is None
    assert set(a['poi_id'] for a in plan['activities']) <= ctx['stubs'].keys()
    assert objective.plan_features(plan) is not None


def test_objective_rain_cost_matches_solver():
    pois, travel = _day()
    spec = _spec(k0=4)
    costs = {(p.poi_id, 0): .5 for p in pois}
    out = _solve(pois, travel, spec, state_bands=[(480, 1080)], state_cost=costs)
    plan = _snapshot_plan(out['itinerary']['activities'], pois, travel, spec, out,
                          state_bands=[(480, 1080)], state_costs=costs)
    f = objective.plan_features(plan)
    assert abs(objective.objective_value(f, spec)
               - out['objective'] / (1000 * out['unit'])) < .01


def test_objective_final_rest_is_not_raw_rest_flag():
    from BE.tests.unit.test_objective_v1 import _poi
    lunch = _poi('lunch', '', 'center', 3, restaurant=True, visit=30)
    museum = _poi('museum', 'history', 'center', 4, visit=60)
    activities = [
        {'poi_id': 'lunch', 'start': '12:00', 'end': '12:30'},
        {'poi_id': 'museum', 'start': '12:40', 'end': '13:40'}]
    plan = _snapshot_plan(activities, [lunch, museum], {}, _spec(), rest_minutes=45)
    assert objective.plan_features(plan)['rest'] == 0
    activities[1].update(start='13:15', end='14:15')
    plan = _snapshot_plan(activities, [lunch, museum], {}, _spec(), rest_minutes=45)
    assert objective.plan_features(plan)['rest'] == .25


def test_objective_state_uses_displayed_duration():
    from BE.tests.unit.test_objective_v1 import _poi
    stub = _poi('museum', 'history', 'center', 4, visit=40)
    plan = _snapshot_plan([{'poi_id': 'museum', 'start': '08:00', 'end': '10:00'}],
                          [stub], {}, _spec(), state_bands=[(480, 540), (540, 660)],
                          state_scores={('museum', 0): 1, ('museum', 1): 0})
    assert objective.plan_features(plan)['state'] == -.5


def test_objective_end_only_change_is_retimed():
    from BE.tests.unit.test_objective_v1 import _poi
    stub = _poi('museum', 'history', 'center', 4, visit=60)
    raw = [{'poi_id': 'museum', 'start': '08:00', 'end': '09:00'}]
    shown = [{'poi_id': 'museum', 'start': '08:00', 'end': '10:00'}]
    plan = _snapshot_plan(shown, [stub], {}, _spec(), {'itinerary': {'activities': raw}},
                          state_bands=[(540, 600)], state_scores={('museum', 0): 0})
    assert plan['_features']['retimed'] and plan['_features']['same_stops']
    assert objective.plan_features(plan, raw=True)['state'] == 0
    assert objective.plan_features(plan)['state'] == -.5


def test_objective_raw_and_final_features_are_separate():
    from unittest.mock import patch
    from BE.app.services import profiles
    from BE.app.services.optimizer import optimize
    from BE.tests.unit.test_profile_objectives import _poi
    pois = [_poi('breakfast', 'restaurant', 4.9, visit=30, hours=('07:00-10:30',)),
            _poi('museum', 'museum', 4.9, visit=45),
            _poi('lunch', 'restaurant', 4.9, visit=30, hours=('11:00-14:00',))]
    by_id = {p['poi_id']: p for p in pois}
    cells = {f'{a}->{b}': {'minutes': 5, 'km': .5} for a in by_id for b in by_id if a != b}
    trip = {'start_time': '07:00', 'end_time': '14:00', 'budget': 1000000,
            'profile': {'pace': 2}, 'must_visit': list(by_id),
            'order_prefs': [('breakfast', 'museum'), ('museum', 'lunch')]}
    with patch.dict('os.environ', {'DAVEL_OBJECTIVE': 'v1'}), \
            patch.object(profiles, 'optimize', wraps=optimize):
        plan = profiles.build_plan('balanced', trip, [{'poi_id': p} for p in by_id],
                                   by_id, cells, template='', workers=1)
    ctx = plan['_context']
    raw = objective.plan_features(plan, raw=True)
    snapshot = plan['_features']
    assert abs(objective.objective_value(raw, ctx['spec']) - snapshot['solver_j']) < .01
    assert snapshot['shown']['j'] >= snapshot['raw']['j'] - 1e-6
    assert raw['meal'] == objective.plan_features(plan)['meal']  # Guard keeps the meal bonus.
    raw['meal'] = -999
    assert objective.plan_features(plan, raw=True)['meal'] >= 0


def test_objective_training_keeps_rain_as_fixed_offset():
    base = objective.weights('v1')
    pair = {'trip': {}, 'fA': {k: 0. for k in objective.FEATURES},
            'fB': {k: 0. for k in objective.FEATURES}}
    pair['fA']['rain'] = 2.5
    offset, x = train_bt.design(pair, 'base', base)
    assert offset == -2.5 and all(abs(v) < 1e-9 for v in x)


def test_objective_generation_supplies_offline_context():
    from unittest.mock import Mock, patch
    rec = {'trip': {'start_time': '08:00', 'end_time': '18:00', 'budget': 1000000},
           'profile': {'pace': 2}}
    fake = {'by_id': {}, 'pois': [], 'cells': {},
            'retrieval': Mock(), 'rank': Mock(), 'profiles': Mock()}
    fake['retrieval'].retrieve.return_value = {'candidates': []}
    with patch.dict(gen_pairs.ev._G, fake, clear=True):
        gen_pairs.solve_plan(rec)
    ctx = fake['profiles'].build_plan.call_args.kwargs['ctx']
    assert ctx['dynamic_state'] is True and ctx['_forecast'] is None


def test_objective_judge_requires_complete_valid_labels():
    import pytest
    from BE.ml.objective.judge_pairs import parse_response
    labels = [{'pair': 1, 'pass': 1, 'winner': 'tie'}]
    assert parse_response({'result': json.dumps(labels)}, {(1, 1)}) == labels
    with pytest.raises(ValueError, match='missing'):
        parse_response({'result': '[]'}, {(1, 1)})
    with pytest.raises(ValueError, match='Invalid'):
        parse_response({'result': json.dumps(labels * 2)}, {(1, 1)})


def test_objective_distant_meals_pay_one_a2_pair():
    from BE.common import to_min
    from BE.tests.unit.test_objective_v1 import _poi
    pois = [_poi('breakfast', '', 'center', 4, restaurant=True, visit=30,
                 windows=((420, 480),)),
            _poi('lunch', '', 'center', 4, restaurant=True, visit=30,
                 windows=((660, 720),))]
    travel = {('breakfast', 'lunch'): 5, ('lunch', 'breakfast'): 5}
    spec = _spec(breakfast=True)
    out = _solve(pois, travel, spec, start=420, end=840,
                 must_visit=['breakfast', 'lunch'])
    acts = [{**a, 'start': to_min(a['start']), 'end': to_min(a['end'])}
            for a in out['itinerary']['activities']]
    assert abs(acts[1]['start'] - acts[0]['start']) > 150
    f = objective.features(acts, {p.poi_id: p for p in pois}, travel, spec, 420, 840)
    assert f['meal_crowd'] == 1
    assert abs(objective.objective_value(f, spec) - out['objective'] / (1000 * out['unit'])) < .01


def test_objective_meal_slot_crowding_remains_at_150_minutes():
    from BE.common import to_min
    from BE.tests.unit.test_objective_v1 import _poi
    pois = [_poi('early', '', 'center', 4, restaurant=True, visit=10, windows=((660, 670),)),
            _poi('late', '', 'center', 4, restaurant=True, visit=10, windows=((810, 820),))]
    travel = {('early', 'late'): 1, ('late', 'early'): 1}
    w = {**objective.weights('v1'), **dict.fromkeys(gen_pairs.COEFS, 0.), 'meal_crowd': 1.}
    spec = _spec(w=w, k0=None)
    out = _solve(pois, travel, spec, start=660, end=840, must_visit=['early', 'late'])
    acts = [{**a, 'start': to_min(a['start']), 'end': to_min(a['end'])}
            for a in out['itinerary']['activities']]
    f = objective.features(acts, {p.poi_id: p for p in pois}, travel, spec, 660, 840)
    assert f['meal_crowd'] == 2  # One A1 slot extra plus one A2 pair.
    assert objective.objective_value(f, spec) == out['objective'] / (1000 * out['unit']) == 0.


def test_objective_judge_refuses_paid_api_auth():
    import pytest
    from unittest.mock import Mock, patch
    from BE.ml.objective.judge_pairs import subscription_login
    result = Mock(returncode=0, stdout=json.dumps({'loggedIn': True, 'authMethod': 'api_key'}))
    with patch('BE.ml.objective.judge_pairs.subprocess.run', return_value=result):
        with pytest.raises(RuntimeError, match='paid API'):
            subscription_login('claude')
        result.stdout = json.dumps({'loggedIn': True, 'authMethod': 'claude.ai'})
        assert subscription_login('claude') == {'auth_method': 'claude.ai'}


def test_objective_pilot_comparison_requires_same_inputs():
    import pytest
    from BE.ml.objective.analyze_pairs import compare_pilots
    with TemporaryDirectory() as tmp:
        paths = [Path(tmp) / 'before.jsonl', Path(tmp) / 'after.jsonl']
        fs = {k: 0. for k in objective.FEATURES}
        for path, ride in zip(paths, (10., 5.)):
            meta = {'request_ids': ['r1'], 'hashes': {'snapshot.json': 'same'}, 'complete': True}
            Path(str(path) + '.manifest.json').write_text(json.dumps(meta), encoding='utf-8')
            side = {'has_plan': True, 'gate_passed': True, 'solver_status': 'optimal',
                    'final_features': {**fs, 'ride': ride}}
            Path(str(path) + '.audit.jsonl').write_text(json.dumps({
                'id': 'r1', 'A': side, 'B': side, 'elapsed_s': 1.}), encoding='utf-8')
            meta['audit_sha256'] = gen_pairs.file_hash(str(path) + '.audit.jsonl')
            Path(str(path) + '.manifest.json').write_text(json.dumps(meta), encoding='utf-8')
        comparison = compare_pilots(*paths)
        assert comparison['ride_lower_equal_higher'] == {'lower': 1, 'equal': 0, 'higher': 0}
        meta['hashes']['snapshot.json'] = 'different'
        Path(str(paths[1]) + '.manifest.json').write_text(json.dumps(meta), encoding='utf-8')
        with pytest.raises(ValueError, match='input data'):
            compare_pilots(*paths)


def test_objective_dataset_rejects_stale_or_mixed_provenance(tmp_path):
    import pytest
    root = Path(__file__).resolve().parents[3]
    ids = tmp_path / 'ids.json'
    ids.write_text('[]', encoding='utf-8')
    meta = gen_pairs.manifest(root, tmp_path, ids, [{'id': 'gv2-1'}], 1)
    context = {k: meta[k] for k in ('feature_schema', 'a2_rule',
                                   'baseline_weights_sha256', 'dataset_sha256')}
    pair = {'schema_version': gen_pairs.SCHEMA_VERSION, 'id': 'gv2-1', 'trip': {},
            'context': context, 'fA': dict.fromkeys(objective.FEATURES, 0.),
            'fB': dict.fromkeys(objective.FEATURES, 0.)}
    path = tmp_path / 'pairs.jsonl'
    path.write_text(json.dumps(pair) + '\n', encoding='utf-8')
    meta.update(complete=True, pairs_sha256=gen_pairs.file_hash(path))
    sidecar = Path(str(path) + '.manifest.json')
    sidecar.write_text(json.dumps(meta), encoding='utf-8')
    base = objective.weights('v1')
    assert train_bt.validate_dataset(path, [pair], base)['complete']
    from BE.ml.objective.analyze_pairs import analyze
    audit_path = Path(str(path) + '.audit.jsonl')
    audit_path.write_text('{}\n', encoding='utf-8')
    meta['audit_sha256'] = 'stale'
    sidecar.write_text(json.dumps(meta), encoding='utf-8')
    with pytest.raises(ValueError, match='Audit contents'):
        analyze(path)
    audit_path.write_text('{"id":"wrong-request"}\n', encoding='utf-8')
    meta['audit_sha256'] = gen_pairs.file_hash(audit_path)
    sidecar.write_text(json.dumps(meta), encoding='utf-8')
    with pytest.raises(ValueError, match='Audit request IDs/count'):
        analyze(path)
    with pytest.raises(ValueError, match='weights'):
        train_bt.validate_dataset(path, [pair], {**base, 'tau': base['tau'] * 2})
    pair['context']['a2_rule'] = 'legacy_or_all_pairs'
    with pytest.raises(ValueError, match='provenance'):
        train_bt.validate_dataset(path, [pair], base)
    pair['context']['a2_rule'] = objective.A2_RULE
    for old_schema in (2, 3):
        meta['schema_version'] = old_schema
        sidecar.write_text(json.dumps(meta), encoding='utf-8')
        with pytest.raises(ValueError, match='schema'):
            train_bt.validate_dataset(path, [pair], base)


def test_objective_training_refuses_old_or_nonfinite_features():
    import pytest
    pair = {'trip': {}, 'fA': dict.fromkeys(objective.FEATURES, 0.),
            'fB': dict.fromkeys(objective.FEATURES, 0.)}
    pair['fA'].pop('rain')
    with pytest.raises(ValueError, match='features'):
        train_bt.design(pair, 'base', objective.weights('v1'))
    pair['fA']['rain'] = float('nan')
    with pytest.raises(ValueError, match='nonfinite'):
        train_bt.design(pair, 'base', objective.weights('v1'))
