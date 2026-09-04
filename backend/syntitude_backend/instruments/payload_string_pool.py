"""A string pool that behaves exactly like ``export_payload._Intern`` — quirks included.

⛔ **Faithfulness, not correctness, is the requirement here.** This exists so a payload rebuilt from
Postgres interns its strings the way the published one did. Where ``_Intern`` does something
surprising, this must do the same surprising thing, because the published files were built by it and
they are the thing being reproduced.

The three behaviours worth naming, each of which a "cleaner" implementation would get wrong:

* **``None`` and a non-finite float are ``-1``, not entries.** ``-1`` is *absent string*, one of the
  five things ``-1`` means in this payload. It is never an index.
* **Everything else is coerced with ``str()`` before lookup**, so the integer ``5`` and the string
  ``"5"`` are the same entry. That is not a bug to fix — it is how 256 published catalogues were
  interned.
* **Only a real ``float`` is caught by the non-finite test.** ``numpy.float64`` subclasses ``float``
  and is caught; ``numpy.float32`` does not and is **interned as the string ``"nan"``**. Likewise
  ``pandas.NA`` is neither ``None`` nor a float, so it interns as ``"<NA>"``. Neither can reach us
  from Postgres — NULL arrives as ``None`` and the ``measurement()`` CHECK forbids NaN — but the
  rule is written down because the day one of them does arrive, the payload will differ by one
  string and nothing will say why.
"""

from __future__ import annotations

import math

#: ``_Intern.idx`` returns this for an absent string. ⛔ Not an index, and not to be conflated with
#: the ``-1`` that means *the contig ends here* in ``arr.vec`` or *outside the catalogue* in
#: ``map_reps.near`` — different blocks, different meanings, same integer.
ABSENT = -1


class StringPool:
    """``index(value)`` returns a stable index; ``values`` is the table to ship beside it."""

    __slots__ = ("_index_of", "values")

    def __init__(self) -> None:
        self._index_of: dict[str, int] = {}
        self.values: list[str] = []

    def index(self, value: object) -> int:
        """The index of ``value``, assigning one **on first use** — which is what makes order matter."""
        if value is None or (isinstance(value, float) and not math.isfinite(value)):
            return ABSENT
        text = str(value)
        position = self._index_of.get(text)
        if position is None:
            position = len(self.values)
            self._index_of[text] = position
            self.values.append(text)
        return position

    def indices(self, values) -> list[int]:
        """A whole column, interned **left to right** — the order is the meaning."""
        return [self.index(value) for value in values]

    def __len__(self) -> int:
        return len(self.values)
