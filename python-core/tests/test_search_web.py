from wiki_agent.search_web import SearchResult


def test_search_result_shape():
    result = SearchResult("标题", "https://example.com", "摘要")
    assert result.title == "标题"
    assert result.engine == ""
