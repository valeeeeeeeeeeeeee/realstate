# Especificação — Sistema de Avisos e Reajustes de Locação

Base: [IDEIA.md](IDEIA.md) + entrevista de 21/10/2026.

## 1. Visão geral

Aplicação web que **roda localmente** no computador da imobiliária. Ela:

1. Envia avisos automáticos de **pagamento** e de **reajuste** por **e-mail**.
2. Aplica o **reajuste anual** dos aluguéis sozinha, pelo **IGP-M acumulado em 12 meses**.
3. Tem um **painel de administração** no navegador para gerenciar locadores, locatários, imóveis e locações.

Os dados ficam em um banco **SQLite**.

## 2. Usuários e acesso

- Um único **administrador**, que entra com usuário e senha.
- A senha é guardada com hash (bcrypt/argon2), nunca em texto puro.
- O painel abre em `localhost`. Ele não é publicado na internet.

## 3. Modelo de dados

### Relações
- Um **locador** pode ter **vários imóveis**.
- Um **imóvel** tem no máximo **uma locação ativa** por vez e guarda o histórico das anteriores.
- Cada **locação** liga um imóvel a um **locatário**.

### Tabelas

**locador**
| campo | tipo | obs |
|---|---|---|
| id | int PK | |
| nome | texto | obrigatório |
| email | texto | obrigatório (recebe o aviso de reajuste) |
| telefone | texto | só para cadastro, não é usado nos envios |
| arquivado_em | data/hora | nulo = ativo |

**locatario**
| campo | tipo | obs |
|---|---|---|
| id | int PK | |
| nome | texto | obrigatório |
| email | texto | obrigatório |
| telefone | texto | só para cadastro, não é usado nos envios |
| arquivado_em | data/hora | nulo = ativo |

**imovel**
| campo | tipo | obs |
|---|---|---|
| id | int PK | |
| locador_id | FK locador | |
| endereco | texto | obrigatório |
| arquivado_em | data/hora | |

**locacao**
| campo | tipo | obs |
|---|---|---|
| id | int PK | |
| imovel_id | FK imovel | |
| locatario_id | FK locatario | |
| data_entrada | data | também serve de data base do reajuste |
| data_saida | data | fim previsto do contrato (só informativo) |
| valor_aluguel | decimal (centavos, inteiro) | valor vigente |
| dia_vencimento | int 1–31 | dia do mês do pagamento |
| status | enum | `ativa`, `rescindida`, `encerrada` |
| data_encerramento | data | preenchida ao rescindir ou encerrar |

**reajuste**: histórico dos reajustes
| campo | tipo | obs |
|---|---|---|
| id | int PK | |
| locacao_id | FK | |
| data_reajuste | data | aniversário do contrato |
| periodo_inicio / periodo_fim | mês | os 12 meses de IGP-M usados |
| igpm_acumulado | decimal | ex.: 0.0412 = 4,12% |
| valor_anterior | decimal | |
| valor_novo | decimal | |
| status | enum | `calculado`, `aplicado` |

**igpm**: índices mensais
| campo | tipo | obs |
|---|---|---|
| mes | data (AAAA-MM) PK | |
| variacao | decimal | % do mês |
| obtido_em | data/hora | |

**feriado**: feriados locais (estaduais e municipais)
| campo | tipo | obs |
|---|---|---|
| data | data PK | |
| descricao | texto | |

**aviso**: log de envios
| campo | tipo | obs |
|---|---|---|
| id | int PK | |
| locacao_id | FK | |
| tipo | enum | `pagamento`, `reajuste` |
| destinatario_tipo | enum | `locatario`, `locador` |
| destino | texto | e-mail usado |
| referencia | texto | ex.: `2026-11` (mês do vencimento) ou id do reajuste |
| status | enum | `enviado`, `falhou` |
| erro | texto | mensagem do servidor SMTP, se falhou |
| enviado_em | data/hora | |

Restrição de unicidade em (`locacao_id`, `tipo`, `destinatario_tipo`, `referencia`) para **nunca enviar o mesmo aviso em dobro**.

## 4. Regras de negócio

### 4.1 Aviso de pagamento
- **Quando:** na data de vencimento de cada mês, só para locações `ativas`. A data é calculada assim:
  1. Parte do `dia_vencimento` no mês. Se o mês não tem esse dia (ex.: dia 31 em novembro), usa o **último dia do mês**.
  2. Se essa data cair em **sábado, domingo ou feriado**, passa para o **próximo dia útil**.
- **Feriados:** os nacionais vêm da biblioteca `holidays` (Brasil). Os estaduais e municipais são cadastrados no painel, na tabela `feriado`.
- **Para quem:** só o locatário.
- **Conteúdo:** endereço do imóvel, valor vigente e data de vencimento (já ajustada para o dia útil).
- O sistema **não controla** se o aluguel foi pago. Ele só avisa.

### 4.2 Aviso de reajuste
- **Quando:** **1 mês antes** do aniversário do contrato (mesmo dia, mês anterior, com a mesma regra de fim de mês).
- **Para quem:** locatário **e** locador.
- **Conteúdo:**
  - O IGP-M de cada um dos 12 meses do período e o acumulado.
  - O cálculo: `valor_novo = valor_atual × (1 + IGP-M acumulado)`.
  - O valor atual, o valor novo e a data em que o novo valor passa a valer.
- Quando o aviso sai, o reajuste é gravado com status `calculado`. O valor informado fica **congelado** e é exatamente o que será aplicado.

