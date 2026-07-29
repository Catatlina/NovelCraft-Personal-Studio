"""V3 §12 ⑪ 场景层：确定性与持久化边界测试（不依赖真实 AI）。"""
from app.services import scene_director
from app.services.scene_director import normalize_scene, persist_scenes, split_scenes


def test_split_scenes_empty():
    assert split_scenes("") == []
    assert split_scenes("   \n  ") == []


def test_split_scenes_by_blank_lines():
    text = "第一段场景内容。\n\n第二段场景内容。\n\n第三段场景内容。"
    scenes = split_scenes(text)
    assert len(scenes) == 3
    assert "第一段" in scenes[0]


def test_split_scenes_by_separator_line():
    text = "场景A内容。\n——\n场景B内容。\n***\n场景C内容。"
    scenes = split_scenes(text)
    assert len(scenes) == 3
    assert scenes[0] == "场景A内容。"
    assert scenes[2] == "场景C内容。"


def test_split_scenes_ignores_leading_trailing_separators():
    text = "——\n场景A内容。\n☆☆\n场景B内容。\n——\n"
    scenes = split_scenes(text)
    assert len(scenes) == 2


def test_normalize_scene_defaults():
    sc = normalize_scene({}, 3)
    assert sc["title"] == "场景3"
    assert sc["beat"] == "发展"


def test_normalize_scene_invalid_beat_falls_back():
    sc = normalize_scene({"title": "对决", "beat": "奇怪节拍", "goal": "决出胜负", "setting": "山顶", "pov": "主角"}, 1)
    assert sc["beat"] == "发展"  # 非法 beat 降级
    assert sc["title"] == "对决"
    assert sc["goal"] == "决出胜负"


def test_normalize_scene_keeps_valid_beat():
    sc = normalize_scene({"title": "反转", "beat": "转折", "goal": "g", "setting": "s", "pov": "p"}, 2)
    assert sc["beat"] == "转折"


def test_persist_scenes_commits_the_real_transaction(monkeypatch):
    class FakeDb:
        def __init__(self):
            self.statements = []
            self.committed = False
            self.closed = False

        def execute(self, sql, params):
            self.statements.append((sql, params))
            return self

        def commit(self):
            self.committed = True

        def close(self):
            self.closed = True

    db = FakeDb()
    monkeypatch.setattr(scene_director, "connect", lambda: db)

    count = persist_scenes(
        "chapter-1",
        "project-1",
        [{"title": "雨夜来客", "beat": "转折", "goal": "交付线索", "setting": "旧巷", "pov": "主角"}],
    )

    assert count == 1
    assert len(db.statements) == 2
    assert db.committed is True
    assert db.closed is True
