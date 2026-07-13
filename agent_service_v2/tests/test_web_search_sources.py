from agent_service_v2.runtime.web_search_sources import normalize_web_search_sources


def test_normalize_web_search_sources_accepts_result_envelope_and_safe_urls_only():
    sources = normalize_web_search_sources(
        {
            "results": [
                None,
                {"title": "Local", "url": "file:///etc/passwd"},
                {
                    "title": "Python",
                    "url": "https://docs.python.org/3/",
                    "description": "Python documentation",
                    "engine": "bing",
                },
            ]
        }
    )

    assert sources == [
        {
            "title": "Python",
            "url": "https://docs.python.org/3/",
            "snippet": "Python documentation",
            "source": "docs.python.org",
            "engine": "bing",
        }
    ]
