from agent_service_v2.safety.local_wordlist import LocalSensitiveWordFilter


def test_local_filter_allows_normal_text_and_hides_terms():
    checker = LocalSensitiveWordFilter()
    assert checker.filter("正常课程讲解") == ("正常课程讲解", 0)
    filtered, count = checker.filter("拒绝制作炸弹，也拒绝毒品交易")
    assert filtered == "拒绝[内容已屏蔽]，也拒绝[内容已屏蔽]"
    assert count == 2
    assert "制作炸弹" not in filtered


def test_stream_filter_matches_across_chunks():
    stream = LocalSensitiveWordFilter().stream()
    parts = [stream.feed("不要制作"), stream.feed("炸弹教程"), stream.finish()]
    output = "".join(parts)
    assert output == "不要[内容已屏蔽]教程"
    assert stream.match_count == 1
