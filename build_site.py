"""Build the complete Bureau dashboard for GitHub Pages (Python standard library)."""
import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from archive_store import has_english_brief, valid
from catalog import catalog

BASE = Path(__file__).resolve().parent
ASSETS = ('index.html', 'practice.html', 'board.js', 'practice.js', 'original-brief.js',
          'style.css', 'practice.css', 'portrait.jpg', 'fashion.jpg', 'mark.svg')
AI_ROLES = ('generation', 'partial', 'none')
SECRET = re.compile(r'(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{24,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)')


def check_secrets(path):
    if path.is_symlink():
        raise ValueError(f'Symlinks are not published: {path.name}')
    if path.suffix.lower() in ('.json', '.md', '.txt', '.html', '.js', '.yml', '.yaml', '.py'):
        if SECRET.search(path.read_text()):
            raise ValueError(f'Possible credential in {path.name}; publication stopped')


def validate(base=BASE):
    data = catalog(base / 'reports')
    if data.get('incomplete'):
        raise ValueError('Archive contains incomplete reports or descriptions; run cleanup.py first')
    rows = data['projects']
    if not rows or len({c['id'] for c in rows}) != len(rows):
        raise ValueError('Empty catalog or duplicate project IDs')
    if not all(valid(c) and has_english_brief(c) for c in rows):
        raise ValueError('Every project needs its original client description and English version')
    if any(c.get('aiRole') not in (None, *AI_ROLES) for c in rows):
        raise ValueError('aiRole must be generation, partial or none')
    practice = json.loads((base / 'data/practice.json').read_text())
    ids = {c['id'] for c in rows}
    practices = practice['projects']
    if len({p['id'] for p in practices}) != len(practices):
        raise ValueError('Duplicate practice IDs')
    missing = ids - {p['id'] for p in practices}
    if missing:
        raise ValueError('Missing practice briefs: ' + ', '.join(sorted(missing)))
    plans = json.loads((base / 'data/application_plans.json').read_text())
    if set(plans.get('projects', {})) - ids:
        raise ValueError('Saved proposals reference missing project cards')
    return data, practice


def build(base=BASE, output=None):
    base = Path(base).resolve()
    output = Path(output or base / 'dist').resolve()
    # Never use a destructive recursive clean on an arbitrary user directory.
    if output == base or base.is_relative_to(output):
        raise ValueError('Build output cannot contain the source directory')
    if output.is_symlink():
        raise ValueError('Build output cannot be a symlink')
    data, practice = validate(base)
    files = [base / 'site' / name for name in ASSETS]
    reports = sorted((base / 'reports').glob('live_*.md'), reverse=True)
    attachments = sorted(p for p in (base / 'applications').rglob('*') if p.is_file())
    for path in [*files, *reports, *attachments, *(base / 'data').glob('*.json')]:
        check_secrets(path)
    output.mkdir(parents=True, exist_ok=True)
    for path in files:
        shutil.copy2(path, output / path.name)
    (output / 'api').mkdir(exist_ok=True)
    (output / 'reports').mkdir(exist_ok=True)
    report_rows = []
    for path in reports:
        timestamp = datetime.strptime(path.name, 'live_%Y%m%dT%H%M%SZ.md').replace(tzinfo=timezone.utc)
        report_rows.append({'name': path.name, 'label': timestamp.astimezone(ZoneInfo('Europe/Kyiv')).strftime('%d.%m.%Y · %H:%M Киев — отчёт и черновики')})
        shutil.copy2(path, output / 'reports' / path.name)
    data['publishedSnapshotAt'] = datetime.now(timezone.utc).isoformat()
    for name, payload in [('projects', data), ('practice', practice), ('reports', {'reports': report_rows})]:
        (output / 'api' / f'{name}.json').write_text(json.dumps(payload, ensure_ascii=False))
    links = []
    from urllib.parse import quote
    for path in attachments:
        relative = path.relative_to(base)
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        links.append(f'<li><a href="./{quote(relative.as_posix())}">{html.escape(relative.as_posix())}</a></li>')
    (output / 'resources.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Бюро · Материалы откликов</title><link rel="stylesheet" href="./style.css"><main class="wrap"><p><a href="./">Бюро проектов</a></p><h1>Материалы откликов</h1><p>Сохранённые письма, ответы и вложения. Даты и условия относятся к моменту подготовки.</p><ul>' + ''.join(links) + '</ul></main></html>')
    for name in ('index.html', 'practice.html'):
        path = output / name
        text = path.read_text().replace('</nav>', '<a href="./resources.html">Материалы откликов</a></nav>', 1)
        path.write_text(text)
    (output / '.nojekyll').write_text('')
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=base, capture_output=True, text=True)
    manifest = {'commit': commit.stdout.strip() if commit.returncode == 0 else None,
                'builtAt': data['publishedSnapshotAt'], 'projects': len(data['projects']),
                'practice': len(practice['projects']), 'reports': len(reports),
                'savedProposals': sum(bool(p.get('applicationPlan')) for p in data['projects']),
                'originalDescriptions': {'full': sum(p['originalDescription']['quality'] == 'full' for p in data['projects']),
                                         'excerpt': sum(p['originalDescription']['quality'] == 'excerpt' for p in data['projects'])},
                'aiRoles': {role: sum(p.get('aiRole') == role for p in data['projects']) for role in AI_ROLES},
                'catalogSha256': hashlib.sha256((output / 'api/projects.json').read_bytes()).hexdigest()}
    (output / 'version.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    print(json.dumps(build(output=args.output), ensure_ascii=False))
