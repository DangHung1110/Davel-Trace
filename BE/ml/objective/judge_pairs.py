"""Judge one blinded pass per fresh Claude CLI session using the existing login.

No API key, paid API, file tools, MCP server, project instructions or previous
conversation is supplied. Raw responses are retained for provenance and review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time


def subscription_login(cli):
    status = subprocess.run([cli, 'auth', 'status'], capture_output=True,
                            text=True, encoding='utf-8', timeout=30)
    auth = json.loads(status.stdout) if status.returncode == 0 else {}
    if not auth.get('loggedIn') or auth.get('authMethod') != 'claude.ai':
        raise RuntimeError('Claude subscription login is required; paid API keys are not allowed')
    return {'auth_method': 'claude.ai'}


def parse_response(response, expected):
    text = response.get('result', '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text)
    labels = json.loads(text)
    if not isinstance(labels, list):
        raise ValueError('Judge must return an array')
    seen = set()
    for row in labels:
        key = (row['pair'], row['pass'])
        if key not in expected or key in seen or row['winner'] not in ('left', 'right', 'tie'):
            raise ValueError('Invalid, duplicate or unexpected label')
        seen.add(key)
    if seen != expected:
        raise ValueError('Judge response has missing labels')
    return labels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sheet', help='Audit sheet path; .pass1.md and .pass2.md must exist')
    parser.add_argument('labels')
    args = parser.parse_args()
    cli = shutil.which('claude')
    if cli is None:
        raise RuntimeError('Claude CLI is unavailable; do not substitute fabricated labels')
    auth = subscription_login(cli)
    out = Path(args.labels).resolve()
    if out.exists():
        raise FileExistsError(out)
    all_labels, sessions = [], []
    for attempt in (1, 2):
        sheet = Path(args.sheet).with_suffix(f'.pass{attempt}.md').resolve()
        content = sheet.read_text(encoding='utf-8')
        expected = {(int(k), int(n)) for k, n in re.findall(r'^## P(\d+)-(\d+)$', content, re.M)}
        if not expected or any(n != attempt for _, n in expected):
            raise ValueError('Invalid independent pass sheet')
        raw = Path(str(out) + f'.pass{attempt}.response.json')
        if raw.exists():
            raise FileExistsError(raw)
        command = [cli, '-p', '--output-format', 'json', '--tools', '',
                   '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                   '--disable-slash-commands', '--no-session-persistence',
                   '--setting-sources', '', '--system-prompt',
                   'You are an independent travel itinerary preference judge. '
                   'Use only the supplied sheet and rubric. Return the requested JSON array.']
        started = time.monotonic()
        run = subprocess.run(command, input=content, cwd=sheet.parent, capture_output=True,
                             text=True, encoding='utf-8', timeout=600)
        raw.write_text(run.stdout, encoding='utf-8')
        if run.returncode:
            Path(str(raw) + '.stderr.txt').write_text(run.stderr, encoding='utf-8')
            raise RuntimeError(f'Claude pass {attempt} failed; inspect {raw}')
        response = json.loads(run.stdout)
        if response.get('is_error'):
            raise RuntimeError(f'Claude pass {attempt} returned an error; inspect {raw}')
        labels = parse_response(response, expected)
        all_labels.extend(labels)
        sessions.append({'pass': attempt, 'session_id': response.get('session_id'),
                         'model_usage': response.get('modelUsage'),
                         'elapsed_s': round(time.monotonic() - started, 2), 'raw_response': str(raw)})
        print(f'Claude pass {attempt}: {len(labels)} labels', flush=True)
    out.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in all_labels), encoding='utf-8')
    Path(str(out) + '.provenance.json').write_text(json.dumps({
        'judge': 'Claude CLI', **auth, 'independent_sessions': True, 'sessions': sessions,
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
