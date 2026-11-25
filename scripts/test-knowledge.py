#!/usr/bin/env python3
"""Test the knowledge gate against isolated temporary Git histories."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

GATE = Path(__file__).with_name('check-knowledge.py')
RECORD = dict(schema=1, id='20261125-test-record', disposition='candidate',
              scope='test', summary='test correction', evidence=['test fixture'],
              tests=['test fixture'], rule_change='NONE: fixture', supersedes=[],
              approval='PENDING: fixture')

class KnowledgeGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        (self.root / 'scripts').mkdir()
        shutil.copyfile(GATE, self.root / 'scripts/check-knowledge.py')
        self.write('README.md', 'base')
        self.commit()
        self.base = self.git('rev-parse', 'HEAD').strip()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, text=True)

    def write(self, path, data):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data, encoding='utf-8')

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture')

    def record(self, obj=None):
        self.write('knowledge/records/20261125-test-record.json', json.dumps(RECORD if obj is None else obj))

    def check(self, expected, message):
        self.commit()
        p = subprocess.run([sys.executable, str(self.root / 'scripts/check-knowledge.py'), '--base', self.base], cwd=self.root, text=True, capture_output=True)
        self.assertEqual(p.returncode == 0, expected, p.stdout + p.stderr)
        self.assertIn(message, p.stdout + p.stderr)

    def test_code_requires_record(self):
        self.write('src/code.py', 'x=1')
        self.check(False, 'needs a new')

    def test_valid_record(self):
        self.write('src/code.py', 'x=1')
        self.record()
        self.check(True, 'PASS')

    def test_invalid_schema(self):
        self.record(dict(RECORD, schema=2))
        self.check(False, 'invalid schema')

    def test_empty_evidence(self):
        self.record(dict(RECORD, evidence=[]))
        self.check(False, 'invalid evidence')

    def test_prior_record_immutable(self):
        self.record()
        self.commit()
        self.base = self.git('rev-parse', 'HEAD').strip()
        self.record(dict(RECORD, summary='rewritten'))
        self.check(False, 'Do not overwrite')

    def test_prior_record_not_deleted(self):
        self.record()
        self.commit()
        self.base = self.git('rev-parse', 'HEAD').strip()
        (self.root / 'knowledge/records/20261125-test-record.json').unlink()
        self.check(False, 'Do not overwrite')

    def test_general_documentation_exempt(self):
        self.write('README.md', 'documentation update')
        self.check(True, 'PASS')

    def test_agent_instructions_not_exempt(self):
        self.write('AGENTS.md', 'changed rule')
        self.check(False, 'needs a new')

if __name__ == '__main__':
    unittest.main(verbosity=2)
