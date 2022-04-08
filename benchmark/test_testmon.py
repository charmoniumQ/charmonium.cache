# pytest --testmon --numprocesses=0  test_testmon.py

def test_testmon():
    f(34)

def f(a):
    if a > 30:
        h(a)
    else:
        a += 1
        g(a)

def h(a):
    print("high")

def g(a):
    print("low")
