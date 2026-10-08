import os
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

import requests
from requests.auth import HTTPBasicAuth

from .config import carregar_ambiente

TIMEOUT_EM_SEGUNDOS = 30
KANBAN_STATUS_KEY_CONCLUIDO = 15

# `suspenso` e `impedido` ficam fora de propósito: o chamado segue vivo, travado.
FLAGS_DE_SAIDA = ("lixeira", "arquivado", "mesclado", "alvoDeSpam")

# ChamadoAPIRepresentation traz os dois; a consulta devolve ticketKey.
CHAVES_DE_ID_NA_RESPOSTA = ("ticketKey", "id")


class ErroDoAcelerato(Exception):
    pass


class StatusChamado(str, Enum):
    ABERTO = "aberto"
    CONCLUIDO = "concluido"
    NAO_ENCONTRADO = "nao_encontrado"


@dataclass(frozen=True)
class Chamado:
    id: int
    status: StatusChamado
    descricao_do_status: str = ""

    @property
    def acompanhamento_encerrado(self) -> bool:
        return self.status is not StatusChamado.ABERTO


class AceleratoAPI:
    def __init__(
        self,
        email: str,
        token: str,
        email_solicitante: str,
        url_base: str,
        categoria_key: int = 0,
        categoria_key_rescisao: int = 0,
        chaves_automaticas: Sequence[int] = (),
        timeout_em_segundos: int = TIMEOUT_EM_SEGUNDOS,
    ):
        self._autenticacao = HTTPBasicAuth(email, token)
        self._email_solicitante = email_solicitante
        self._categoria_key = categoria_key
        self.categoria_key_rescisao = categoria_key_rescisao
        self._chaves_automaticas = set(chaves_automaticas)
        self._chave_por_email: dict[str, int] = {}
        self._url_base = url_base
        self._timeout_em_segundos = timeout_em_segundos

    def abrir_chamado(
        self,
        titulo: str,
        descricao: str,
        chaves_dos_seguidores: Sequence[int] = (),
        categoria_key: int | None = None,
    ) -> int:
        # Seguidor só entra por usuarioKey: `{"email": ...}` devolve 500, e
        # repetir um seguidor que o Acelerato já pôs também.
        payload = {
            "titulo": titulo,
            "descricao": descricao,
            "categoria": {"categoriaKey": categoria_key or self._categoria_key},
            "solicitante": {"email": self._email_solicitante},
        }
        seguidores = [
            {"usuarioKey": chave}
            for chave in dict.fromkeys(chaves_dos_seguidores)
            if chave and chave not in self._chaves_automaticas
        ]
        if seguidores:
            payload["seguidores"] = seguidores

        resposta = self._requisitar("POST", "/chamados", json=payload)

        if resposta.status_code not in (200, 201):
            raise ErroDoAcelerato(
                f"Abertura de chamado recusada: HTTP {resposta.status_code} — {resposta.text[:300]!r}"
            )
        return self._extrair_id(resposta)

    def ignorar_como_seguidores(self, chaves: Sequence[int]) -> None:
        self._chaves_automaticas.update(chave for chave in chaves if chave)

    def buscar_chave_do_usuario(self, email: str) -> int:
        # Os campos de FiltroUsuario vão achatados na query: passar `filtro=`
        # não filtra, devolve sempre os mesmos 10 usuários, calado.
        chave = self._chave_por_email.get(email.lower())
        if chave is not None:
            return chave

        self._chave_por_email[email.lower()] = 0
        resposta = self._requisitar("GET", "/usuarios", params={"email": email})
        if resposta.status_code != 200:
            return 0

        for usuario in self._ler_json_lista(resposta):
            if (usuario.get("email") or "").lower() == email.lower():
                self._chave_por_email[email.lower()] = usuario.get("usuarioKey") or 0
                break
        return self._chave_por_email[email.lower()]

    def consultar_chamado(self, chamado_id: int) -> Chamado:
        resposta = self._requisitar("GET", f"/v2/chamados/{chamado_id}")

        if resposta.status_code == 404:
            return Chamado(chamado_id, StatusChamado.NAO_ENCONTRADO)

        # Estourar mantém o chamado em acompanhamento: tratar erro de servidor
        # como excluído largaria um chamado que a TI nunca concluiu.
        if resposta.status_code != 200:
            raise ErroDoAcelerato(
                f"Consulta do chamado {chamado_id} falhou: HTTP {resposta.status_code} — {resposta.text[:300]!r}"
            )

        return self._converter_chamado(chamado_id, self._ler_json(resposta))

    def _converter_chamado(self, chamado_id: int, corpo: dict) -> Chamado:
        kanban = corpo.get("kanbanStatus") or {}

        # Cada quadro numera suas etapas, então a key 15 só vale no da Tecnologia;
        # `fim` é o status dizendo que é etapa final, cancelamento incluso.
        etapa_final = (
            kanban.get("fim") is True
            or kanban.get("kanbanStatusKey") == KANBAN_STATUS_KEY_CONCLUIDO
        )
        if etapa_final:
            # Antes das flags de saída: concluído e depois arquivado é concluído.
            return Chamado(
                id=chamado_id,
                status=StatusChamado.CONCLUIDO,
                descricao_do_status=kanban.get("descricao") or "",
            )

        fora_de_circulacao = next(
            (flag for flag in FLAGS_DE_SAIDA if corpo.get(flag) is True), ""
        )
        if fora_de_circulacao:
            return Chamado(
                chamado_id,
                StatusChamado.NAO_ENCONTRADO,
                descricao_do_status=fora_de_circulacao,
            )

        return Chamado(
            id=chamado_id,
            status=StatusChamado.ABERTO,
            descricao_do_status=kanban.get("descricao") or "",
        )

    def _extrair_id(self, resposta: requests.Response) -> int:
        corpo = self._ler_json(resposta)
        for chave in CHAVES_DE_ID_NA_RESPOSTA:
            if corpo.get(chave) is not None:
                return int(corpo[chave])
        raise ErroDoAcelerato(
            f"Chamado aberto, mas a resposta não trouxe o id em {CHAVES_DE_ID_NA_RESPOSTA}: {corpo}"
        )

    def _requisitar(self, metodo: str, caminho: str, **kwargs) -> requests.Response:
        try:
            return requests.request(
                metodo,
                self._url_base + caminho,
                auth=self._autenticacao,
                timeout=self._timeout_em_segundos,
                **kwargs,
            )
        except requests.RequestException as erro:
            raise ErroDoAcelerato(f"{metodo} {caminho} não completou: {erro}") from erro

    def _ler_json_lista(self, resposta: requests.Response) -> list[dict]:
        corpo = self._ler_json(resposta)
        return corpo if isinstance(corpo, list) else corpo.get("content", [])

    def _ler_json(self, resposta: requests.Response) -> dict:
        try:
            return resposta.json()
        except ValueError as erro:
            raise ErroDoAcelerato(
                f"Resposta não é JSON (HTTP {resposta.status_code}): {resposta.text[:300]!r}"
            ) from erro


def criar_cliente_acelerato() -> AceleratoAPI:
    carregar_ambiente()
    email = _ler_variavel("EMAIL_ACELERATO")
    solicitante = _ler_variavel("ACELERATO_EMAIL_SOLICITANTE")

    cliente = AceleratoAPI(
        email=email,
        token=_ler_variavel("TOKEN_ACELERATO"),
        email_solicitante=solicitante,
        url_base=_ler_variavel("ACELERATO_URL_BASE"),
        categoria_key=int(_ler_variavel("ACELERATO_CATEGORIA_KEY")),
        categoria_key_rescisao=int(_ler_variavel("ACELERATO_CATEGORIA_KEY_RESCISAO")),
    )
    cliente.ignorar_como_seguidores(
        [cliente.buscar_chave_do_usuario(email), cliente.buscar_chave_do_usuario(solicitante)]
    )
    return cliente


def _ler_variavel(nome: str) -> str:
    valor = os.getenv(nome)
    if not valor:
        raise ErroDoAcelerato(f"Variável {nome} ausente no .env")
    return valor

