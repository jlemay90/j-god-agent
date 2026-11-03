import unittest
from j_policy import validate
from j_ranker import scores
from pathlib import Path

class RetrievalTests(unittest.TestCase):
    def test_relevance(self):
        records=[dict(id='a',kind='project',key='cabin',value='Insulate exposed water pipes'),dict(id='b',kind='project',key='phone',value='Compare folding phones')]
        values=scores(records,'cabin water pipes')
        self.assertGreater(values['a'],values['b'])
    def test_preferences_survive_unrelated_queries(self):
        r=dict(id='a',kind='preference',key='answer length',value='Concise answers')
        self.assertGreater(scores([r],'anything else')['a'],0)
    def test_no_credential_access(self):
        for source in ['import os\ndef score(memory,query):\n return os.environ', 'def score(memory,query):\n return open("/etc/passwd").read()', 'def score(memory,query):\n return memory.__class__', 'def score(memory,query):\n return eval(query)', 'def score(memory,query):\n return score(memory,query)']:
            with self.assertRaises(ValueError): validate(source)
    def test_infinite_work_is_bounded(self):
        with self.assertRaises(Exception): scores([dict(id='x')],'x',source='def score(memory,query):\n return sum(range(1000000000000))')
    def test_invalid_output_rejected(self):
        with self.assertRaises(Exception): scores([dict(id='x')],'x',source='def score(memory,query):\n return "bad"')

if __name__=='__main__': unittest.main()
