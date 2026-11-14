"""Acesso HTTP educado: identifica o robô, repete em caso de erro e limita o ritmo."""
import sys
import threading
import time

import requests

AGENTE = "RadarCidades/2.0 (monitoramento cidadao de dados publicos)"


class Cliente:
    def __init__(self, pausa=0.15, tentativas=4, tempo=60):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = AGENTE
        ad = requests.adapters.HTTPAdapter(pool_connections=8, pool_maxsize=8)
        self.s.mount("https://", ad)
        self.s.mount("http://", ad)
        self.pausa, self.tentativas, self.tempo = pausa, tentativas, tempo
        self.pedidos = 0
        self._trava = threading.Lock()

    def _get(self, url, params=None, ok404=False):
        for i in range(self.tentativas):
            try:
                r = self.s.get(url, params=params, timeout=self.tempo)
                with self._trava:
                    self.pedidos += 1
                if r.status_code == 404 and ok404:
                    return None
                r.raise_for_status()
                time.sleep(self.pausa)
                return r
            except requests.RequestException as e:
                if i == self.tentativas - 1:
                    raise RuntimeError(f"falhou: {url} ({e})") from e
                print(f"  erro em {url} ({e}); tentando de novo", file=sys.stderr)
                time.sleep(3 * (i + 1))

    def html(self, url, params=None):
        r = self._get(url, params)
        r.encoding = "utf-8"
        return r.text

    def json(self, url, params=None):
        return self._get(url, params).json()

    def bytes(self, url, ok404=True):
        r = self._get(url, ok404=ok404)
        return r.content if r is not None else None
