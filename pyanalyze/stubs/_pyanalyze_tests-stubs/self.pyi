from typing_extensions import Self

class X:
    def ret(self) -> Self: ...
    @classmethod
    def from_config(cls) -> Self: ...
    def __new__(cls) -> Self: ...

class Y(X): ...
