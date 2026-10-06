from dataclasses import dataclass
from datetime import date
from typing import Sequence

CARGOS_DE_CHEFIA = ("gerente%", "supervisor%", "lider%", "%coordenador%")

CONSULTA_DE_ADMITIDOS = """
    SELECT f.cpf, mf.loja, f.nome_funcionario, cf.nome_funcao, mf.data_admissao::date
    FROM mov_funcao mf
    JOIN cad_funcionario f ON f.id_funcionario = mf.id_funcionario
    JOIN cad_funcao cf     ON cf.id_funcao     = mf.id_funcao
    WHERE mf.status IS TRUE
      AND mf.data_admissao >= current_date - %s
    ORDER BY mf.data_admissao DESC, f.nome_funcionario
"""

CONSULTA_DE_CHEFIA = """
    SELECT mf.loja, f.cpf, f.nome_funcionario, cf.nome_funcao
    FROM mov_funcao mf
    JOIN cad_funcionario f ON f.id_funcionario = mf.id_funcionario
    JOIN cad_funcao cf     ON cf.id_funcao = mf.id_funcao
    WHERE mf.status IS TRUE
      AND mf.loja = ANY(%s)
      AND cf.nome_funcao ILIKE ANY(%s)
"""


def formatar_cpf(cpf: str) -> str:
    digitos = "".join(filter(str.isdigit, str(cpf))).zfill(11)
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


@dataclass(frozen=True)
class Admitido:
    filial: str
    nome: str
    cpf: str
    funcao: str
    data_admissao: date
    loja: int = 0
    supervisor: str = ""

    @property
    def celulas(self) -> tuple[str, ...]:
        return (
            self.filial,
            self.nome.title(),
            formatar_cpf(self.cpf),
            self.funcao.capitalize(),
            self.data_admissao.strftime("%d/%m/%Y"),
            self.supervisor,
        )


@dataclass(frozen=True)
class Chefe:
    cpf: str
    nome: str
    cargo: str


class RepositorioDeAdmitidos:
    def __init__(self, banco):
        self._banco = banco

    def buscar_recentes(self, dias: int = 2) -> list[Admitido]:
        cursor = self._banco.execute_sql(CONSULTA_DE_ADMITIDOS, (dias,))
        return [
            Admitido(
                filial=f"Loja {loja}",
                nome=nome,
                cpf=cpf,
                funcao=funcao,
                data_admissao=data_admissao,
                loja=loja,
            )
            for cpf, loja, nome, funcao, data_admissao in cursor.fetchall()
        ]


class RepositorioDeChefia:
    def __init__(self, banco):
        self._banco = banco

    def buscar_por_loja(self, lojas: Sequence[int]) -> dict[int, list[Chefe]]:
        if not lojas:
            return {}

        cursor = self._banco.execute_sql(
            CONSULTA_DE_CHEFIA, (list(set(lojas)), list(CARGOS_DE_CHEFIA))
        )
        por_loja: dict[int, list[Chefe]] = {}
        for loja, cpf, nome, cargo in cursor.fetchall():
            por_loja.setdefault(loja, []).append(Chefe(cpf, nome.title(), cargo))
        return por_loja
