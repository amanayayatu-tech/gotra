"""Token budget accounting for Phase BT sampled and full runs."""

from __future__ import annotations

from dataclasses import dataclass
import os


class BudgetExceeded(RuntimeError):
    """Raised when a run would exceed its token budget."""


@dataclass
class TokenBudget:
    max_tokens: int | None = None
    spent_tokens: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

    @classmethod
    def from_env(cls, explicit: int | None = None) -> TokenBudget:
        if explicit is not None:
            return cls(max_tokens=explicit)
        value = os.getenv("BT_TOKEN_BUDGET") or os.getenv("JUDGE_DAILY_TOKEN_BUDGET")
        if not value:
            return cls(max_tokens=None)
        return cls(max_tokens=int(value))

    def charge(self, *, cache_key: str, estimated_tokens: int, cache_hit: bool) -> None:
        del cache_key
        if cache_hit:
            self.cache_hits += 1
            return
        self.cache_misses += 1
        proposed = self.spent_tokens + max(0, int(estimated_tokens))
        if self.max_tokens is not None and proposed > self.max_tokens:
            raise BudgetExceeded(
                f"BT token budget exceeded: proposed={proposed}, max={self.max_tokens}"
            )
        self.spent_tokens = proposed

    def snapshot(self) -> dict[str, int | None]:
        return {
            "max_tokens": self.max_tokens,
            "spent_tokens": self.spent_tokens,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
        }


def estimate_tokens(text: str) -> int:
    """Conservative local estimate; real provider usage should override when available."""

    return max(1, len(text.encode("utf-8")) // 4)
