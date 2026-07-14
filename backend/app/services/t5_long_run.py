"""T5 long-run harness: resumable real-provider chapter generation and evidence reports."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


TERMINAL_BATCH_STATES = {"succeeded", "needs_review", "failed", "cancelled"}


class T5RunError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, base_url: str, token: str = "", api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.api_key = api_key
        self._email = ""
        self._password = ""

    def request(self, method: str, path: str, body: dict | None = None, _retry_auth: bool = True) -> Any:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        req = urllib.request.Request(
            f"{self.base_url}{path}", method=method, headers=headers,
            data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            if exc.code == 401 and _retry_auth and self._email and path != "/auth/login":
                self.login(self._email, self._password)
                return self.request(method, path, body, _retry_auth=False)
            raise T5RunError(f"{method} {path} failed ({exc.code}): {detail[:500]}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise T5RunError(f"{method} {path} failed: {exc}") from exc
        return payload.get("data", payload)

    def login(self, email: str, password: str) -> None:
        self._email, self._password = email, password
        self.token = ""
        data = self.request("POST", "/auth/login", {"email": email, "password": password}, _retry_auth=False)
        token = data.get("access_token") if isinstance(data, dict) else None
        if not token:
            raise T5RunError("login response did not contain access_token")
        self.token = token


@dataclass
class T5Config:
    project_id: str
    novel_id: str
    target_new_chapters: int = 100
    batch_size: int = 10
    poll_seconds: float = 5.0
    max_poll_seconds: int = 7200
    max_resume_attempts: int = 3
    allow_needs_review: bool = False
    estimated_cost_per_chapter_cny: float = 0.03
    cost_cap_cny: float = 5.0

    def validate(self) -> None:
        if not self.project_id or not self.novel_id:
            raise T5RunError("project_id and novel_id are required")
        if not 1 <= self.target_new_chapters <= 1000:
            raise T5RunError("target_new_chapters must be between 1 and 1000")
        if not 1 <= self.batch_size <= 50:
            raise T5RunError("batch_size must be between 1 and 50")
        estimated = self.target_new_chapters * self.estimated_cost_per_chapter_cny
        if estimated > self.cost_cap_cny:
            raise T5RunError(
                f"estimated cost ¥{estimated:.2f} exceeds configured cap ¥{self.cost_cap_cny:.2f}"
            )


@dataclass
class Checkpoint:
    project_id: str
    novel_id: str
    target_new_chapters: int
    baseline_chapters: int = 0
    batch_ids: list[str] = field(default_factory=list)
    resume_attempts: dict[str, int] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""


def extract_body_text(body: Any) -> str:
    if isinstance(body, str):
        return body
    if isinstance(body, list):
        return "\n".join(extract_body_text(item) for item in body)
    if isinstance(body, dict):
        own = body.get("text") if isinstance(body.get("text"), str) else ""
        nested = extract_body_text(body.get("content", []))
        return "\n".join(part for part in (own, nested) if part)
    return ""


def _ngrams(text: str, size: int = 5) -> set[str]:
    normalized = re.sub(r"\s+", "", text or "")
    return {normalized[index:index + size] for index in range(max(0, len(normalized) - size + 1))}


def adjacent_repeat_scores(chapters: list[dict]) -> list[dict]:
    scores = []
    ordered = sorted(chapters, key=lambda item: int((item.get("meta") or {}).get("seq") or 0))
    for previous, current in zip(ordered, ordered[1:]):
        left, right = _ngrams(extract_body_text(previous.get("body"))), _ngrams(extract_body_text(current.get("body")))
        union = left | right
        score = len(left & right) / len(union) if union else 0.0
        scores.append({"previous_id": previous.get("id"), "current_id": current.get("id"),
                       "jaccard_5gram": round(score, 4)})
    return scores


def build_evidence(chapters: list[dict], checkpoint: Checkpoint, batches: list[dict]) -> dict:
    generated = chapters[checkpoint.baseline_chapters:]
    scores = [float((item.get("meta") or {}).get("review_score")) for item in generated
              if (item.get("meta") or {}).get("review_score") is not None]
    continuity = [((item.get("meta") or {}).get("continuity") or {}).get("status", "missing")
                  for item in generated]
    repeats = adjacent_repeat_scores(generated)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_id": checkpoint.project_id,
        "novel_id": checkpoint.novel_id,
        "target_new_chapters": checkpoint.target_new_chapters,
        "baseline_chapters": checkpoint.baseline_chapters,
        "new_chapters": len(generated),
        "reviewed_chapters": sum(item.get("status") == "reviewed" for item in generated),
        "needs_rewrite_chapters": sum(item.get("status") == "needs_rewrite" for item in generated),
        "average_review_score": round(sum(scores) / len(scores), 2) if scores else None,
        "continuity": {status: continuity.count(status) for status in sorted(set(continuity))},
        "max_adjacent_5gram_jaccard": max((item["jaccard_5gram"] for item in repeats), default=0.0),
        "adjacent_repeat_scores": repeats,
        "batches": batches,
        "checkpoint": asdict(checkpoint),
        "accepted": len(generated) >= checkpoint.target_new_chapters
                    and not any(item.get("status") == "needs_rewrite" for item in generated)
                    and all(status in {"clean", "flagged"} for status in continuity),
    }


def write_evidence(evidence: dict, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = output_dir / "t5-evidence.json", output_dir / "t5-report.md"
    json_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# NovelCraft T5 长跑验收报告", "",
        f"- 生成时间：{evidence['generated_at']}",
        f"- Novel：`{evidence['novel_id']}`",
        f"- 目标/新增章节：{evidence['target_new_chapters']} / {evidence['new_chapters']}",
        f"- 已审核/待返工：{evidence['reviewed_chapters']} / {evidence['needs_rewrite_chapters']}",
        f"- 平均审核分：{evidence['average_review_score']}",
        f"- 连续性状态：`{json.dumps(evidence['continuity'], ensure_ascii=False)}`",
        f"- 相邻章节最大 5-gram Jaccard：{evidence['max_adjacent_5gram_jaccard']}",
        f"- 验收结论：{'通过' if evidence['accepted'] else '未通过'}", "",
        "> 报告只记录实际 API/数据库返回；未通过不会被改写为成功。", "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


class LongRunRunner:
    def __init__(self, client: ApiClient, config: T5Config, checkpoint_path: Path,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        config.validate()
        self.client, self.config, self.checkpoint_path, self.sleep = client, config, checkpoint_path, sleep

    def _save(self, checkpoint: Checkpoint) -> None:
        checkpoint.updated_at = datetime.now(timezone.utc).isoformat()
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path.write_text(json.dumps(asdict(checkpoint), ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_or_create(self, baseline: int) -> Checkpoint:
        if self.checkpoint_path.exists():
            checkpoint = Checkpoint(**json.loads(self.checkpoint_path.read_text(encoding="utf-8")))
            if (checkpoint.project_id, checkpoint.novel_id) != (self.config.project_id, self.config.novel_id):
                raise T5RunError("checkpoint belongs to another project/novel")
            if checkpoint.target_new_chapters != self.config.target_new_chapters:
                raise T5RunError("checkpoint target differs from requested target_new_chapters")
            return checkpoint
        checkpoint = Checkpoint(self.config.project_id, self.config.novel_id,
                                self.config.target_new_chapters, baseline_chapters=baseline)
        self._save(checkpoint)
        return checkpoint

    def _chapters(self) -> list[dict]:
        chapters: list[dict] = []
        offset = 0
        while True:
            page = self.client.request(
                "GET", f"/contents?project_id={self.config.project_id}&parent_id={self.config.novel_id}"
                       f"&limit=200&offset={offset}"
            )
            chapters.extend(page)
            if len(page) < 200:
                return chapters
            offset += len(page)

    def _wait_batch(self, batch_id: str, checkpoint: Checkpoint) -> dict:
        deadline = time.monotonic() + self.config.max_poll_seconds
        while time.monotonic() < deadline:
            batch = self.client.request("GET", f"/generation-batches/{batch_id}")
            status = batch.get("status")
            if status == "failed":
                attempts = checkpoint.resume_attempts.get(batch_id, 0)
                if attempts >= self.config.max_resume_attempts:
                    raise T5RunError(f"batch {batch_id} exhausted failure resumes: {batch.get('error')}")
                self.client.request("POST", f"/generation-batches/{batch_id}/resume", {})
                checkpoint.resume_attempts[batch_id] = attempts + 1
                self._save(checkpoint)
            elif status in TERMINAL_BATCH_STATES:
                if status == "cancelled":
                    raise T5RunError(f"batch {batch_id} ended as {status}: {batch.get('error')}")
                if status == "needs_review" and not self.config.allow_needs_review:
                    raise T5RunError(f"batch {batch_id} requires review; rerun with explicit allow_needs_review")
                return batch
            self.sleep(self.config.poll_seconds)
        raise T5RunError(f"batch {batch_id} timed out after {self.config.max_poll_seconds}s")

    def run(self) -> tuple[Checkpoint, list[dict], list[dict]]:
        novel = self.client.request("GET", f"/contents/{self.config.novel_id}")
        if novel.get("project_id") != self.config.project_id or novel.get("type") != "novel":
            raise T5RunError("novel does not belong to project or is not type=novel")
        initial = self._chapters()
        checkpoint = self._load_or_create(len(initial))
        batch_evidence = []
        # A process may have died after persisting a batch id but before that
        # batch finished. Reconcile every checkpointed batch before creating a
        # new one, otherwise a restart can over-generate chapters.
        for batch_id in checkpoint.batch_ids:
            batch = self.client.request("GET", f"/generation-batches/{batch_id}")
            if batch.get("status") not in {"succeeded", "needs_review"}:
                batch = self._wait_batch(batch_id, checkpoint)
            if batch.get("status") == "needs_review" and not self.config.allow_needs_review:
                raise T5RunError(f"batch {batch_id} requires review; explicit override is required")
            batch_evidence.append(batch)
        while len(self._chapters()) - checkpoint.baseline_chapters < checkpoint.target_new_chapters:
            remaining = checkpoint.target_new_chapters - (len(self._chapters()) - checkpoint.baseline_chapters)
            count = min(self.config.batch_size, remaining)
            created = self.client.request("POST", f"/novels/{self.config.novel_id}/chapters/batch",
                                          {"chapter_count": count})
            batch_id = created["batch_id"]
            checkpoint.batch_ids.append(batch_id)
            self._save(checkpoint)
            batch_evidence.append(self._wait_batch(batch_id, checkpoint))
        return checkpoint, self._chapters(), batch_evidence
