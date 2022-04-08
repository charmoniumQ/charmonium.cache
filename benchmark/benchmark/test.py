def g(a: int, b: int) -> int:
    if a == 0:
        return 1
    else:
        result = a * b
        result += g(a-1, b)
        return result

def f() -> int:
    a = g(g(0, 1), g(2, 3))
    b = g(1, 2)
    c = a + b
    return c

def main() -> None:
    f()
