import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import agent

class PipelineTests(unittest.TestCase):
    def test_discovers_auth_page_without_saved_app_data(self):
        docs={
          'https://example.com/docs': {'text':'Developer documentation','links':['https://example.com/docs/authentication','https://unrelated.test/api']},
          'https://example.com/llms.txt':{'text':'Index','links':[]},
          'https://example.com/docs/authentication':{'text':'Use an API key. REST API. Free trial available.','links':[]}}
        def fake(url,cache,refresh): return {'url':url,'status':'read',**docs[url]}
        with tempfile.TemporaryDirectory() as tmp, patch('agent.fetch',side_effect=fake):
            result=agent.run('New app','https://example.com/docs',Path(tmp)/'run',4)
            self.assertEqual(result['pages_read'],3)
            self.assertIn('K',result['fields']['auth'])
            self.assertEqual(result['prototype'],'Needs review')
            self.assertTrue(all(e['url'].startswith('https://example.com/') for e in result['evidence']))
            self.assertTrue((Path(tmp)/'run/report.html').exists())
    def test_failed_fetches_never_become_buildable(self):
        with tempfile.TemporaryDirectory() as tmp, patch('agent.fetch',side_effect=lambda u,c,r:{'url':u,'status':'unavailable','text':'','links':[]}):
            result=agent.run('Missing','https://example.com',Path(tmp),2)
            self.assertTrue(result['prototype'].startswith('Blocked'))
            self.assertEqual(result['evidence'],[])
    def test_page_budget_is_enforced(self):
        with tempfile.TemporaryDirectory() as tmp, patch('agent.fetch',side_effect=lambda u,c,r:{'url':u,'status':'read','text':'REST','links':['https://example.com/api/'+str(i) for i in range(30)]}):
            result=agent.run('Budget','https://example.com',Path(tmp),3)
            self.assertEqual(result['pages_attempted'],3)
    def test_private_and_non_https_urls_rejected(self):
        for url in ['http://example.com','https://localhost','https://127.0.0.1','https://user:pass@example.com']:
            with self.assertRaises(ValueError):agent.public_url(url)
    def test_sample_not_overlapping_and_rows_corrected(self):
        root=Path(__file__).parent
        first=json.loads((root/'data/audit.json').read_text())
        second=json.loads((root/'data/holdout-audit.json').read_text())['checks']
        self.assertFalse({c['id'] for c in first}&{c['id'] for c in second})
        from research import load_review
        rows={r['id']:r for r in load_review()}
        self.assertEqual(len(second),10)
        for c in second:self.assertEqual(rows[c['id']]['auth'],c['expected'])

if __name__=='__main__':unittest.main()
