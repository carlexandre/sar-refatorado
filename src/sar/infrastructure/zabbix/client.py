import requests
import time
import logging
from pyzabbix import ZabbixAPI
from sar.domain.errors import ConfigurationError, IntegrationError


class ZabbixGateway:
    def __init__(self, settings, secrets):
        # pyzabbix DEBUG records include the login payload; never allow that diagnostic channel.
        logging.getLogger("pyzabbix.api").disabled = True
        self.settings = settings
        self.secrets = secrets
        self._api = None
        self._session = None

    def _connect(self):
        if self._api is not None:
            return self._api
        if not self.settings.zabbix_url:
            raise ConfigurationError("Configure a conexão HTTPS com o Zabbix.")
        session = requests.Session()
        session.verify = self.settings.ca_bundle or True
        token = self.secrets.get("zabbix-token")
        user, password = (
            (None, None) if token else (self.secrets.get("zabbix-user"), self.secrets.get("zabbix-password"))
        )
        if not token and not (user and password):
            session.close()
            raise ConfigurationError("Credenciais de execução do Zabbix não provisionadas.")
        try:
            api = ZabbixAPI(self.settings.zabbix_url, session=session, timeout=self.settings.timeout)
            if token:
                api.login(api_token=token)
            else:
                api.login(user, password)
            self._api, self._session = api, session
            return api
        except Exception:
            session.close()
            raise IntegrationError("Não foi possível autenticar no Zabbix com TLS válido.") from None

    def _get(self, resource, **parameters):
        api = self._connect()
        for attempt in range(2):
            try:
                return getattr(api, resource).get(**parameters)
            except requests.exceptions.SSLError:
                break
            except (requests.ConnectionError, requests.Timeout):
                if attempt == 0:
                    time.sleep(0.5)
                    continue
            except Exception:
                break
        raise IntegrationError(
            "Falha na consulta ao Zabbix. Verifique o serviço e a configuração TLS."
        ) from None

    def hosts(self):
        return self._get("host", output=["hostid", "name"], sortfield="name")

    def items(self, host_id):
        return self._get(
            "item",
            hostids=host_id,
            output=["itemid", "name", "key_"],
            search={"name": "Interface"},
            sortfield="name",
        )

    def history(self, item_id, start, end):
        return self._get(
            "history", itemids=[item_id], time_from=start, time_till=end, output="extend", history=3
        )

    def trends(self, item_id, start, end):
        return self._get(
            "trend",
            itemids=[item_id],
            time_from=start,
            time_till=end,
            output=["clock", "value_avg", "value_max"],
        )

    def events(self, host_id, start, end):
        return self._get(
            "event",
            hostids=[host_id],
            time_from=start,
            time_till=end,
            output=["eventid", "name", "clock", "r_eventid"],
            value=1,
            sortfield="clock",
        )

    def recoveries(self, ids):
        return self._get("event", eventids=ids, output=["eventid", "clock"]) if ids else []

    def close(self):
        if self._session:
            self._session.close()
        self._session = self._api = None
