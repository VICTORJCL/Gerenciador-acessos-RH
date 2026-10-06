from dataclasses import dataclass
from typing import Sequence

SUPERVISOR_EM_BRANCO = {"", "-"}

CONSULTA_DE_VAGAS = """
    SELECT c.cpf, btrim(coalesce(v.supervisor, '')), coalesce(u.email, '')
    FROM rh_candidatovaga cv
    JOIN rh_candidato c       ON c.id = cv.candidato_id
    JOIN rh_solicitacaovaga v ON v.id = cv.vaga_id
    LEFT JOIN auth_user u     ON u.id = v.solicitante_id
    WHERE cv.etapa = 'ADMITIDO'
      AND regexp_replace(coalesce(c.cpf, ''), '\\D', '', 'g') = ANY(%s)
"""

CONSULTA_DE_EMAILS_DA_LOJA = """
    SELECT pl.lojabluesoft_id, u.email
    FROM acessos_perfilacesso p
    JOIN auth_user u                   ON u.id = p.usuario_id
    JOIN acessos_perfilacesso_lojas pl ON pl.perfilacesso_id = p.id
    WHERE p.escopo = 'LOJA'
      AND u.is_active
      AND btrim(coalesce(u.email, '')) <> ''
      AND pl.lojabluesoft_id = ANY(%s)
"""


@dataclass(frozen=True)
class VagaDoAdmitido:
    supervisor_informado: str
    email_do_solicitante: str

    @property
    def tem_supervisor(self) -> bool:
        return self.supervisor_informado.lower() not in SUPERVISOR_EM_BRANCO


class RepositorioDeVagas:
    def __init__(self, banco):
        self._banco = banco

    def buscar_por_cpf(self, cpfs: Sequence[str]) -> dict[str, VagaDoAdmitido]:
        if not cpfs:
            return {}

        cursor = self._banco.execute_sql(CONSULTA_DE_VAGAS, (list(cpfs),))
        return {
            cpf: VagaDoAdmitido(supervisor, email)
            for cpf, supervisor, email in cursor.fetchall()
        }


class RepositorioDeEmailsDaLoja:
    def __init__(self, banco_mpcore):
        self._banco = banco_mpcore

    def buscar_por_loja(self, lojas: Sequence[int]) -> dict[int, list[str]]:
        if not lojas:
            return {}

        cursor = self._banco.execute_sql(CONSULTA_DE_EMAILS_DA_LOJA, (list(set(lojas)),))
        por_loja: dict[int, list[str]] = {}
        for loja, email in cursor.fetchall():
            por_loja.setdefault(loja, []).append(email.strip())
        return por_loja
