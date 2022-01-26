import random
import time

class Struct:
    pass

x = Struct()
print("id", id(x))
print("hash", hash(x))
print("time", time.time())
print("random", random.random())
