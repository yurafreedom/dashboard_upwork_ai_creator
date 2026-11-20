import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from archive_store import build_catalog, merge_original
from build_site import BASE, build, validate
from sync_github import merge_data, merge_remote, stage_and_commit


class PublicationTests(unittest.TestCase):
    def test_complete_archive_and_subpath_links(self):
        source, practice = validate()
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'dashboard_upwork_ai_creator'
            manifest = build(output=out)
            published = json.loads((out / 'api/projects.json').read_text())
            self.assertEqual({p['id'] for p in source['projects']}, {p['id'] for p in published['projects']})
            self.assertEqual(len(practice['projects']), manifest['practice'])
            self.assertEqual(sum(bool(p.get('applicationPlan')) for p in source['projects']), manifest['savedProposals'])
            for name in ('index.html', 'practice.html'):
                text = (out / name).read_text()
                self.assertNotRegex(text, r'(?:href|src)="/(?!/)')
            for name in ('board.js', 'practice.js'):
                self.assertNotRegex((out / name).read_text(), r'''["']/api/''')
            self.assertFalse((out / 'connection_status.json').exists())
            self.assertEqual(len(list((BASE / 'reports').glob('live_*.md'))), len(list((out / 'reports').glob('live_*.md'))))

    def test_future_card_needs_english_original(self):
        sample = copy.deepcopy(validate()[0]['projects'][0])
        sample.pop('originalDescription')
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / 'reports').mkdir()
            report = base / 'reports/live_20200101T000000Z.md'
            def write():
                report.write_text('```project-cards\n' + json.dumps([sample]) + '\n```\n')
            write()
            self.assertIn(sample['id'], build_catalog(base)['pendingOriginalIds'])
            sample['originalDescription'] = {'text':'Brief\n\n- Requirement', 'language':'en', 'quality':'full', 'source':'Upwork · get', 'retrievedAt':'2020-01-01T00:00:00Z'}
            write()
            self.assertEqual(build_catalog(base)['projects'][0]['originalDescription']['text'], 'Brief\n\n- Requirement')
            merge_original(sample, {'text':'Brief...', 'language':'en', 'quality':'excerpt', 'source':'Upwork · search', 'retrievedAt':'2020-01-02T00:00:00Z'})
            self.assertEqual(sample['originalDescription']['quality'], 'full')

    def test_concurrent_new_projects_and_original_dates(self):
        original = {'id':'1', 'checked':'2026-11-01T00:00:00Z', 'firstSeen':'2026-10-01T00:00:00Z', 'title':'Original'}
        base = {'projects':[original], 'updated':'2026-11-01T00:00:00Z'}
        ours = {'projects':[original, {'id':'2','title':'Local'}], 'updated':'2026-11-02T00:00:00Z'}
        theirs = {'projects':[original, {'id':'3','title':'Remote'}], 'updated':'2026-11-03T00:00:00Z'}
        result = merge_data(base, ours, theirs)
        self.assertEqual([p['id'] for p in result['projects']], ['1','2','3'])
        self.assertEqual(result['projects'][0]['firstSeen'], original['firstSeen'])

    def test_ambiguous_concurrent_edits_stop(self):
        with self.assertRaises(ValueError):
            merge_data({'text':'initial'}, {'text':'local correction'}, {'text':'remote correction'})

    def test_publish_accepts_cyrillic_filename(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            def run(*args):
                return subprocess.run(['git', *args], cwd=path, check=True, capture_output=True, text=True).stdout
            run('init', '-b', 'main')
            run('config', 'user.name', 'Test')
            run('config', 'user.email', 'test@example.invalid')
            (path / 'Открыть каталог.command').write_text('#!/bin/sh\n')
            stage_and_commit('Publish launcher', cwd=path)
            self.assertEqual(run('ls-files', '-z'), 'Открыть каталог.command\0')

    def test_actual_git_merge_retains_both_chats(self):
        def run(path, *args):
            return subprocess.run(['git', *args], cwd=path, check=True, capture_output=True, text=True).stdout
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            run(path, 'init', '-b', 'main')
            run(path, 'config', 'user.name', 'Test')
            run(path, 'config', 'user.email', 'test@example.invalid')
            (path / 'data').mkdir()
            archive = path / 'data/projects.json'
            archive.write_text(json.dumps({'projects':[{'id':'1','title':'base'}]}))
            run(path, 'add', '.')
            run(path, 'commit', '-m', 'base')
            base = run(path, 'rev-parse', 'HEAD').strip()
            archive.write_text(json.dumps({'projects':[{'id':'1','title':'base'},{'id':'2','title':'local'}]}))
            run(path, 'commit', '-am', 'local addition')
            run(path, 'checkout', '-b', 'other', base)
            archive.write_text(json.dumps({'projects':[{'id':'1','title':'base'},{'id':'3','title':'remote'}]}))
            run(path, 'commit', '-am', 'remote addition')
            run(path, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
            run(path, 'checkout', 'main')
            merge_remote(path)
            self.assertEqual({r['id'] for r in json.loads(archive.read_text())['projects']}, {'1','2','3'})
            self.assertEqual(run(path, 'status', '--porcelain').strip(), '')


if __name__ == '__main__':
    unittest.main()