### 4.3 Cálculo do IGP-M acumulado
- `acumulado = Π(1 + variacao_i / 100) − 1` sobre 12 meses consecutivos.
- **Período:** os 12 meses que terminam no mês anterior ao do aviso (portanto 2 meses antes do aniversário). Ex.: aviso em 15/11/2026 → IGP-M de nov/2025 a out/2026. A FGV divulga o índice no fim do próprio mês, então esse mês já está publicado na data do aviso.
- **Acumulado negativo:** o reajuste fica em **0%** e o valor se mantém. O aviso é enviado mesmo assim, informando isso.
- **Arredondamento:** o valor novo é arredondado para centavos (meio para cima).

### 4.4 Aplicação do reajuste
- **Totalmente automática**, sem aprovação, na data do aniversário.
- Atualiza `locacao.valor_aluguel` e marca o reajuste como `aplicado`.
- Se a locação deixar de estar `ativa` antes da data, o reajuste não é aplicado.
- O primeiro reajuste ocorre 12 meses após a `data_entrada`, e os seguintes a cada 12 meses.

### 4.5 Fonte do IGP-M
- A API do **Banco Central (SGS, série 189)** é consultada todo dia:
  `https://api.bcb.gov.br/dados/serie/bcdata.sgs.189/dados?formato=json&dataInicial=...`
- Os meses novos são gravados na tabela `igpm`.
- Se faltar algum mês do período na hora do aviso, o aviso **não é enviado**. A pendência aparece no painel e o sistema tenta de novo no dia seguinte.

### 4.6 Data de saída
- Quando a `data_saida` chega, o sistema **não faz nada**. A locação continua `ativa` e segue gerando avisos e reajustes.
- Encerrar ou rescindir a locação é sempre uma ação manual do administrador no painel.

## 5. Agendamento

- Uma rotina diária (ex.: às 08:00) roda dentro da aplicação, na seguinte ordem:
  1. Atualiza o IGP-M.
  2. Aplica os reajustes do dia.
  3. Envia os avisos de reajuste.
  4. Envia os avisos de pagamento.
- **Recuperação:** como roda no PC da imobiliária, a máquina pode estar desligada no horário. Ao iniciar, a rotina processa todos os dias pendentes desde a última execução, registrada em uma tabela `execucao`.
- Graças à unicidade em `aviso`, rodar a rotina de novo é seguro.
- A aplicação deve iniciar junto com o Windows (atalho na inicialização ou serviço).

## 6. Envio

- Só por **e-mail**, via SMTP configurável (servidor, porta, usuário, senha, remetente). Pode ser uma conta Gmail com senha de app, que é gratuita.
- As credenciais ficam em um arquivo `.env`, fora do banco e do git.
- Uma falha de envio vai para o log com `status = falhou` e não impede os demais envios.
- Os textos dos avisos ficam em templates editáveis (arquivos), com variáveis como `{nome}`, `{valor}`, `{vencimento}` etc.

## 7. Painel de administração

| Tela | Funções |
|---|---|
| Login | usuário e senha |
| Início | próximos vencimentos, próximos reajustes, falhas de envio, pendências de IGP-M |
| Locadores | listar, buscar, adicionar, editar, arquivar |
| Locatários | listar, buscar, adicionar, editar, arquivar |
| Imóveis | listar, adicionar, editar, vincular a locador |
| Locações | adicionar; editar datas, valor, dia de vencimento; **marcar como rescindida** ou **encerrada** (com data); ver histórico de reajustes |
| Avisos | log com filtros (tipo, status, período); **reenviar** aviso que falhou |
| IGP-M | tabela dos índices obtidos; botão "atualizar agora" |
| Feriados | listar, adicionar e remover feriados locais |
| Configurações | horário da rotina, teste de envio de e-mail, troca de senha |

- **Remover = arquivar.** O registro some das listas, mas o histórico de locações, reajustes e avisos fica guardado.
- Não dá para arquivar um locador ou locatário que tenha locação `ativa`. Antes é preciso encerrar ou rescindir a locação.
- Uma locação `rescindida` ou `encerrada` não gera mais avisos nem reajustes.

## 8. Stack

Escala: cerca de 10 clientes. Desempenho não pesa; o critério é ter pouco código para manter e uma instalação simples.

- **Python 3.12+** e **Django 6.1**
- O painel do §7 é o **Django Admin**, que já traz login, hash de senha, listas, busca, filtros e formulários. Ele é customizado com:
  - **Arquivar** em vez de excluir (ação + filtro padrão `arquivado_em` nulo), bloqueado se houver locação `ativa`
  - Ações em Locação: **rescindir** e **encerrar** (com data), mais o histórico de reajustes como inline
  - Aviso somente leitura, com a ação **reenviar** para os que falharam
  - Views extras: **atualizar IGP-M agora** e **teste de envio de e-mail**
  - Página inicial customizada com próximos vencimentos, próximos reajustes, falhas de envio e pendências de IGP-M
- **SQLite** pelo ORM do Django, com migrações nativas
- **APScheduler** (BackgroundScheduler), iniciado no `AppConfig.ready()`, para a rotina diária e a recuperação ao iniciar. Também há o comando `manage.py rodar_rotina` para rodar à mão
- `django.core.mail` para o envio por SMTP, configurado pelo `.env` (`python-dotenv`). Templates dos avisos em arquivos de template do Django
- `holidays` para os feriados nacionais e `python-dateutil` para as datas
- **Waitress** para servir em `localhost`. A aplicação inicia com o Windows por um atalho na pasta Inicializar (`pythonw run.py`)
- `pytest` + `pytest-django` para os testes, com foco no cálculo do IGP-M, nas regras de datas (fim de mês, dia útil) e na idempotência dos avisos

## 9. Fora do escopo (v1)

- Controle de pagamentos e inadimplência
- SMS e WhatsApp
- Ações automáticas na data de saída
- Vários usuários e permissões
- Acesso pela internet
- Geração de boletos ou contratos
