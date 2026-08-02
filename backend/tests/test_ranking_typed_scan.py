from app.api.v1.ranking import RankingScanRequest, _filter_scoped_items


def test_typed_scan_scope_is_explicit_and_traceable():
    scope = RankingScanRequest(
        leaderboard="newbook",
        gender="female",
        main_category="都市",
        sub_category="都市重生",
        limit=30,
    )
    assert scope.is_default is False
    assert scope.as_dict() == {
        "mode": "typed",
        "leaderboard": "newbook",
        "gender": "female",
        "main_category": "都市",
        "sub_category": "都市重生",
        "limit": 30,
    }


def test_typed_scan_filters_category_and_gender_without_guessing_missing_metadata():
    scope = RankingScanRequest(
        leaderboard="newbook",
        gender="female",
        main_category="都市",
        sub_category="都市重生",
        limit=30,
    )
    items = [
        {"source": "fanqie", "gender": "female", "category": "都市|都市重生", "title": "命中"},
        {"source": "fanqie", "gender": "male", "category": "都市|都市重生", "title": "性别不命中"},
        {"source": "fanqie", "gender": "female", "category": "玄幻|高武", "title": "分类不命中"},
    ]
    filtered, warning = _filter_scoped_items(items, scope)
    assert warning is None
    assert [item["title"] for item in filtered] == ["命中"]


def test_typed_scan_reports_data_sparse_when_gender_is_not_observable():
    scope = RankingScanRequest(gender="male")
    filtered, warning = _filter_scoped_items(
        [{"source": "qidian", "category": "都市|都市脑洞", "title": "没有性别证据"}],
        scope,
    )
    assert filtered == []
    assert warning and "数据稀疏" in warning
