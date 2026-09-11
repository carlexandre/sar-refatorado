from unittest.mock import Mock
import logging
import os
import pytest
import requests
from sar.config.settings import Settings
from sar.domain.errors import ConfigurationError, IntegrationError
from sar.infrastructure.secrets.runtime_credentials import RuntimeCredentials
from sar.infrastructure.zabbix.client import ZabbixGateway


def test_missing_certificate_fails(tmp_path):
    with pytest.raises(ConfigurationError):
        Settings(tmp_path, ca_bundle=str(tmp_path / "missing.crt"))
    with pytest.raises(ConfigurationError):
        Settings(tmp_path, zabbix_url="http://example.org")
    with pytest.raises(ConfigurationError):
        Settings(tmp_path, zabbix_url="https://example.org?password=secret")


def test_credentials_not_loaded_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ZABBIX_PASSWORD", "should-not-be-used")
    assert RuntimeCredentials(None).get("zabbix-password") is None
    with pytest.raises(ConfigurationError):
        RuntimeCredentials(tmp_path).get("../password")


def test_runtime_credential_permissions(tmp_path):
    path = tmp_path / "zabbix-token"
    path.write_text("synthetic-token")
    if os.name == "posix":
        path.chmod(0o644)
        with pytest.raises(ConfigurationError):
            RuntimeCredentials(tmp_path).get("zabbix-token")
        path.chmod(0o600)
    assert RuntimeCredentials(tmp_path).get("zabbix-token") == "synthetic-token"


def test_zabbix_tls_and_no_raw_debug(monkeypatch, tmp_path):
    import sar.infrastructure.zabbix.client as module

    secrets = Mock()
    secrets.get.return_value = "synthetic-token"
    api = Mock()
    factory = Mock(return_value=api)
    monkeypatch.setattr(module, "ZabbixAPI", factory)
    gateway = ZabbixGateway(Settings(tmp_path, zabbix_url="https://example.org"), secrets)
    gateway.hosts()
    assert factory.call_args.kwargs["session"].verify is True
    assert factory.call_args.kwargs["timeout"] == 30
    assert logging.getLogger("pyzabbix.api").disabled
    api.login.assert_called_once_with(api_token="synthetic-token")
    gateway.close()


def test_zabbix_tls_failure_never_retried(monkeypatch, tmp_path):
    gateway = ZabbixGateway(Settings(tmp_path, zabbix_url="https://example.org"), Mock())
    gateway._api = Mock()
    gateway._api.host.get.side_effect = requests.exceptions.SSLError("private response")
    with pytest.raises(IntegrationError) as error:
        gateway.hosts()
    assert gateway._api.host.get.call_count == 1
    assert "private response" not in str(error.value)
