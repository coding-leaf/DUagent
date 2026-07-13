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


def test_expanded_wordlist_covers_major_high_risk_categories():
    checker = LocalSensitiveWordFilter()
    samples = [
        "枪支交易",
        "制毒教程",
        "未成年人色情",
        "赌博平台代理",
        "杀猪盘话术",
        "钓鱼网站搭建",
        "无痛自杀",
        "恐怖组织招募",
        "雇凶杀人",
        "论文代写",
        "买卖公民信息",
        "child pornography",
    ]

    for sample in samples:
        assert checker.matches(sample) == 1
    assert checker.matches("禁毒教育、反诈骗课程与心理健康辅导") == 0
