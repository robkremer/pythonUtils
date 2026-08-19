'''
Created on Jul 4, 2026

@author: robkremer
'''
import math

def pythag2(a:float|None=None, b:float|None=None, c:float|None=None) -> float|bool:
  def printTriangle(a:float, b:float, c:float):
    fudgeFactor = 1.5
    a_, b_ = a, b
    while a_ < 5.0 or b_ < 5.0:
      a_ *= 2
      b_ *= 2
    middle:int = int(a_/2)
    at = f'{a:.2f}'
    bt = f'{b:.2f}'
    ct = f'{c:.2f}'
    for line in range(0, int(a_)):
      print(f'{" "*len(at) if (line != middle) else at}|{" "*int(line/(a_-1)*b_*fudgeFactor)}\{"" if (line!=middle) else ct}')
    print(f'{" "*int(len(at))}{"-"*int((b_+2)*fudgeFactor)}')
    print(f'{" "*int(len(at)+((b-len(bt))/2+1)*fudgeFactor)}{bt}')
    
  count = len([1 for i in [a, b, c] if i is not None])
  if count == 2:
    print("One value missing. Calculating missing value.")
    if c is None:
      out = c = math.sqrt(a**2 + b**2)
      print(f'c = {c}')
    if b is None:
      out = b = math.sqrt(c**2 - a**2)
      print(f'b = {b}')
    if a is None:
      out = a = math.sqrt(c**2 - b**2)
      print(f'a = {a}')
    printTriangle(a,b,c)
    return out
  
  if count == 3:
    print("All are provided. Checking if valid.")
    printTriangle(a,b,c)
    return a**2 + b**2 == c**2
  
  raise ArithmeticError("Error: More than one value missing. Nope.")
  
pythag2(3, 4)
pythag2(3, c=5)
pythag2(b=4, c=5)
pythag2(3, 4, 5)
#pythag2(2)
pythag2(6,9,11)
pythag2(9,6,11)
pythag2(29.567,6.9,11)
pythag2(2, 29.567, 11)
