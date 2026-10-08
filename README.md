# Gerenciador de acessos — RH

Automatiza a abertura e o acompanhamento de chamados de acesso no service desk da
empresa: pede a **criação** dos acessos de quem foi admitido e a **inativação** dos
de quem foi desligado, sem intervenção manual do RH.

Antes: alguém do RH abria cada chamado à mão e conferia o status um por um.
Ex-funcionário com acesso ativo era achado por acaso.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-2_bases-blue)
![peewee](https://img.shields.io/badge/ORM-peewee-blue)

---

## O que faz

| Rotina | Dispara | Resultado |
|---|---|---|
| **Admissão** | admitido nos últimos 2 dias | chamado "Cadastro de Cód Zanthus" com os gestores em cópia |
| **Rescisão** | rescisão confirmada, a partir do dia seguinte | chamado "Inativar acessos" |
| **Acompanhamento** | chamados em aberto | grava o status até o chamado sair de circulação |

Uma execução por dia. O agendamento é externo — a rotina não agenda nada.

```bash
python executar.py              # abre os chamados e grava
python executar.py --simular    # mostra o que seria enviado, sem efeito algum
```

---

## Arquitetura

```
executar.py                       ponto de entrada (CLI)
└── rotina_de_acessos.py          orquestra admissão + acompanhamento
    rotina_de_rescisoes.py        orquestra rescisão
    ├── gestores.py               decide quem é o gestor (lógica pura, sem I/O)
    ├── chamado_acessos.py        monta título e corpo HTML
    │   chamado_rescisoes.py
    ├── fonte_rh.py               adapter: base do RH
    ├── fonte_mpcore.py           adapter: base do recrutamento
    ├── acelerato.py              adapter: API do service desk
    └── models.py / repository.py persistência (peewee)
```

Separação por fonte de dados: cada adapter lê **uma** base. O `gestores.py` não
abre conexão nem chama API — recebe o que as fontes trouxeram e decide. As
dependências entram pelo construtor; quem lê o `.env` é a fábrica, então importar
módulo não abre conexão.

**1.327 linhas, 13 módulos.**

---

## De onde vêm os dados

Nenhum arquivo de configuração de dados — tudo de banco ou API.

| Informação | Fonte |
|---|---|
| Admitidos e rescindidos | base do RH: `mov_funcao` + `cad_funcionario` + `cad_funcao` |
| Supervisor do admitido | base de recrutamento: vaga do candidato, ligada por CPF |
| E-mail do gestor | base de recrutamento: usuário solicitante da vaga |
| E-mail do gestor (fallback) | base de recrutamento: perfil de acesso da loja |
| `usuarioKey` do seguidor | API do service desk, resolvida pelo e-mail |

O gestor é resolvido por uma cascata de 4 fontes, da mais específica à mais
genérica. **O e-mail nunca é deduzido do nome** — essa tentativa foi medida e
errou 3 em 10, porque há gestor com e-mail pessoal e outro em domínio diferente.

---

## Decisões técnicas

As que custaram mais investigação e as que evitam erro silencioso.

**Idempotência por pessoa, não por data do chamado.**
A chave é `cpf + data_do_evento`. Cobre três casos que a data do chamado não
cobria: rodar duas vezes no mesmo dia, ficar um dia sem rodar, e admissão com data
futura — que existe na base e, sem isso, era pedida de novo todo dia até a data
chegar.

**O chamado de rescisão só sai no dia seguinte ao desligamento.**
`data_rescisao <= current_date - 1`. Sem esse limite, o acesso cairia com a pessoa
ainda trabalhando.

**Erro de API mantém o chamado em acompanhamento.**
Só conclusão, lixeira, arquivamento, mesclagem ou 404 encerram. Tratar erro de
servidor como conclusão largaria um chamado que a TI nunca atendeu.

**Deduplicação por CPF na origem.**
Quem foi transferido tem uma linha por loja na base — até cinco para a mesma
pessoa e a mesma data. Sem `DISTINCT ON (cpf)`, saía repetida no chamado.

**Modo simulação.**
Criado depois de um chamado duplicado aberto por acidente ao usar o ponto de
entrada real como teste. Faz tudo menos abrir e gravar.

**Migração automática de schema.**
`CREATE TABLE IF NOT EXISTS` não altera tabela existente, então as colunas são
conferidas à parte e a nova é preenchida com o default — o deploy não exige
migração manual.

---

## Particularidades da API

Comportamentos descobertos por engenharia reversa, ausentes da documentação.

| Comportamento | Consequência |
|---|---|
| Seguidor só entra por `usuarioKey`; por e-mail devolve `500` mesmo com usuário existente | o `usuarioKey` é resolvido pelo e-mail antes de enviar |
| `GET /usuarios` ignora o parâmetro `filtro` e devolve sempre os mesmos 10 | os campos do filtro vão achatados na query |
| A API adiciona a conta de integração e o solicitante como seguidores; repetir um deles devolve `500` | essas chaves são descartadas antes do envio |
| Chamado inexistente devolve `404`, não corpo vazio | só o `404` encerra o acompanhamento |
| `kanbanStatus.fim` indica etapa final | mais confiável que comparar o id da etapa, que varia por quadro |

---

## Tabelas de controle

Criadas e migradas automaticamente na primeira execução.

| Tabela | Chave | Para que serve |
|---|---|---|
| `cham_admitidos` | `chamado_id` | status de cada chamado, com `tipo` (admissão/rescisão) |
| `cham_admitidos_acesso` | `cpf + data_admissao` | quem já teve acesso pedido |
| `cham_rescindidos_acesso` | `cpf + data_rescisao` | quem já teve inativação pedida |

Os dois tipos de chamado dividem a tabela de status porque o acompanhamento é
idêntico — um laço só cobre os dois.

---

## Configuração

Copie o `.env.example` para `.env` e preencha. O `.env` não vai para o repositório.

| Variável | |
|---|---|
| `ACELERATO_URL_BASE` | instância do service desk |
| `EMAIL_ACELERATO` / `TOKEN_ACELERATO` | conta e token da API |
| `ACELERATO_EMAIL_SOLICITANTE` | quem assina os chamados |
| `ACELERATO_CATEGORIA_KEY` | categoria do chamado de admissão |
| `ACELERATO_CATEGORIA_KEY_RESCISAO` | categoria do chamado de rescisão |
| `ACELERATO_SEGUIDORES_FIXOS` | quem entra em cópia sempre, separado por vírgula |
| `DB_*` / `RH_FONTE_DB_*` | base do RH |
| `MPCORE_DB_*` | base de recrutamento |

```bash
pip install -r requirements.txt
```

---

## Limitações conhecidas

- Unidade sem perfil de acesso cadastrado na base de recrutamento sai sem gestor em
  cópia. É cadastro faltando, não código.
- Loja sem gerente ativo na base do RH sai sem supervisor na tabela.
- Gestor sem conta no service desk aparece na tabela, mas não entra em cópia.
- A janela de 2 dias não alcança desligamento antigo; recuperar atraso exige rodar
  uma vez com janela maior.
