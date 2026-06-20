"""Polling loop for the Judge Agent."""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from typing import TextIO

from gotra.judge_agent.alaya_client import AlayaClient
from gotra.judge_agent.judge_agent import JudgeAgent
from gotra.judge_agent.llm import CodexJudgeProvider


def auto_judge_enabled() -> bool:
    """Return whether AUTO_JUDGE permits the poller to act."""

    return os.getenv("AUTO_JUDGE", "true").strip().lower() not in {"0", "false", "no", "off"}


@dataclass
class GatePoller:
    """Poll pending Alaya human gates and route Judge decisions."""

    judge: JudgeAgent
    alaya_client: AlayaClient
    interval_seconds: float = 60.0
    dry_run: bool = False
    consecutive_failures: int = 0
    last_evaluated_count: int = 0
    stderr: TextIO = field(default_factory=lambda: sys.stderr)

    def poll_once(self) -> int:
        """Judge all currently pending gates once."""

        gates = self.alaya_client.list_human_gates(status="pending")
        self.last_evaluated_count = len(gates)
        acted = 0
        for gate in gates:
            result = self.judge.judge_gate(str(gate["id"]), apply=not self.dry_run)
            if result.routed_action != "none":
                acted += 1
        self.consecutive_failures = 0
        return acted

    def run_forever(self) -> None:
        """Run a resilient poll loop. Five consecutive failures warn but do not exit."""

        if not auto_judge_enabled():
            raise SystemExit(0)
        while True:
            try:
                self.poll_once()
            except Exception as exc:  # noqa: BLE001 - poller must keep running.
                self.consecutive_failures += 1
                if self.consecutive_failures >= 5:
                    print(
                        f"[judge-poller] {self.consecutive_failures} consecutive failures: {exc}",
                        file=self.stderr,
                    )
            time.sleep(max(0.1, self.interval_seconds))


def interval_from_env() -> float:
    return float(os.getenv("JUDGE_POLL_INTERVAL", "60"))


def build_default_poller(
    *,
    data_dir: str = "engine/ksana/data",
    dry_run: bool = False,
    provenance_log_path: str | None = None,
) -> GatePoller:
    """Build a production poller from environment configuration."""

    alaya_client = AlayaClient.from_env()
    judge = JudgeAgent(
        alaya_client=alaya_client,
        decision_provider=CodexJudgeProvider(),
        data_dir=data_dir,
        provenance_log_path=provenance_log_path,
    )
    return GatePoller(
        judge=judge,
        alaya_client=alaya_client,
        interval_seconds=interval_from_env(),
        dry_run=dry_run,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run gotra Judge Agent gate poller.")
    parser.add_argument("--once", action="store_true", help="poll once and exit")
    parser.add_argument("--data-dir", default="engine/ksana/data")
    parser.add_argument("--dry-run", action="store_true", help="evaluate gates without Alaya writes")
    parser.add_argument("--provenance-log-path", default=None, help="append Judge decisions to JSONL")
    args = parser.parse_args(argv)

    if not auto_judge_enabled():
        return 0
    if args.dry_run:
        print("[judge-poller] dry-run/shadow mode enabled; no Alaya writes will be attempted.")
    poller = build_default_poller(
        data_dir=args.data_dir,
        dry_run=args.dry_run,
        provenance_log_path=args.provenance_log_path,
    )
    if args.once:
        acted = poller.poll_once()
        if args.dry_run:
            print(
                "[judge-poller] dry-run/shadow poll complete; "
                f"gates_evaluated={poller.last_evaluated_count}; routed_actions={acted}"
            )
        return 0
    poller.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
