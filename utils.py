#!/usr/bin/env python3

from typing import Iterable

from cards import Cards


def count_card(plate: Iterable[Cards], card: Cards) -> int:
	return len([c for c in plate if c == card])
