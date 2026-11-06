from yai_scout.retrieval.quality import classify_source, domain_of


def test_domain_of_strips_www():
    assert domain_of("https://www.reuters.com/world/x") == "reuters.com"


def test_classify_tiers():
    assert classify_source("https://www.whitehouse.gov/briefing/")[0] == 1
    assert classify_source("https://arxiv.org/abs/2401.00001")[0] == 1
    assert classify_source("https://www.reuters.com/tech/")[0] == 2
    assert classify_source("https://pypi.org/project/pandas/#history")[0] == 2
    assert classify_source("https://www.reddit.com/r/x")[0] == 4
    assert classify_source("https://random-blog.example/page")[0] == 3
