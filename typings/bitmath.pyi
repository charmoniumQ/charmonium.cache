class Bitmath:
    value: float
    def __init__(self, value: int) -> None:
        ...
    def to_Byte(self) -> Bitmath:
        ...

class MiB(Bitmath):
    def __init__(self, value: int) -> None:
        ...
