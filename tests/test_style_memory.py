import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('style',ROOT/'scripts/style_memory.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def setUp(self):
  self.refs=json.loads((ROOT/'examples/references.json').read_text());self.event=json.loads((ROOT/'examples/approved-feedback.json').read_text())
 def test_measured_summary(self):
  r=m.profile(self.refs);self.assertEqual(r['metrics']['shot_median_sec']['median'],5);self.assertEqual(r['reference_count'],3)
 def test_scope_isolation_and_idempotence(self):
  s=m.learn({},self.event);self.assertEqual(s,m.learn(s,self.event))
  self.assertEqual(m.resolve(s,{'project':'other','format':'talking-head-vertical'})['values'],{})
  self.assertEqual(m.resolve(s,self.event['scope'])['values']['caption_max_words'],5)
 def test_reject_unreviewed_or_mixed_references(self):
  self.refs[0]['reviewed']=False
  with self.assertRaises(ValueError):m.profile(self.refs)
  self.refs[0]['reviewed']=True;self.refs[0]['format']='podcast'
  with self.assertRaises(ValueError):m.profile(self.refs)
 def test_duplicate_sources_rejected(self):
  with self.assertRaises(ValueError):m.profile([self.refs[0]]*3)
 def test_conflicting_ids_and_unapproved_feedback_rejected(self):
  s=m.learn({},self.event);self.event['values']['caption_y']=.9
  with self.assertRaises(ValueError):m.learn(s,self.event)
  self.event['approved']=False
  with self.assertRaises(ValueError):m.learn({},self.event)
 def test_invalid_numbers_and_read_path(self):
  self.event['values']['caption_y']=float('nan')
  with self.assertRaises(ValueError):m.resolve({'events':[self.event]},self.event['scope'])
 def test_newer_correction_overrides_in_scope(self):
  s=m.learn({},self.event);self.event['id']='demo-review-002';self.event['values']={'caption_y':.8}
  r=m.resolve(m.learn(s,self.event),self.event['scope']);self.assertEqual(r['values'],{'caption_y':.8,'caption_max_words':5})
if __name__=='__main__':unittest.main()
