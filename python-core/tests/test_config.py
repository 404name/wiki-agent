from wiki_agent import config


def test_public_config_hides_api_key(monkeypatch):
    monkeypatch.setattr(config, "LLM_API_KEY", "secret")
    public = config.public_config()
    assert public["llm_configured"] is True
    assert "secret" not in str(public)
