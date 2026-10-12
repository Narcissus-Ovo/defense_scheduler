"""Run reproducible checks on an isolated test database and retain UTF-8 logs.

Usage: .venv/Scripts/python.exe scripts/qa/run-baseline.py
       .venv/Scripts/python.exe scripts/qa/run-baseline.py --only probes,quality,documents
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', help='Comma-separated check names; omit for the full baseline')
    args = parser.parse_args()
    local_node = ROOT / '.runtime-deps' / 'node-v24.13.1-win-x64' / 'node.exe'
    node = str(local_node) if local_node.exists() else shutil.which('node')
    if not node:
        raise SystemExit('Node.js is required')
    node_version = subprocess.check_output([node, '--version'], text=True).strip()
    expected = (ROOT / '.nvmrc').read_text().strip().lstrip('v')
    if node_version.lstrip('v') != expected or sys.version_info[:2] != (3, 12):
        raise SystemExit(f'Use Node {expected} and Python 3.12; actual: {node_version}, {sys.version.split()[0]}')
    stamp = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S')
    out = ROOT / '.tmp' / 'qa-baseline' / stamp
    out.mkdir(parents=True)
    env = os.environ.copy()
    env.update(DJANGO_ENV='local', DJANGO_SECRET_KEY='local-isolated-verification-only',
        DJANGO_DB_PATH=str(out / 'verification.sqlite3'), PYTHONIOENCODING='utf-8',
        VITE_USE_MOCK='false', VITE_ENABLE_DEMO_TOOLS='false')
    checks = {
        'documents': [sys.executable, 'scripts/check-project-docs.py'],
        'lint': [node, 'node_modules/eslint/bin/eslint.js', '.', '--ext', '.ts,.vue'],
        'domain': [node, 'scripts/test-frontend-domain.cjs'],
        'types': [node, 'node_modules/vue-tsc/bin/vue-tsc.js', '-b'],
        'build': [node, 'node_modules/vite/bin/vite.js', 'build'],
        'django': [sys.executable, 'manage.py', 'check'],
        'migrations': [sys.executable, 'manage.py', 'makemigrations', '--check', '--dry-run'],
        'backend': [sys.executable, 'manage.py', 'test', 'api', 'defense_scheduler', '--noinput'],
        'probes': [sys.executable, 'scripts/qa/probe-baseline.py'],
        'quality': [node, 'scripts/qa/probe-quality.cjs'],
        'whitespace': ['git', 'diff', '--check'],
    }
    selected = args.only.split(',') if args.only else list(checks)
    if any(name not in checks for name in selected):
        raise SystemExit(f'Unknown checks. Choose from {", ".join(checks)}')
    business_db = ROOT / 'db.sqlite3'
    fingerprint = lambda: hashlib.sha256(business_db.read_bytes()).hexdigest() if business_db.exists() else None
    before = fingerprint()
    results = []
    for name in selected:
        start = time.monotonic()
        with (out / f'{name}.log').open('w', encoding='utf-8') as log:
            result = subprocess.run(checks[name], cwd=ROOT, env=env, stdout=log,
                stderr=subprocess.STDOUT, text=True, encoding='utf-8')
        results.append(dict(check=name, command=checks[name][1:], returncode=result.returncode,
            seconds=round(time.monotonic() - start, 3)))
        print(f'{name}: exit {result.returncode}', flush=True)
    report = dict(date=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        branch=subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        python=sys.version.split()[0], node=node_version, checks=results,
        business_database_unchanged=before == fingerprint(),
        note='Probe exit 0 means observations were collected; inspect meets_new_expectation, not a requirement pass.')
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Report: {out.relative_to(ROOT) / "report.json"}')
    raise SystemExit(int(any(item['returncode'] for item in results) or not report['business_database_unchanged']))


if __name__ == '__main__':
    main()
