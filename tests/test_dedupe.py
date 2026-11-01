from yai_scout.retrieval.dedupe import canonicalize_url, dedupe_sources


def test_canonicalize_strips_tracking_and_www():
    url = "https://www.Example.com/a/b/?utm_source=x&id=2&fbclid=zz#frag"
    assert canonicalize_url(url) == "https://example.com/a/b?id=2"


def test_canonicalize_keeps_root_and_port():
    assert canonicalize_url("http://example.com:8080/") == "http://example.com:8080/"
    assert canonicalize_url("https://example.com/") == "https://example.com/"


def test_dedupe_sources_by_canonical_url():
    items = [
        {"canonical_url": "https://a.com/x"},
        {"canonical_url": "https://a.com/x"},
        {"canonical_url": "https://b.com/y"},
    ]
    assert len(dedupe_sources(items, key=lambda i: i["canonical_url"])) == 2
