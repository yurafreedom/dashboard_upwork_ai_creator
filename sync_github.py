"""Pull before a search; validate, commit and push afterwards. Never force-push."""
import argparse
import copy
import fcntl
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from archive_store import atomic_json, merge_original
from build_site import check_secrets, validate

BASE = Path(__file__).resolve().parent
REPO = 'yurafreedom/dashboard_upwork_ai_creator'
URL = f'https://github.com/{REPO}.git'
PAGES = 'https://yurafreedom.github.io/dashboard_upwork_ai_creator/'
TRACKED = ('AGENTS.md', 'README.md', '.gitignore', '.github', 'catalog.py', 'archive_store.py',
           'cleanup.py', 'build_site.py', 'sync_github.py', 'tests', 'site', 'reports',
           'applications', 'data/projects.json', 'data/practice.json', 'data/availability.json',
           'data/application_plans.json', 'seen_jobs.json', 'search_brief.md', 'profile_facts.md',
           'portfolio_map.md', 'profile_draft_en.md', 'operations.md', 'automation_prompt.md',
           'tool_catalog.md', 'user_request.md', 'connection_status.example.json',
           'Открыть каталог.command')
MERGEABLE = {'data/projects.json', 'data/practice.json', 'data/availability.json', 'seen_jobs.json'}


def git(*args, cwd=BASE, check=True):
    result = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'Git command failed')
    return result


def merge_data(base, ours, theirs, path=''):
    """Three-way merge. Keep additions by ID; reject ambiguous concurrent edits."""
    if ours == theirs or theirs == base:
        return copy.deepcopy(ours)
    if ours == base:
        return copy.deepcopy(theirs)
    if isinstance(ours, dict) and isinstance(theirs, dict):
        base = base if isinstance(base, dict) else {}
        # Both processes refreshed the same job. The newer verified row wins;
        # original description completeness and first discovery are independent.
        if ours.get('id') == theirs.get('id') and 'checked' in ours and 'checked' in theirs:
            if ours['checked'] == theirs['checked'] and ours != theirs:
                # Equal check times are not evidence that one manual edit is newer.
                ignored = {'originalDescription', 'firstSeen'}
                left = {k:v for k,v in ours.items() if k not in ignored}
                right = {k:v for k,v in theirs.items() if k not in ignored}
                if left != right:
                    return merge_fields(base, ours, theirs, path)
            newer, older = sorted((ours, theirs), key=lambda x: x['checked'], reverse=True)
            merged = {**copy.deepcopy(older), **copy.deepcopy(newer)}
            dates = [r['firstSeen'] for r in (ours, theirs) if r.get('firstSeen')]
            if dates:
                merged['firstSeen'] = min(dates)
            merge_original(merged, older.get('originalDescription'))
            return merged
        if 'at' in ours and 'at' in theirs and ours['at'] != theirs['at']:
            return copy.deepcopy(max((ours, theirs), key=lambda x: x['at']))
        return merge_fields(base, ours, theirs, path)
    if isinstance(ours, list) and isinstance(theirs, list):
        rows = ours + theirs
        key = next((k for k in ('id', 'job_id') if rows and all(isinstance(r, dict) and k in r for r in rows)), None)
        if key:
            old = {r[key]:r for r in base or []}
            left, right = {r[key]:r for r in ours}, {r[key]:r for r in theirs}
            # Permanent archive: a missing row never deletes the other copy.
            return [merge_data(old.get(uid), left[uid], right[uid], path+'/'+uid)
                    if uid in left and uid in right else copy.deepcopy(left.get(uid, right.get(uid)))
                    for uid in sorted(left.keys() | right.keys())]
    if path.endswith(('/firstSeen', '/first_shown_at')):
        return min(ours, theirs)
    if path.endswith(('/updated', '/started')) and isinstance(ours, str) and isinstance(theirs, str):
        return max(ours, theirs)
    if '/seen/' in path and path.endswith('/status'):
        # cleanup.py derives the final status from the merged project record.
        return ours
    raise ValueError(f'Concurrent edits need review: {path or "root"}')


def merge_fields(base, ours, theirs, path):
    result = {}
    for key in sorted(ours.keys() | theirs.keys()):
        if key in ours and key in theirs:
            result[key] = merge_data(base.get(key), ours[key], theirs[key], path+'/'+key)
        else:
            result[key] = copy.deepcopy(ours.get(key, theirs.get(key)))
    return result


def merge_remote(cwd=BASE):
    result = git('merge', '--no-edit', 'origin/main', cwd=cwd, check=False)
    if result.returncode == 0:
        return
    conflicts = git('diff', '--name-only', '--diff-filter=U', cwd=cwd).stdout.splitlines()
    try:
        if not conflicts or set(conflicts) - MERGEABLE:
            raise ValueError('Conflicting source files: ' + ', '.join(conflicts))
        merged = {}
        for name in conflicts:
            versions = []
            for stage in (1, 2, 3):
                content = git('show', f':{stage}:{name}', cwd=cwd, check=False)
                versions.append(json.loads(content.stdout) if content.returncode == 0 else None)
            merged[name] = merge_data(*versions, path='/seen' if name == 'seen_jobs.json' else name)
        for name, data in merged.items():
            atomic_json(Path(cwd) / name, data)
        git('add', '--', *conflicts, cwd=cwd)
        git('commit', '--no-edit', cwd=cwd)
    except Exception:
        git('merge', '--abort', cwd=cwd, check=False)
        raise


