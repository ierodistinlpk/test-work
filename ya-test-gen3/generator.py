from random import randrange as randrange
import logging,sys


#log_level=logging.DEBUG
#log_level=logging.WARNING
log_level=logging.ERROR

logging.basicConfig(level=log_level, handlers=[logging.StreamHandler(sys.stdout)])


def generator(maxkey=1,maxval=100,length=None):
    __doc__="""generator returns {<key>:<val>} where:
    key is 2 letters and random int number from 0 to maxkey-1 (use 1 if you don't need random)
    value is a random integer form 0 to maxval-1.
    zero maxkey or maxval raises ValueError exception"""
    strs=['aa','bb','cc','dd','ee']
    n=0
    while True:
        if length and n>=length:
            return
        k=strs[n%len(strs)]+randrange(maxkey).__str__()
        v=randrange(maxval)
        yield({k:v})
        n+=1


def sum_generators(src_a,src_b,src_c,seq_len=10,stop_on_empty=False):
    """ aggregates summ of three generators used seq_len times
    returns dict with all string keys given from generators and aggregated value to each key
    raises StopIteration at stoped iterator if 'stop_on_empty' was set to True"""
    logging.debug('generators: a %s, b %s, c %s',src_a, src_b,src_c)
    result={}
    for i in range (0,seq_len):
        for gen in [src_a, src_b, src_c]:
            try:
                item=next(gen)
                logging.debug('generator %s, value %s',gen,item)
                key= list(item)[0]
                if  key in result.keys():
                    result[key]+=item[key]
                else:
                    result[key]=item[key]
            except StopIteration as e:
                logging.warning('WARN: generator %s stopped, %s',gen,e)
                if stop_on_empty:
                    raise e
    return result

def main():
    src_a=generator(1,100,10)
    src_b=generator(2,100)
    src_c=generator(3,100)
    result=sum_generators(src_a,src_b,src_c,5)
    print (result)
    result=sum_generators(src_a,src_b,src_c,12)
    print (result)
    result=sum_generators(src_a,src_b,src_c,12,True)
    print (result)            
#    result=sum_generators('asd',src_b,0,12,False)
#    print (result)            


if __name__ == '__main__':
    main()

