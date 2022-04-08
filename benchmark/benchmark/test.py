def g(a, b):
    if a == 0:
        return 1
    else:
        result = a * b
        result += g(a-1, b)
        return result

def f():
    a = g(g(0, 1), g(2, 3))
    b = g(1, 2)
    c = a + b
    return c

def main():
    f()
