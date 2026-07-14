"""The lexicon is the single source of visible strings; it must stay in
newspaper English (REDESIGN.md §1)."""

from smc import lexicon


def _visible_strings():
    for table in (lexicon.STRATEGIES, lexicon.ATTACKERS, lexicon.OBJECTIVES):
        for name, blurb in table.values():
            yield name
            yield blurb
    yield lexicon.CONDITION
    yield lexicon.metric_phrase()
    yield lexicon.metric_phrase("linear")
    yield lexicon.metric_phrase("threshold", 2)
    yield lexicon.GOALPOST_LEFT
    yield lexicon.GOALPOST_RIGHT


def test_no_jargon_in_visible_strings():
    offenders = []
    for s in _visible_strings():
        for banned in lexicon.BANNED_IN_VISIBLE:
            if banned in s:
                offenders.append((banned, s))
    assert not offenders, offenders


def test_pct_formatting():
    assert lexicon.pct(0.206) == "21%"
    assert lexicon.pct(0.206, 1) == "20.6%"
    assert lexicon.pct(1.0) == "100%"


def test_sentence_case_names():
    """Names start with a capital and are not shouting (product names exempt)."""
    for name, _ in lexicon.STRATEGIES.values():
        assert name[0].isupper() or name in ("You",), name
        if name not in ("SACRED",) and not name.startswith("SACRED"):
            assert not name.isupper(), name
