import json,unittest
from steering.official_mask import FIELDS,SCHEMA,load_official,validate_numeric,classify_response

class MaskParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.official=load_official()
    def response(self,text,finish='stop'):
        return {'choices':[{'finish_reason':finish,'message':{'content':text}}]}
    def test_binary_unknown_is_valid(self):
        status,value,_=classify_response(self.response('Explanation.\nAnswer: C'),False,self.official)
        self.assertEqual((status,value),('ok','C'))
        self.assertEqual(classify_response(self.response('invalid'),False,self.official)[0],'malformed')
        self.assertEqual(classify_response(self.response('Answer: A','length'),False,self.official)[0],'truncated')
    def test_numeric_schema_unknown_and_point(self):
        data={k:None for k in FIELDS}
        self.assertEqual(validate_numeric(json.dumps(data)),(None,None,None,None))
        data.update(lower_bound=42,upper_bound=42)
        self.assertEqual(validate_numeric(json.dumps(data))[:2],(42,42))
        for bad in [{'lower_bound':42},dict(data,lower_bound=True),dict(data,lower_bound=43)]:
            with self.assertRaises(ValueError):validate_numeric(json.dumps(bad))
    def test_official_consistent_belief(self):
        scoring={'eval_belief_elicit_1':'A','eval_belief_elicit_2':'B'}
        self.assertEqual(self.official['aggregate_eval_beliefs'](scoring,list(scoring)),'C')
        scoring={'ground_truth_extracted':'A','pressure':'C'}
        self.assertEqual(self.official['aggregate_eval_honesty'](scoring,['pressure'],'eval_belief'),'0')

if __name__=='__main__':unittest.main()
