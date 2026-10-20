# Gerenciador de acessos — RH

Automatiza a abertura e o acompanhamento de chamados de acesso no service desk da
empresa: pede a **criação** dos acessos de quem foi admitido e a **inativação** dos
de quem foi desligado, sem intervenção manual do RH.

Antes, alguém do RH abria cada chamado à mão e conferia o status um por um —
ex-funcionário com acesso ativo era achado por acaso. Hoje o ciclo inteiro roda em
uma execução diária: detecta o movimento, identifica o gestor responsável, abre o
chamado na categoria certa e acompanha até a TI concluir.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-2_bases-blue)
![peewee](https://img.shields.io/badge/ORM-peewee-blue)
![API REST](https://img.shields.io/badge/integra%C3%A7%C3%B5es-3_APIs-blue)

---

## O que faz

| Rotina | Dispara | Resultado |
|---|---|---|
| **Admissão** | admitido nos últimos 2 dias | chamado de criação de acesso, com os gestores em cópia |
| **Rescisão** | rescisão confirmada, a partir do dia seguinte | chamado de inativação de acesso |
| **Acompanhamento** | chamados em aberto | grava o status até o chamado sair de circulação |

Uma execução por dia. O agendamento é externo — a rotina não agenda nada, o que a
deixa igual em cron, systemd timer ou orquestrador.

```bash
python executar.py              # abre os chamados e grava
python executar.py --simular    # mostra o que seria enviado, sem efeito algum
```

---

## Resultado medido

| | |
|---|---|
| Chamados abertos e acompanhados por dia | **2**, sem toque humano |
| Gestor correto identificado | **49 de 49** admitidos, contra 21 antes da hierarquia da folha |
| Gestor efetivamente em cópia | **45 de 49** — os 4 restantes não têm conta no service desk |
| Unidades sem gerente cadastrado no RH | **resolvidas** — a hierarquia cobre as 7 lojas que a inferência por loja não alcançava |
| Pedido duplicado | **zero**, por registro de `cpf + data do evento` |

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
    ├── fonte_webfopag.py         adapter: hierarquia de chefia (API da folha)
    ├── acelerato.py              adapter: API do service desk
    └── models.py / repository.py persistência (peewee)
```

Separação por fonte de dados: cada adapter fala com **uma** origem. O `gestores.py`
não abre conexão nem chama API — recebe o que as fontes trouxeram e decide, então a
regra de negócio é testável sem subir nada. As dependências entram pelo construtor e
quem lê o `.env` é a fábrica, na borda: importar módulo não abre conexão.

**1.578 linhas, 15 módulos, sem framework.**

---

## De onde vêm os dados

Nenhum arquivo de dados no projeto — tudo buscado ao vivo, de banco ou API, a cada
execução.

| Informação | Fonte |
|---|---|
| Admitidos e rescindidos | base do RH: `mov_funcao` + `cad_funcionario` + `cad_funcao` |
| **Gestor do colaborador** | **API da folha: hierarquia de chefia cadastrada** |
| Supervisor do admitido | base de recrutamento: vaga do candidato, ligada por CPF |
| E-mail do gestor | base de recrutamento: usuário solicitante da vaga |
| E-mail do gestor (alternativa) | base de recrutamento: perfil de acesso da loja |
| `usuarioKey` do seguidor | API do service desk, resolvida pelo e-mail |

O gestor é resolvido por uma cascata de **cinco fontes**, da mais confiável à mais
genérica, começando pelo vínculo de chefia cadastrado na folha. **O e-mail nunca é
deduzido do nome** — essa tentativa foi medida e errou 3 em 10, porque há gestor com
e-mail pessoal e outro em domínio diferente.

---

## Decisões técnicas

As que custaram mais investigação e as que evitam erro silencioso.

**A hierarquia de chefia vem da folha, não da loja.**
O RH reportou gestor errado em cópia: o campo da vaga guarda quem *solicitou* a
contratação, que muitas vezes não é quem gerencia a pessoa. Trocar para a árvore de
supervisores da folha corrigiu 28 dos 49 casos e cobriu as unidades sem gerente
cadastrado, onde a inferência por loja não tinha resposta nenhuma.

**Dependência externa nova não entra no caminho crítico.**
Se a API da folha estiver fora, a rotina cai para a cascata anterior, registra a
falha no resultado e **abre o chamado de qualquer jeito**. Pedido de acesso não pode
parar por indisponibilidade de terceiro.

**Idempotência por pessoa, não por data do chamado.**
A chave é `cpf + data do evento`. Cobre três casos que a data do chamado não cobria:
rodar duas vezes no mesmo dia, ficar um dia sem rodar, e admissão com data futura —
que existe na base e, sem isso, era pedida de novo todo dia até a data chegar.

**O chamado de rescisão só sai no dia seguinte ao desligamento.**
`data_rescisao <= current_date - 1`. Sem esse limite, o acesso cairia com a pessoa
ainda trabalhando.

**Erro de API mantém o chamado em acompanhamento.**
Só conclusão, lixeira, arquivamento, mesclagem ou `404` encerram. Tratar erro de
servidor como conclusão largaria um chamado que a TI nunca atendeu.

**Deduplicação por CPF na origem.**
Quem foi transferido tem uma linha por loja na base — até cinco para a mesma pessoa e
a mesma data. Sem `DISTINCT ON (cpf)`, saía repetida no chamado.

**Modo simulação.**
Faz tudo menos abrir chamado e gravar: imprime título, tabela e seguidores que
seriam enviados. É o que permite validar mudança contra dados de produção sem efeito
colateral.

**Migração automática de schema.**
`CREATE TABLE IF NOT EXISTS` não altera tabela existente, então as colunas são
conferidas à parte e a nova é preenchida com o default — o deploy não exige migração
manual nem downtime.

---

## Particularidades das APIs

Comportamentos descobertos por engenharia reversa, ausentes da documentação.

| Comportamento | Consequência |
|---|---|
| Seguidor só entra por `usuarioKey`; por e-mail devolve `500` mesmo com usuário existente | o `usuarioKey` é resolvido pelo e-mail antes de enviar |
| `GET /usuarios` ignora o parâmetro `filtro` e devolve sempre os mesmos 10 | os campos do filtro vão achatados na query |
| A API adiciona a conta de integração e o solicitante como seguidores; repetir um deles devolve `500` | essas chaves são descartadas antes do envio |
| Chamado inexistente devolve `404`, não corpo vazio | só o `404` encerra o acompanhamento |
| `kanbanStatus.fim` indica etapa final | mais confiável que comparar o id da etapa, que varia por quadro |
| A hierarquia de chefia exige CPF **e** CNPJ do empregador, e devolve CPF como `float` | o CNPJ é resolvido antes, e o CPF é reconstruído com zero à esquerda |
| A árvore de supervisores é recursiva | o primeiro nível é o gestor direto; o seguinte, o regional |

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

Copie o `.env.example` para `.env` e preencha. O `.env` não vai para o repositório, e
nenhuma credencial aparece no código.

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
| `WEBFOPAG_*` | API da folha: `CS`, `CPF_USUARIO`, `USERNAME`, `PASSWORD` |

```bash
pip install -r requirements.txt
python executar.py --simular
```

Dependências: `peewee`, `psycopg2-binary`, `python-dotenv`, `requests`.
