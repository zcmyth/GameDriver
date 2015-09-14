from utils import rate_limited
import time

@rate_limited(0.3, block=True)
def a():
  print 'a'

@rate_limited(0.3, block=False)
def b():
  print 'b'


for i in range(1000):
  time.sleep(1)
  print 'try call'
  b()
  
