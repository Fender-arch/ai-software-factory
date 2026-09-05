from integrations.outbound_proxy import http_proxy_url


def test_http_proxy_url_prefers_https_proxy():
    assert (
        http_proxy_url(
            {
                "HTTPS_PROXY": "http://egress:8888",
                "HTTP_PROXY": "http://other:1",
            }
        )
        == "http://egress:8888"
    )


def test_http_proxy_url_empty_is_none():
    assert http_proxy_url({"HTTPS_PROXY": "  ", "HTTP_PROXY": ""}) is None


def test_http_proxy_url_all_proxy_fallback():
    assert http_proxy_url({"ALL_PROXY": "http://egress:8888"}) == "http://egress:8888"
