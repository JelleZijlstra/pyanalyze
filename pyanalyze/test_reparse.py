from .reparse import (
    Begin,
    Character,
    CharacterClass,
    CharacterRange,
    CharacterSet,
    Dot,
    End,
    ExactRepetition,
    MinimalQuantified,
    MinimalRangedRepetition,
    NonCapturingGroup,
    NumberedGroup,
    PosessiveQuantified,
    PossessiveRangedRepetition,
    Quantified,
    RangedRepetition,
    SequencePattern,
    Text,
    parse,
)


def test_text() -> None:
    assert parse("a") == Text(0, 1, "a")
    assert parse("ab") == Text(0, 2, "ab")


def test_numbered_group() -> None:
    assert parse("(a)") == NumberedGroup(0, 3, Text(1, 2, "a"))
    assert parse("((a))") == NumberedGroup(0, 5, NumberedGroup(1, 4, Text(2, 3, "a")))


def test_sequence_pattern() -> None:
    assert parse("a(b)") == SequencePattern(
        0, 4, [Text(0, 1, "a"), NumberedGroup(1, 4, Text(2, 3, "b"))]
    )


def test_non_capturing_group() -> None:
    assert parse("(?:ab)") == NonCapturingGroup(0, 6, Text(3, 5, "ab"))


def test_dot() -> None:
    assert parse(".") == Dot(0, 1)


def test_begin() -> None:
    assert parse("^") == Begin(0, 1)


def test_end() -> None:
    assert parse("$") == End(0, 1)


def test_quantifiers() -> None:
    assert parse("a*") == Quantified(0, 2, Text(0, 1, "a"), "*")
    assert parse("a+") == Quantified(0, 2, Text(0, 1, "a"), "+")
    assert parse("a?") == Quantified(0, 2, Text(0, 1, "a"), "?")
    assert parse("a*?") == MinimalQuantified(0, 3, Text(0, 1, "a"), "*")
    assert parse("a*+") == PosessiveQuantified(0, 3, Text(0, 1, "a"), "*")


def test_repetition() -> None:
    assert parse("a{2}") == ExactRepetition(0, 4, Text(0, 1, "a"), 2)
    assert parse("a{234}") == ExactRepetition(0, 6, Text(0, 1, "a"), 234)
    assert parse("a{2,3}") == RangedRepetition(0, 6, Text(0, 1, "a"), 2, 3)
    assert parse("a{2,3}?") == MinimalRangedRepetition(0, 7, Text(0, 1, "a"), 2, 3)
    assert parse("a{2,3}+") == PossessiveRangedRepetition(0, 7, Text(0, 1, "a"), 2, 3)


def test_charset() -> None:
    assert parse("[a]") == CharacterSet(0, 3, [Character(1, 2, "a")], False)
    assert parse("[^a]") == CharacterSet(0, 4, [Character(2, 3, "a")], True)
    assert parse("[ab]") == CharacterSet(
        0, 4, [Character(1, 2, "a"), Character(2, 3, "b")], False
    )
    assert parse("[a-b]") == CharacterSet(0, 5, [CharacterRange(1, 4, "a", "b")], False)
    assert parse(r"[\s]") == CharacterSet(0, 4, [CharacterClass(1, 3, "s")], False)
    assert parse(r"[\@-\!]") == CharacterSet(
        0, 7, [CharacterRange(1, 6, "@", "!")], False
    )
    assert parse("[-]") == CharacterSet(0, 3, [Character(1, 2, "-")], False)
    assert parse("[a^]") == CharacterSet(
        0, 4, [Character(1, 2, "a"), Character(2, 3, "^")], False
    )
