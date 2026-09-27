"""Opt-in sample values and their masking.

Spec: section 3.4 *Samples*. Values of identifying shapes (``Options.masked_shapes``) are
masked character by character so their shape stays visible: letters become ``x``, digits ``0``, everything else is kept, and the
first character is kept (``anna@example.com`` → ``axxx@xxxxxxx.xxx``).
"""

from collections.abc import Collection

from ddp_parser.model import Samples, Shape

type Scalar = str | int | float | bool


def mask(value: str) -> str:
    masked = ("x" if char.isalpha() else "0" if char.isdigit() else char for char in value[1:])
    return value[:1] + "".join(masked)


def build_samples(
    observed: list[tuple[Scalar, Shape | None]], masked: Collection[str]
) -> Samples | None:
    if not observed:
        return None
    values: list[Scalar] = []
    redacted = False
    for value, shape in observed:
        if isinstance(value, str) and shape in masked:
            values.append(mask(value))
            redacted = True
        else:
            values.append(value)
    return Samples(tuple(values), redacted=redacted)
