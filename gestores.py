import unicodedata
from dataclasses import dataclass, replace
from typing import Callable, Iterable, Sequence

from .fonte_mpcore import VagaDoAdmitido
from .fonte_rh import Chefe

CARGO_DE_GERENTE = "gerente de loja"
PALAVRAS_IGNORADAS = {"de", "da", "do", "dos", "das", "e"}


def _tokens(texto: str) -> set[str]:
    sem_acento = (
        unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    )
    partes = sem_acento.lower().replace(".", " ").replace("@", " ").split()
    return {parte for parte in partes if parte not in PALAVRAS_IGNORADAS}


@dataclass(frozen=True)
class Gestor:
    nome: str
    cargo: str
    loja: int
    email: str = ""
    origem: str = ""
    chave_no_acelerato: int = 0

    @property
    def esta_completo(self) -> bool:
        return bool(self.nome and self.chave_no_acelerato)


def resolver_gestor(
    loja: int,
    vaga: VagaDoAdmitido | None,
    chefia_da_loja: Sequence[Chefe],
    emails_da_loja: Sequence[str] = (),
    buscar_chave: Callable[[str], int] | None = None,
) -> Gestor | None:
    gestor = _escolher(loja, vaga, chefia_da_loja, emails_da_loja)
    if gestor is None:
        return None
    if buscar_chave is None or not gestor.email:
        return gestor
    return replace(gestor, chave_no_acelerato=buscar_chave(gestor.email))


def _escolher(
    loja: int,
    vaga: VagaDoAdmitido | None,
    chefia_da_loja: Sequence[Chefe],
    emails_da_loja: Sequence[str],
) -> Gestor | None:
    if vaga is not None and vaga.tem_supervisor:
        chefe = _casar_pelo_nome(vaga.supervisor_informado, chefia_da_loja)
        if chefe is not None:
            # E-mail do próprio gestor antes do solicitante: quem abre a vaga às
            # vezes é o RH. Supervisor não tem perfil de acesso, só gerente.
            return Gestor(
                nome=chefe.nome,
                cargo=chefe.cargo,
                loja=loja,
                email=_email_do_chefe(chefe, emails_da_loja) or vaga.email_do_solicitante,
                origem="MPCore + chefia da loja",
            )
        return Gestor(
            nome=vaga.supervisor_informado.title(),
            cargo="",
            loja=loja,
            email=vaga.email_do_solicitante,
            origem="MPCore (nome não resolvido na chefia)",
        )

    gerente = _gerente_da_loja(chefia_da_loja)
    if gerente is None:
        return None

    if vaga is not None and vaga.email_do_solicitante:
        return Gestor(gerente.nome, gerente.cargo, loja,
                      vaga.email_do_solicitante, "MPCore (só solicitante)")

    return Gestor(
        nome=gerente.nome,
        cargo=gerente.cargo,
        loja=loja,
        email=_email_do_chefe(gerente, emails_da_loja),
        origem="gerente da loja + perfil de acesso do MPCore",
    )


def _email_do_chefe(chefe: Chefe, emails_da_loja: Sequence[str]) -> str:
    # Há loja com dois perfis de acesso: pegar o primeiro mandaria para a
    # pessoa errada, então empate devolve vazio.
    do_nome = _tokens(chefe.nome)
    casados = [email for email in emails_da_loja if _tokens(email.split("@")[0]) & do_nome]
    return casados[0] if len(casados) == 1 else ""


def _casar_pelo_nome(informado: str, chefia: Sequence[Chefe]) -> Chefe | None:
    # O MPCore guarda só o primeiro nome, em caixa variada: 'Ana', 'ana', 'ANA'.
    procurado = _tokens(informado)
    casados = [chefe for chefe in chefia if procurado & _tokens(chefe.nome)]
    return casados[0] if len(casados) == 1 else None


def _gerente_da_loja(chefia: Sequence[Chefe]) -> Chefe | None:
    gerentes = [chefe for chefe in chefia if chefe.cargo.startswith(CARGO_DE_GERENTE)]
    return gerentes[0] if len(gerentes) == 1 else None


def separar_sem_email(gestores: Iterable[Gestor]) -> list[Gestor]:
    return [gestor for gestor in gestores if not gestor.esta_completo]
