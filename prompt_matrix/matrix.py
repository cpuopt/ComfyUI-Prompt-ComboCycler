from __future__ import annotations

from dataclasses import dataclass
from math import comb, gcd
import random
from typing import Iterable, Literal

MatrixMode = Literal["combination", "permutation"]


@dataclass(frozen=True)
class MatrixSource:
    items: tuple[str, ...]
    mode: MatrixMode
    choose_k: int
    item_separator: str
    enabled: bool = True

    @property
    def count(self) -> int:
        if not self.enabled or len(self.items) == 0:
            return 1
        k = clamp_choose_k(self.choose_k, len(self.items))
        if self.mode == "permutation":
            return permutation_count(len(self.items), k)
        return choose_count(len(self.items), k)

    def to_payload(self) -> dict:
        return {
            "_prompt_matrix_source": True,
            "items": list(self.items),
            "mode": self.mode,
            "choose_k": self.choose_k,
            "item_separator": self.item_separator,
            "enabled": self.enabled,
            "count": self.count,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "MatrixSource":
        return cls(
            items=tuple(str(item) for item in payload.get("items", [])),
            mode=normalize_mode(payload.get("mode", "combination")),
            choose_k=int(payload.get("choose_k", 1)),
            item_separator=str(payload.get("item_separator", ", ")),
            enabled=bool(payload.get("enabled", True)),
        )


def normalize_mode(mode: str) -> MatrixMode:
    return "permutation" if mode == "permutation" else "combination"


def parse_prompt_lines(text: str | None) -> tuple[str, ...]:
    if not text:
        return ()
    return tuple(line.strip() for line in str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n") if line.strip())


def clamp_choose_k(k: int, n: int) -> int:
    if n <= 0:
        return 0
    return max(1, min(int(k), n))


def choose_count(n: int, k: int) -> int:
    if n < 0:
        return 0
    if k < 0 or k > n:
        return 0
    return comb(n, k)


def permutation_count(n: int, k: int) -> int:
    if n < 0:
        return 0
    if k < 0 or k > n:
        return 0
    result = 1
    for value in range(n - k + 1, n + 1):
        result *= value
    return result


def unrank_combination(n: int, k: int, index: int) -> list[int]:
    total = choose_count(n, k)
    if total <= 0:
        return []
    index %= total
    result: list[int] = []
    start = 0
    for position in range(k):
        remaining_slots = k - position - 1
        for candidate in range(start, n - remaining_slots):
            block = choose_count(n - candidate - 1, remaining_slots)
            if index < block:
                result.append(candidate)
                start = candidate + 1
                break
            index -= block
    return result


def unrank_permutation(n: int, k: int, index: int) -> list[int]:
    total = permutation_count(n, k)
    if total <= 0:
        return []
    index %= total
    available = list(range(n))
    result: list[int] = []
    for position in range(k):
        remaining_slots = k - position - 1
        block = permutation_count(len(available) - 1, remaining_slots)
        choice_position = 0 if block == 0 else index // block
        index = 0 if block == 0 else index % block
        result.append(available.pop(choice_position))
    return result


def source_from_text(
    text: str | None,
    mode: str,
    choose_k: int,
    item_separator: str,
    enabled: bool = True,
) -> MatrixSource:
    return MatrixSource(
        items=parse_prompt_lines(text),
        mode=normalize_mode(mode),
        choose_k=int(choose_k),
        item_separator=str(item_separator),
        enabled=bool(enabled),
    )


def select_from_source(source: MatrixSource | dict, index: int) -> str:
    if isinstance(source, dict):
        source = MatrixSource.from_payload(source)
    if not source.enabled or len(source.items) == 0:
        return ""

    k = clamp_choose_k(source.choose_k, len(source.items))
    if k == 0:
        return ""

    if source.mode == "permutation":
        item_indices = unrank_permutation(len(source.items), k, index)
    else:
        item_indices = unrank_combination(len(source.items), k, index)

    return source.item_separator.join(source.items[item_index] for item_index in item_indices)


def mixed_radix_indices(global_index: int, counts: Iterable[int]) -> list[int]:
    counts_list = [max(1, int(count)) for count in counts]
    local_indices = [0] * len(counts_list)
    remaining = int(global_index)
    for idx in range(len(counts_list) - 1, -1, -1):
        count = counts_list[idx]
        local_indices[idx] = remaining % count
        remaining //= count
    return local_indices


def stable_random_index(total: int, seed: int, execution_counter: int) -> int:
    if total <= 1:
        return 0
    rng = random.Random(f"prompt-matrix:{int(seed)}:repeat:{int(execution_counter)}")
    return rng.randrange(total)


def shuffle_no_repeat_index(total: int, seed: int, cursor: int) -> int:
    if total <= 1:
        return 0
    position = cursor % total
    cycle = cursor // total
    rng = random.Random(f"prompt-matrix:{int(seed)}:shuffle:{int(cycle)}:{int(total)}")
    offset = rng.randrange(total)
    stride = 1
    for _ in range(256):
        candidate = rng.randrange(1, total)
        if gcd(candidate, total) == 1:
            stride = candidate
            break
    return (offset + position * stride) % total
