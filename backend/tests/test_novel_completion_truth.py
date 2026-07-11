from __future__ import annotations


class _Cursor:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = many or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class _Db:
    def __init__(self, novel, chapters):
        self.novel = novel
        self.chapters = chapters

    def execute(self, sql, _params=()):
        return _Cursor(one=self.novel) if "type = 'novel'" in sql else _Cursor(many=self.chapters)

    def close(self):
        pass


def _status(monkeypatch, meta, chapters):
    from app.services import novel_export

    monkeypatch.setattr(novel_export, "connect", lambda: _Db({"title": "测试", "status": "draft", "meta": meta}, chapters))
    return novel_export.get_novel_completion_status("novel-1")


def test_one_chapter_is_not_100_percent_of_an_800k_word_novel(monkeypatch):
    chapter = {"status": "reviewed", "body": "一" * 3000, "meta": {"seq": 1, "continuity": {"status": "clean"}}}
    result = _status(monkeypatch, {"target_words": 800_000}, [chapter])
    assert result["generation_percent"] < 1
    assert result["progress_basis"] == "words"
    assert result["ready_for_release"] is False


def test_missing_target_returns_unknown_instead_of_100(monkeypatch):
    result = _status(monkeypatch, {}, [{"status": "reviewed", "body": "正文", "meta": {}}])
    assert result["generation_percent"] is None
    assert result["completion_percent"] is None
    assert result["target_missing"] is True


def test_review_and_continuity_are_separate_release_gates(monkeypatch):
    chapters = [
        {"status": "reviewed", "body": "正文", "meta": {"continuity": {"status": "flagged"}}},
        {"status": "draft", "body": "正文", "meta": {"continuity": {"status": "unchecked"}}},
    ]
    result = _status(monkeypatch, {"target_chapters": 2}, chapters)
    assert result["generation_percent"] == 100
    assert result["review_percent"] == 50
    assert result["continuity_flagged"] == 1
    assert result["continuity_unchecked"] == 1
    assert result["ready_for_release"] is False
    assert result["quality_warnings"]
