class Bitmath:
    value: float
    def __init__(self, value: int) -> None: ...
    def to_MiB(self) -> Bitmath: ...
    def to_KiB(self) -> Bitmath: ...
    def to_Byte(self) -> Bitmath: ...
    def __add__(self, other: Bitmath) -> Bitmath: ...
    def __sub__(self, other: Bitmath) -> Bitmath: ...
    def __lt__(self, other: Bitmath) -> bool: ...
    def __le__(self, other: Bitmath) -> bool: ...
    def __gt__(self, other: Bitmath) -> bool: ...
    def __ge__(self, other: Bitmath) -> bool: ...
    def __eq__(self, other: Bitmath) -> bool: ...
    def __ne__(self, other: Bitmath) -> bool: ...
    def format(self, fmt_string: str) -> str: ...

def MiB(value: int) -> Bitmath: ...
def KiB(value: int) -> Bitmath: ...
def Byte(value: int) -> Bitmath: ...
def parse_string(value: str) -> Bitmath: ...