def bootstrap():
    state = BASE / 'connection_status.json'
    if not state.exists():
        atomic_json(state, json.loads((BASE / 'connection_status.example.json').read_text()))


def check_repo():
    if Path(git('rev-parse', '--show-toplevel').stdout.strip()).resolve() != BASE:
        raise RuntimeError('Run this script from the dashboard repository, not a parent repository')
    remote = git('remote', 'get-url', 'origin').stdout.strip()
    if remote not in (URL, URL.removesuffix('.git'), f'git@github.com:{REPO}.git'):
        raise RuntimeError('Unexpected origin; expected ' + URL)
    if git('branch', '--show-current').stdout.strip() != 'main':
        raise RuntimeError('Publishing requires the main branch')
    if git('diff', '--name-only', '--diff-filter=U').stdout.strip():
        raise RuntimeError('Resolve existing Git conflicts before publishing')
    bootstrap()


def stage_and_commit(message, cwd=BASE):
    paths = [name for name in TRACKED if (Path(cwd) / name).exists()]
    for name in paths:
        path = Path(cwd) / name
        for file in path.rglob('*') if path.is_dir() else [path]:
            if file.is_file() and '__pycache__' not in file.parts:
                check_secrets(file)
    git('add', '--all', '--', *paths, cwd=cwd)
    staged = [name for name in git('diff', '--cached', '--name-only', '-z', cwd=cwd).stdout.split('\0') if name]
    if staged:
        for name in staged:
            if not any(name == allowed or name.startswith(allowed+'/') for allowed in TRACKED):
                raise RuntimeError('Unexpected staged file; review before publishing: ' + name)
        git('commit', '-m', message, cwd=cwd)


def wait_for_pages(sha, attempts=36):
    print('Push complete. Waiting for GitHub Pages…', flush=True)
    for attempt in range(attempts):
        try:
            request = Request(PAGES+'version.json?commit='+sha, headers={'Cache-Control':'no-cache'})
            with urlopen(request, timeout=12) as response:
                version = json.load(response)
            if version.get('commit') == sha:
                return version
        except (HTTPError, URLError, TimeoutError, ValueError):
            pass
        if attempt + 1 < attempts:
            time.sleep(10)
    raise RuntimeError('Git push succeeded, but this commit is not yet verified on Pages. Check the Actions run; do not claim the site is updated.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('pull', 'publish'))
    parser.add_argument('--message', default='Update Bureau project archive')
    parser.add_argument('--wait', action='store_true', help='Verify that Pages serves the pushed commit')
    args = parser.parse_args()
    check_repo()
    lock_path = Path(git('rev-parse', '--git-path', 'bureau-publish.lock').stdout.strip())
    if not lock_path.is_absolute():
        lock_path = BASE / lock_path
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'pull':
            if git('status', '--porcelain', '--untracked-files=no').stdout.strip():
                raise RuntimeError('Local changes exist. Publish or review them first; nothing was reset or stashed.')
            git('pull', '--ff-only', 'origin', 'main')
            print('Latest main loaded. Verify Upwork access in this environment before searching.')
            return
        subprocess.run([sys.executable, 'cleanup.py', '--apply'], cwd=BASE, check=True)
        validate(BASE)
        stage_and_commit(args.message)
        for attempt in range(3):
            exists = git('ls-remote', '--heads', 'origin', 'main').stdout.strip()
            if exists:
                git('fetch', 'origin', 'main')
                merge_remote()
                subprocess.run([sys.executable, 'cleanup.py', '--apply'], cwd=BASE, check=True)
                validate(BASE)
                stage_and_commit('Reconcile project archive after synchronization')
            pushed = git('push', '--set-upstream', 'origin', 'main', check=False)
            if pushed.returncode == 0:
                break
            if attempt == 2 or not any(word in pushed.stderr for word in ('fetch first', 'non-fast-forward')):
                raise RuntimeError(pushed.stderr.strip())
        sha = git('rev-parse', 'HEAD').stdout.strip()
        state = {'commit':sha, 'pushedAt':datetime.now(timezone.utc).isoformat(), 'url':PAGES, 'pagesVerified':False}
        atomic_json(BASE / '.publish-state.json', state)
        if args.wait:
            version = wait_for_pages(sha)
            state.update(pagesVerified=True, verifiedAt=datetime.now(timezone.utc).isoformat(), projects=version['projects'])
            atomic_json(BASE / '.publish-state.json', state)
        print(json.dumps(state, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, BlockingIOError, subprocess.CalledProcessError) as error:
        print('Publication stopped: ' + str(error), file=sys.stderr)
        sys.exit(1)
