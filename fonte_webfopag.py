import os
import ssl
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Sequence

import requests
import urllib3
from requests.adapters import HTTPAdapter

from .config import carregar_ambiente

# O certificado não valida e a verificação já é desligada no adaptador; sem isto
# cada requisição polui o log com o mesmo aviso.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL_BASE = "https://webapi.webfopag.com.br"
EMPREGADORES = (8, 7)
TIMEOUT_EM_SEGUNDOS = 90
BUSCAS_SIMULTANEAS = 8


class ErroDoWebfopag(Exception):
    pass


@dataclass(frozen=True)
class GestorDoEmpregado:
    nome: str
    cpf: str


class _AdaptadorSemVerificacao(HTTPAdapter):
    # O certificado do Webfopag não valida na cadeia padrão; é o mesmo
    # tratamento que o provider do programa de colaboradores já faz.
    def init_poolmanager(self, *args, **kwargs):
        contexto = ssl.create_default_context()
        contexto.check_hostname = False
        contexto.verify_mode = ssl.CERT_NONE
        kwargs["ssl_context"] = contexto
        return super().init_poolmanager(*args, **kwargs)


def _so_digitos(valor) -> str:
    return "".join(filter(str.isdigit, str(valor or "")))


def _cpf(valor) -> str:
    # A API devolve CPF como float (15189025969.0), então formatar direto perde
    # o zero à esquerda e vira notação científica em CPF curto.
    if valor is None:
        return ""
    return str(int(float(valor))).zfill(11)


class RepositorioDeGestores:
    """Hierarquia de chefia do Webfopag: quem é o gestor de cada pessoa.

    É o vínculo cadastrado, não inferência por loja — por isso cobre também as
    unidades que não têm gerente de loja no cadastro do RH.
    """

    def __init__(self, cs: str, cpf_usuario: str, usuario: str, senha: str):
        self._cs = cs
        self._sessao = requests.Session()
        self._sessao.mount("https://", _AdaptadorSemVerificacao())
        self._token = self._autenticar(cpf_usuario, usuario, senha)
        self._cnpj_por_cpf: dict[str, str] | None = None

    def buscar_por_cpf(self, cpfs: Sequence[str]) -> dict[str, GestorDoEmpregado]:
        if not cpfs:
            return {}

        procurados = list(dict.fromkeys(cpfs))
        with ThreadPoolExecutor(max_workers=BUSCAS_SIMULTANEAS) as executor:
            achados = executor.map(self._gestor_de, procurados)
        return {cpf: gestor for cpf, gestor in zip(procurados, achados) if gestor}

    def _gestor_de(self, cpf: str) -> GestorDoEmpregado | None:
        cnpj = self._cnpj_do_empregado(cpf)
        if not cnpj:
            return None

        resposta = self._sessao.get(
            f"{URL_BASE}/api/Supervisor/CarregarHierarquiaEmpregado",
            headers=self._cabecalho(),
            params={"cs": self._cs, "numCPF": cpf, "numCNPJ": cnpj},
            verify=False,
            timeout=TIMEOUT_EM_SEGUNDOS,
        )
        if resposta.status_code != 200:
            return None

        # A resposta é uma árvore: o primeiro `Supervisor` é o gestor direto, o
        # seguinte já é o regional.
        supervisor = (resposta.json() or {}).get("Supervisor") or {}
        nome = (supervisor.get("Nome") or "").strip()
        return GestorDoEmpregado(nome, _cpf(supervisor.get("CPF"))) if nome else None

    def _cnpj_do_empregado(self, cpf: str) -> str:
        if self._cnpj_por_cpf is None:
            self._cnpj_por_cpf = self._carregar_cnpjs()
        return self._cnpj_por_cpf.get(cpf, "")

    def _carregar_cnpjs(self) -> dict[str, str]:
        # A hierarquia exige o CNPJ do empregador junto do CPF, e ele só vem na
        # listagem de empregados.
        por_cpf: dict[str, str] = {}
        for empregador in EMPREGADORES:
            resposta = self._sessao.post(
                f"{URL_BASE}/api/Empregado",
                headers=self._cabecalho(),
                params={"cs": self._cs},
                json={"IDEmpregador": empregador, "FlagEmpregadoInativo": False},
                verify=False,
                timeout=TIMEOUT_EM_SEGUNDOS,
            )
            if resposta.status_code != 200:
                continue
            for empregado in resposta.json():
                cpf = _cpf(empregado.get("CPF"))
                if cpf:
                    por_cpf.setdefault(cpf, _so_digitos(empregado.get("CNPJ")))
        return por_cpf

    def _cabecalho(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "CS": self._cs,
        }

    def _autenticar(self, cpf_usuario: str, usuario: str, senha: str) -> str:
        resposta = self._sessao.post(
            f"{URL_BASE}/token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "CpfUsuario": cpf_usuario,
                "Cs": self._cs,
            },
            data={"grant_type": "password", "username": usuario, "password": senha},
            verify=False,
            timeout=TIMEOUT_EM_SEGUNDOS,
        )
        if resposta.status_code != 200:
            raise ErroDoWebfopag(
                f"Autenticação recusada: HTTP {resposta.status_code} — {resposta.text[:200]!r}"
            )
        token = resposta.json().get("access_token")
        if not token:
            raise ErroDoWebfopag("Autenticação sem access_token na resposta")
        return token


def criar_repositorio_de_gestores() -> RepositorioDeGestores:
    carregar_ambiente()
    faltando = [
        nome
        for nome in ("WEBFOPAG_CS", "WEBFOPAG_CPF_USUARIO", "WEBFOPAG_USERNAME", "WEBFOPAG_PASSWORD")
        if not os.getenv(nome)
    ]
    if faltando:
        raise ErroDoWebfopag(f"Variáveis ausentes no .env: {', '.join(faltando)}")

    return RepositorioDeGestores(
        cs=os.getenv("WEBFOPAG_CS"),
        cpf_usuario=os.getenv("WEBFOPAG_CPF_USUARIO"),
        usuario=os.getenv("WEBFOPAG_USERNAME"),
        senha=os.getenv("WEBFOPAG_PASSWORD"),
    )
