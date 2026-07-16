import importlib
import os

import pytest

import config.credentials as credentials_module
import runtime.llm_client as llm_client_module


@pytest.fixture(autouse=True)
def isolated_config_dir(tmp_path, monkeypatch):
    """Every test gets its own throwaway credentials dir so a real /connect on the
    developer's machine (~/.autonomous_runtime) never leaks into test assertions."""
    monkeypatch.setenv("RUNTIME_CONFIG_DIR", str(tmp_path / "autonomous_runtime_test"))
    importlib.reload(credentials_module)
    importlib.reload(llm_client_module)
    yield
    importlib.reload(credentials_module)
    importlib.reload(llm_client_module)


def _clear_provider_env(monkeypatch):
    for key in ["LLM_PROVIDER", "LLM_MODEL", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "OPENROUTER_BASE_URL"]:
        monkeypatch.delenv(key, raising=False)


def test_defaults_to_anthropic(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    cfg = llm_client_module._resolve_config()
    assert cfg.provider == "anthropic"
    assert cfg.model == "claude-sonnet-4-6"
    assert cfg.api_key == "sk-ant-test"


def test_missing_key_raises(monkeypatch):
    _clear_provider_env(monkeypatch)
    with pytest.raises(RuntimeError):
        llm_client_module._resolve_config(provider="anthropic")


def test_openai_provider_via_env(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-oa-test")
    cfg = llm_client_module._resolve_config()
    assert cfg.provider == "openai"
    assert cfg.model == "gpt-4.1"
    assert cfg.api_key == "sk-oa-test"


def test_openrouter_provider_explicit_arg_overrides_env(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "openai")  # should be overridden by explicit arg
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    cfg = llm_client_module._resolve_config(provider="openrouter")
    assert cfg.provider == "openrouter"
    assert cfg.model == "anthropic/claude-sonnet-4.6"
    assert cfg.base_url == "https://openrouter.ai/api/v1"


def test_model_override(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    cfg = llm_client_module._resolve_config(model="claude-opus-4-8")
    assert cfg.model == "claude-opus-4-8"


def test_unknown_provider_raises(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    with pytest.raises(ValueError):
        llm_client_module._resolve_config(provider="not-a-real-provider")


def test_shared_lazy_client_does_not_resolve_until_complete_called(monkeypatch):
    _clear_provider_env(monkeypatch)
    # No API key set at all - constructing the lazy client must not raise.
    client = llm_client_module.SharedLazyLLMClient(provider="anthropic")
    assert client._delegate is None
    with pytest.raises(RuntimeError):
        client.complete("system", "user")


def test_connect_saves_and_resolves_without_env_vars(monkeypatch):
    _clear_provider_env(monkeypatch)
    credentials_module.save_connection("openrouter", "sk-or-saved", model="anthropic/claude-sonnet-4.6")
    cfg = llm_client_module._resolve_config()
    assert cfg.provider == "openrouter"
    assert cfg.api_key == "sk-or-saved"
    assert cfg.model == "anthropic/claude-sonnet-4.6"


def test_env_var_overrides_saved_connection(monkeypatch):
    _clear_provider_env(monkeypatch)
    credentials_module.save_connection("openrouter", "sk-or-saved")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    cfg = llm_client_module._resolve_config()
    assert cfg.provider == "anthropic"
    assert cfg.api_key == "sk-ant-env"


def test_disconnect_clears_saved_connection(monkeypatch):
    _clear_provider_env(monkeypatch)
    credentials_module.save_connection("openai", "sk-oa-saved")
    assert credentials_module.load_credentials().get("provider") == "openai"
    credentials_module.clear_connection()
    assert credentials_module.load_credentials() == {}
    with pytest.raises(RuntimeError):
        llm_client_module._resolve_config()


def test_credentials_file_permissions_are_owner_only(monkeypatch):
    _clear_provider_env(monkeypatch)
    credentials_module.save_connection("anthropic", "sk-ant-saved")
    mode = oct(credentials_module.CREDENTIALS_PATH.stat().st_mode)[-3:]
    assert mode == "600"
