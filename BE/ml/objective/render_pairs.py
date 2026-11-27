"""Render two independent blinded judging passes and a private audit sheet."""
import hashlib
import json
from pathlib import Path
import random
import sys

RUBRIC = '''Judge the two itineraries against the trip, not against a hidden scoring formula.
Prioritize explicit requests and feasibility, appropriate meals/rest and pace,
meaningful variety without duplicate experiences, then unnecessary riding.
More stops is not automatically better. Fees are planner estimates, not verified quotes.
Do not invent facts about places. Choose tie when the difference is unclear.
Return ONLY a JSON array of {"pair": k, "pass": n, "winner": "left"|"right"|"tie", "reason": "short evidence"}.
Each Pk-n is an independent decision. You have only this pass; never infer a previous vote.
'''


def pair_hash(pair):
    return hashlib.sha256(json.dumps(pair, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def block(k, attempt, pair, left):
    lines = [f'## P{k}-{attempt}', '', 'Trip: ' + json.dumps(pair['trip'], ensure_ascii=False), '']
    for side, which in (('Left', left), ('Right', 'B' if left == 'A' else 'A')):
        plan = pair[which]
        lines += [f'### {side}', '']
        for s in plan['stops']:
            lines.append(f"{s['start']}–{s['end']} {s['name']} [{s['poi_id']}] ({s['category']}, zone {s['zone']}, {s['ride_min_from_prev']} phút chạy, fee {s['fee']})")
        lines += ['Rest: ' + json.dumps(plan.get('rest'), ensure_ascii=False),
                  'Totals: ' + json.dumps(plan['totals']), '']
    return '\n'.join(lines)


def render(pairs, out, seed=42):
    targets = [Path(out), Path(str(out) + '.key.json'),
               Path(out).with_suffix('.pass1.md'), Path(out).with_suffix('.pass2.md')]
    if any(p.exists() for p in targets):
        raise FileExistsError('Use a fresh sheet name; existing sheets/keys must not be overwritten')
    rng = random.Random(seed)
    key, passes = {}, {1: [], 2: []}
    for k, pair in enumerate(pairs, 1):
        first = rng.choice(('A', 'B'))
        for attempt, left in ((1, first), (2, 'B' if first == 'A' else 'A')):
            key[f'P{k}-{attempt}'] = {'id': pair['id'], 'pair_sha256': pair_hash(pair),
                                     'left': 'base' if left == 'A' else 'perturbed'}
            passes[attempt].append(block(k, attempt, pair, left))
    combined = []
    for attempt, blocks in passes.items():
        rng.shuffle(blocks)
        content = RUBRIC + '\n\n' + '\n'.join(blocks)
        Path(out).with_suffix(f'.pass{attempt}.md').write_text(content, encoding='utf-8')
        combined.append(content)
    Path(out).write_text('# AUDIT ONLY — do not send both passes to one judge session\n\n'
                         + '\n'.join(combined), encoding='utf-8')
    Path(str(out) + '.key.json').write_text(json.dumps(key, indent=2), encoding='utf-8')


if __name__ == '__main__':
    render([json.loads(s) for s in Path(sys.argv[1]).read_text(encoding='utf-8').splitlines() if s.strip()],
           sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 42)
