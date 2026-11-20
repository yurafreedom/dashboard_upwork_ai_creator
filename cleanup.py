"""Preserve project summaries and deduplication history; never expire by age."""
import argparse
import json
from pathlib import Path
from archive_store import build_catalog, has_english_brief, sync_archive
if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();base=Path(__file__).resolve().parent
    data=sync_archive(base) if args.apply else build_catalog(base)
    originals = {'full': 0, 'excerpt': 0, 'missing': 0}
    missing = list(data.get('pendingOriginalIds', []))
    originals['missing'] = len(missing)
    for card in data['projects']:
        original = card.get('originalDescription') or {}
        quality = original.get('quality') if has_english_brief(card) else None
        if quality not in ('full', 'excerpt'):
            quality = 'missing'
            missing.append(card['id'])
        originals[quality] += 1
    print(json.dumps({'apply':args.apply,'projects':len(data['projects']),'deleted':0,'retention':'persistent','incomplete':data['incomplete'],'originalDescriptions':originals,'missingOriginalIds':missing}))
    if missing:
        raise SystemExit(1)
