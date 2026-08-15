"""工作台账：把任务中间状态结构化落盘（JSON），支持断点续跑与追溯。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

LEDGER_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "ledger"


class WorkLedger:
    def __init__(self, task: str, task_id: str | None = None):
        self.task_id = task_id or datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = LEDGER_DIR / f"{self.task_id}.json"
        self.data = {
            "task_id": self.task_id,
            "task": task,
            "created_at": self._now(),
            "updated_at": self._now(),
            "status": "running",
            "actions": [],
            "failures": [],
        }
        self.save()

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def save(self) -> None:
        self.data["updated_at"] = self._now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def record_action(self, name: str, arguments: dict, result: str) -> None:
        entry = {
            "time": self._now(),
            "tool": name,
            "arguments": arguments,
            "result_preview": result[:500],
        }
        self.data["actions"].append(entry)
        if result.startswith("工具执行失败") or result.startswith("搜索失败"):
            self.data["failures"].append(entry)
        self.save()

    def finish(self, final_answer: str) -> None:
        self.data["status"] = "done"
        self.data["final_answer"] = final_answer
        self.save()

    @classmethod
    def load(cls, task_id: str) -> "WorkLedger":
        ledger = cls.__new__(cls)
        ledger.task_id = task_id
        ledger.path = LEDGER_DIR / f"{task_id}.json"
        ledger.data = json.loads(ledger.path.read_text(encoding="utf-8"))
        return ledger