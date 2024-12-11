"""A re parser."""

from collections.abc import Container
from dataclasses import dataclass
from typing import ClassVar, Literal, Optional, Union, get_args

Quantifier = Literal["*", "?", "+"]
QUANTIFIERS = set(get_args(Quantifier))
SPECIAL = {"(", ")", "[", "]", *QUANTIFIERS, ".", "\\", "^", "$", "{", "["}


@dataclass
class ParseError(Exception):
    pos: int
    message: str


@dataclass
class Node:
    can_be_quantified: ClassVar[bool] = True
    start_pos: int
    end_pos: int


@dataclass
class Text(Node):
    value: str

    def __str__(self) -> str:
        return self.value


@dataclass
class Dot(Node):
    def __str__(self) -> str:
        return "."


@dataclass
class Begin(Node):
    def __str__(self) -> str:
        return "^"


@dataclass
class End(Node):
    def __str__(self) -> str:
        return "$"


@dataclass
class NonCapturingGroup(Node):
    inner: Node

    def __str__(self) -> str:
        return f"(?:{self.inner})"


@dataclass
class NumberedGroup(Node):
    inner: Node

    def __str__(self) -> str:
        return f"({self.inner})"


@dataclass
class SequencePattern(Node):
    can_be_quantified: ClassVar[bool] = False
    children: list[Node]

    def __str__(self) -> str:
        return "".join(str(child) for child in self.children)


@dataclass
class Quantified(Node):
    can_be_quantified: ClassVar[bool] = False
    inner: Node
    quantifier: Quantifier

    def __str__(self) -> str:
        return f"{self.inner}{self.quantifier}"


@dataclass
class MinimalQuantified(Node):
    can_be_quantified: ClassVar[bool] = False
    inner: Node
    quantifier: Quantifier

    def __str__(self) -> str:
        return f"{self.inner}{self.quantifier}?"


@dataclass
class PosessiveQuantified(Node):
    can_be_quantified: ClassVar[bool] = False
    inner: Node
    quantifier: Quantifier

    def __str__(self) -> str:
        return f"{self.inner}{self.quantifier}+"


@dataclass
class ExactRepetition(Node):
    can_be_quantified: ClassVar[bool] = False
    inner: Node
    count: int

    def __str__(self):
        return f"{self.inner}{{{self.count}}}"


@dataclass
class RangedRepetition(Node):
    can_be_quantified: ClassVar[bool] = False
    inner: Node
    minimum: int
    maximum: int

    def __str__(self):
        return f"{self.inner}{{{self.minimum},{self.maximum}}}"


@dataclass
class MinimalRangedRepetition(Node):
    can_be_quantified: ClassVar[bool] = False
    inner: Node
    minimum: int
    maximum: int

    def __str__(self):
        return f"{self.inner}{{{self.minimum},{self.maximum}}}?"


@dataclass
class PossessiveRangedRepetition(Node):
    can_be_quantified: ClassVar[bool] = False
    inner: Node
    minimum: int
    maximum: int

    def __str__(self):
        return f"{self.inner}{{{self.minimum},{self.maximum}}}+"


@dataclass
class CharacterClass(Node):
    char: str

    def __str__(self):
        return f"\\{self.char}"


@dataclass
class Character(Node):
    char: str

    def __str__(self):
        return self.char


@dataclass
class CharacterRange(Node):
    min: str
    max: str

    def __str__(self):
        return f"{self.min}-{self.max}"


CharSetMember = Union[CharacterClass, Character, CharacterRange]


@dataclass
class CharacterSet(Node):
    members: list[CharSetMember]
    is_inverted: bool

    def __str__(self):
        inv = "^" if self.is_inverted else ""
        return f"[{inv}{''.join(map(str, self.members))}]"


@dataclass
class _ParserState:
    text: str
    pos: int

    def peek(self) -> Optional[str]:
        if self.pos < len(self.text):
            return self.text[self.pos]
        return None

    def next(self, message: str = "Unexpected end of input"):
        value = self.peek()
        if value is None:
            raise ParseError(self.pos, message)
        self.pos += 1
        return value


def _parse_text(st: _ParserState) -> Text:
    start_pos = st.pos
    while st.pos < len(st.text) and st.text[st.pos] not in SPECIAL:
        st.pos += 1
    return Text(start_pos, st.pos, st.text[start_pos : st.pos])


def _parse_int(st: _ParserState) -> int:
    chars = []
    while st.pos < len(st.text) and st.text[st.pos].isdigit():
        chars.append(st.text[st.pos])
        st.pos += 1
    if not chars:
        raise ParseError(st.pos, "Expected a number")
    return int("".join(chars))


def _parse_parenthesized(st: _ParserState) -> Node:
    start_pos = st.pos
    st.pos += 1
    if st.peek() == "?":
        # Extension pattern
        st.pos += 1
        next_char = st.next()
        if next_char == ":":
            inner = _parse_and_close(st, ")", "Unterminated parentheses")
            return NonCapturingGroup(start_pos, st.pos, inner)
        else:
            raise ParseError(st.pos, f"Unsupported extension {next_char!r}")
    else:
        inner = _parse_and_close(st, ")", "Unterminated parentheses")
        return NumberedGroup(start_pos, st.pos, inner)


