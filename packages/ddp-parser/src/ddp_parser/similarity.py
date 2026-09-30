"""Whether sibling folders or object values look alike inside (spec 3.5 and 3.6)."""

from collections import Counter
from collections.abc import Sequence


def look_alike(signatures: Sequence[set[str]], threshold: float) -> bool:
    """True if, on average, at least ``threshold`` of each signature's names are shared by more
    than half of the signatures. Empty signatures never look alike.
    """
    if not signatures or not all(signatures):
        return False
    counts = Counter(name for signature in signatures for name in signature)
    common = {name for name, count in counts.items() if count * 2 > len(signatures)}
    shares = [len(signature & common) / len(signature) for signature in signatures]
    return sum(shares) / len(shares) >= threshold
