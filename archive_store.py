"""Persistent local project summaries. Age affects filters, never retention."""
import fcntl
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
BLOCK = re.compile(r'^```project-cards\s*\n(.*?)^```[ \t]*$', re.M | re.S)

def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)

def valid(row):
    return (isinstance(row, dict) and isinstance(row.get('id'), str) and row['id'].isdigit()
            and isinstance(row.get('tasks'), list) and all(isinstance(t, str) for t in row['tasks'])
            and all(isinstance(row.get(k), str) and row[k] for k in
                    ('title','url','description','client','about','risk','question','kind','budget','payment'))
            and re.fullmatch(r'https://www\.upwork\.com/jobs/~[0-9]+(?:\?[^\s]*)?', row['url']))

def merge_original(card, candidate):
    """Prefer a complete client description, then the more recent source."""
    if not isinstance(candidate, dict):
        return
    quality = candidate.get('quality')
    body = candidate.get('text')
    if candidate.get('source') not in ('Upwork · get', 'Upwork · search'):
        return
    if quality not in ('full', 'excerpt') or not isinstance(body, str) or not body.strip():
        return
    try:
        captured = datetime.fromisoformat(candidate['retrievedAt'].replace('Z', '+00:00'))
        if captured.utcoffset() is None:
            return
    except (AttributeError, KeyError, TypeError, ValueError):
        return
    translation = candidate.get('translationEn')
    has_translation = isinstance(translation, str) and bool(translation.strip())
    language = candidate.get('language')
    previous = card.get('originalDescription')
    if previous and body == previous['text']:
        language = language or previous.get('language')
        if not has_translation and previous.get('translationEn'):
            translation = previous['translationEn']
            has_translation = True
    incoming = {'text': body, 'quality': quality, 'language': language, 'translationEn': translation}
    if previous:
        if has_english_brief(card) and not has_english_brief({'originalDescription': incoming}):
            return
        previous_time = datetime.fromisoformat(previous['retrievedAt'].replace('Z', '+00:00'))
        if (previous['quality'] == 'full', previous_time) >= (quality == 'full', captured):
            if body == previous['text']:
                if has_translation and not previous.get('translationEn'):
                    previous['translationEn'] = translation
                if language and not previous.get('language'):
                    previous['language'] = language
            return
    card['originalDescription'] = {
        'text': body, 'quality': quality, 'retrievedAt': captured.isoformat(),
        'source': candidate['source'],
    }
    if has_translation:
        card['originalDescription']['translationEn'] = translation
    if language:
        card['originalDescription']['language'] = language

def has_english_brief(card):
    original = card.get('originalDescription') or {}
    if not isinstance(original, dict) or original.get('quality') not in ('full', 'excerpt'):
        return False
    text = original.get('text')
    if not isinstance(text, str) or not text.strip():
        return False
    language = original.get('language')
    if not isinstance(language, str) or not language.strip():
        return False
    if language.strip().lower().split('-')[0] == 'en':
        return True
    translation = original.get('translationEn')
    return isinstance(translation, str) and bool(translation.strip())

def build_catalog(base, now=None):
    base = Path(base); now = now or datetime.now(timezone.utc)
    path = base / 'data' / 'projects.json'
    archive = json.loads(path.read_text()) if path.exists() else {'projects': []}
    cards = {r['id']: dict(r) for r in archive['projects'] if valid(r)}
    archived_ids = set(cards)
    incomplete = 0
    for report in sorted((base / 'reports').glob('live_*.md')):
        if report.is_symlink(): continue
        try: checked = datetime.strptime(report.name, 'live_%Y%m%dT%H%M%SZ.md').replace(tzinfo=timezone.utc)
        except ValueError: continue
        if checked > now: continue
        try: content = report.read_text()
        except FileNotFoundError: continue
        blocks = BLOCK.findall(content)
        if not blocks and 'upwork.com/jobs/' in content: incomplete += 1
        for block in blocks:
            try:
                rows = json.loads(block)
                if not isinstance(rows, list): raise ValueError
            except ValueError:
                incomplete += 1; continue
            for row in rows:
                if not isinstance(row, dict): incomplete += 1; continue
                uid = row.get('id'); previous = cards.get(uid, {})
                original = row.pop('originalDescription', None)
                if row.get('updateOnly'):
                    if previous:
                        merge_original(previous, original)
                    changes = {k: row[k] for k in ('status','activity','cost') if k in row}
                    if previous and changes and checked >= datetime.fromisoformat(previous.get('statusChecked',previous['checked']).replace('Z','+00:00')):
                        previous.update(changes)
                        previous['statusChecked'] = checked.isoformat()
                    continue
                if not valid(row): incomplete += 1; continue
                if previous and checked < datetime.fromisoformat(previous['checked'].replace('Z','+00:00')):
                    merge_original(previous, original)
                    continue
                card = {**previous, **row}
                merge_original(card, original)
                card['checked'] = checked.isoformat()
                card['firstSeen'] = previous.get('firstSeen', checked.isoformat())
                card['sourceReport'] = report.name
                if previous.get('statusChecked') and datetime.fromisoformat(previous['statusChecked'].replace('Z','+00:00')) > checked:
                    card.update({k: previous[k] for k in ('status','activity','cost') if k in previous})
                cards[uid] = card
    # Keep incomplete new entries in their source reports for the next sync.
    # Check after all updates so a later report can supply the missing original.
    pending = sorted(uid for uid in cards.keys() - archived_ids if not has_english_brief(cards[uid]))
    for uid in pending:
        del cards[uid]
    rows = list(cards.values())
    return {'projects':rows,'updated':max((r['checked'] for r in rows),default=None),
            'incomplete':incomplete + len(pending),'retention':'persistent','restored':archive.get('restored'),
            **({'pendingOriginalIds': pending} if pending else {})}

def sync_archive(base):
    base = Path(base); (base/'data').mkdir(exist_ok=True)
    with (base/'data/.archive.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = build_catalog(base)
        atomic_json(base/'data/projects.json',data)
        state=base/'seen_jobs.json'
        seen={r['job_id']:r for r in json.loads(state.read_text())} if state.exists() else {}
        for row in data['projects']:
            prior=seen.get(row['id'],{})
            seen[row['id']]={'job_id':row['id'],'first_shown_at':prior.get('first_shown_at',row['firstSeen']),
                             'status':row.get('status','consider'),'url':row['url']}
        atomic_json(state,list(seen.values()))
        return data
