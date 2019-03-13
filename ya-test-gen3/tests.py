import unittest
from itertools import tee
from generator import sum_generators
class TestGenSumm(unittest.TestCase):
    #src_a=None
    #src_b=None
    #src_c=None
    
    def setUp(self):
        self.src_a=iter([
            {'a':1},
            {'b':1},
            {'c':1},
            {'d':1},
            {'e':1}
        ])
        self.src_b=iter([
            {'a':1},
            {'b':2},
            {'c':3},
            {'d':4},
            {'':5}
        ])
        self.src_c=iter([
            {'a':5},
            {'b':5},
            {'c':5},
            {None:5}
        ])
    
    def test_full_params_ok(self):
        res=sum_generators(self.src_a,self.src_b,self.src_c,3,False)
        self.assertEqual(res,{'a':7,'b':8,'c':9},msg='summ fit')
    #def test_full_params_fail(self):
    #    res=sum_generators(self.src_a,self.src_b,self.src_c,3,False)
    #    self.assertEqual(res,{'a':1,'b':8,'c':9},msg='summ fit')

    def test_no_len_params_ok(self):
        res=sum_generators(self.src_a,self.src_b,self.src_c,stop_on_empty=False)
        self.assertEqual(res,{'a':7,'b':8,'c':9,'d':5,'e':1,"":5,None:5},msg='summ fit')

    def test_not_a_generator_params_raise(self):
        self.assertRaisesRegex(TypeError,"object is not an iterator",sum_generators,self.src_a,self.src_b,[{'a':1},{'b':2}],2,stop_on_empty=False)#,msg='not an iterator'

    def test_big_len_ok(self):
        res=sum_generators(self.src_a,self.src_b,self.src_c,10,stop_on_empty=False)
        self.assertEqual(res,{'a':7,'b':8,'c':9,'d':5,'e':1,"":5,None:5},msg='summ fit')

    def test_big_len_raise(self):
        self.assertRaises(StopIteration,sum_generators,self.src_a,self.src_b,self.src_c,10,stop_on_empty=True)#,msg='raises at stop'

    def test_not_a_number_raise(self):
        c=iter([{'a':1},{'b':'qwerty'}])
        self.assertRaises(TypeError,sum_generators,self.src_a,self.src_b,c,2,stop_on_empty=False)#,msg='raises at stop'

if __name__ == '__main__':
    unittest.main()
