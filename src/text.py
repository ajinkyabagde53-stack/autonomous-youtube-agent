from __future__ import annotations

import re

# Common English words that carry no topic meaning. Without this list, words
# like "how", "best" or "your" make almost every title match every topic.
STOPWORDS = frozenset("""
a about after again all also always an and any are as at be because been before
being best better between both but by can could did do does doing done down each
even ever every few for from get gets getting got had has have having here how
into its it's just know least less like made make makes making many may more
most much must need needs never new next not now off old once one only other our
out over own part really right same see should since some still such than that
the their them then there these they thing things this those through time times
too top under until use used using very want was way ways well were what when
where which while who why will with without would yes yet you your youre you're
video videos episode full official
""".split())


def tokenize(value: str) -> set[str]:
    """Meaningful lowercase words (3+ characters, stopwords removed)."""
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 2 and token not in STOPWORDS
    }


def title_tokens(value: str) -> list[str]:
    """Ordered meaningful words, for building candidate phrases from titles."""
    return [
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 3 and token not in STOPWORDS and not token.isdigit()
    ]


def coverage(topic_tokens: set[str], text_tokens: set[str]) -> float:
    """Share of the topic's words that appear in the text (0-1)."""
    if not topic_tokens:
        return 0.0
    return len(topic_tokens & text_tokens) / len(topic_tokens)


def matches(topic_tokens: set[str], text_tokens: set[str], threshold: float = 0.5) -> bool:
    """True when at least `threshold` of the topic's words appear in the text."""
    return bool(topic_tokens) and coverage(topic_tokens, text_tokens) >= threshold