def _parse_and_close(st: _ParserState, closing: str, message: str) -> Node:
    inner = _parse_pattern(st, {closing})
    if st.pos < len(st.text):
        assert st.text[st.pos] == closing
        st.pos += 1
    else:
        raise ParseError(st.pos, message)
    return inner


def _create_ranges(members: list[CharSetMember]) -> list[CharSetMember]:
    pending_range: Optional[Character] = None
    final_members: list[CharSetMember] = []
    for i, member in enumerate(members):
        if pending_range is not None:
            if isinstance(member, Character):
                range_start = final_members[-1]
                if not isinstance(range_start, Character):
                    raise ParseError(
                        range_start.start_pos, "Range can only contain characters"
                    )
                final_members[-1] = CharacterRange(
                    range_start.start_pos, member.end_pos, range_start.char, member.char
                )
                pending_range = None
            else:
                raise ParseError(member.start_pos, "Range can only contain characters")
        elif i > 0 and isinstance(member, Character) and member.char == "-":
            pending_range = member
        else:
            final_members.append(member)
    return final_members


def _parse_charset_members(st: _ParserState) -> list[CharSetMember]:
    members: list[CharSetMember] = []
    while st.pos < len(st.text):
        start_pos = st.pos
        c = st.next()
        if c == "]":
            return _create_ranges(members)
        elif c == "\\":
            following = st.next()
            if following.isalpha():
                members.append(CharacterClass(start_pos, st.pos, following))
            else:
                members.append(Character(start_pos, st.pos, following))
        else:
            members.append(Character(start_pos, st.pos, c))

    raise ParseError(st.pos, "Unexpected end of input in character class")


def _parse_pattern(st: _ParserState, end_chars: Container[str] = frozenset()) -> Node:
    children: list[Node] = []
    start_pos = st.pos
    while st.pos < len(st.text):
        c = st.text[st.pos]
        if c in end_chars:
            break
        if c == "(":
            children.append(_parse_parenthesized(st))
        elif c == ".":
            children.append(Dot(st.pos, st.pos + 1))
            st.pos += 1
        elif c == "^":
            children.append(Begin(st.pos, st.pos + 1))
            st.pos += 1
        elif c == "$":
            children.append(End(st.pos, st.pos + 1))
            st.pos += 1
        elif c in QUANTIFIERS:
            if not children:
                raise ParseError(st.pos, f"Quantifier {c!r} must follow a pattern")
            st.pos += 1
            to_wrap = children[-1]
            if st.pos < len(st.text) and st.text[st.pos] == "?":
                st.pos += 1
                children[-1] = MinimalQuantified(to_wrap.start_pos, st.pos, to_wrap, c)
            elif st.pos < len(st.text) and st.text[st.pos] == "+":
                st.pos += 1
                children[-1] = PosessiveQuantified(
                    to_wrap.start_pos, st.pos, to_wrap, c
                )
            else:
                children[-1] = Quantified(to_wrap.start_pos, st.pos, to_wrap, c)
        elif c == "{":
            st.pos += 1
            if not children:
                raise ParseError(st.pos, "'{' must follow a pattern")
            min_count = _parse_int(st)
            next_char = st.next()
            to_wrap = children[-1]
            if next_char == "}":
                children[-1] = ExactRepetition(
                    to_wrap.start_pos, st.pos, to_wrap, min_count
                )
            elif next_char == ",":
                max_count = _parse_int(st)
                if st.next() != "}":
                    raise ParseError(st.pos - 1, "Expected '}'")
                next_char = st.peek()
                if next_char == "?":
                    st.pos += 1
                    children[-1] = MinimalRangedRepetition(
                        to_wrap.start_pos, st.pos, to_wrap, min_count, max_count
                    )
                elif next_char == "+":
                    st.pos += 1
                    children[-1] = PossessiveRangedRepetition(
                        to_wrap.start_pos, st.pos, to_wrap, min_count, max_count
                    )
                else:
                    children[-1] = RangedRepetition(
                        to_wrap.start_pos, st.pos, to_wrap, min_count, max_count
                    )
            else:
                raise ParseError(st.pos - 1, "Expected ',' or '}'")
        elif c == "[":
            start_pos = st.pos
            st.pos += 1
            if st.peek() == "^":
                st.next()
                is_inverted = True
            else:
                is_inverted = False
            members = _parse_charset_members(st)
            children.append(CharacterSet(start_pos, st.pos, members, is_inverted))
        else:
            children.append(_parse_text(st))
    if len(children) == 1:
        return children[0]
    else:
        return SequencePattern(start_pos, st.pos, children)


def parse(text: str) -> Node:
    return _parse_pattern(_ParserState(text, 0))
