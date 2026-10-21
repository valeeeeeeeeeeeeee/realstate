# Sistema de Avisos Automáticos para Imobiliária

## Objetivo

Criar um sistema que envie avisos automaticamente para os clientes de uma imobiliária e que faça os reajustes anuais de aluguel sozinho.

## Avisos automáticos

### 1. Aviso de pagamento
- Enviado **na data de vencimento** do aluguel.
- Lembra o locatário do valor e da data do pagamento.

### 2. Aviso de reajuste de aluguel
- Enviado **1 mês antes** da data prevista para o reajuste.
- Deve informar:
  - O IGP-M acumulado no período de 12 meses.
  - O cálculo do reajuste (valor atual × (1 + IGP-M acumulado) = novo valor).
  - O novo valor do aluguel e a data em que ele passa a valer.

## Reajuste anual automático

- O sistema aplica o reajuste anual de cada contrato **automaticamente** na data prevista.
- O índice usado é o **IGP-M acumulado nos 12 meses** anteriores ao reajuste.
- O novo valor substitui o valor do aluguel no cadastro da locação.

## Banco de dados

- Banco leve: **SQLite**.
- Guarda informações de **imóveis**, **locatários** e **locadores**:
  - Nomes
  - E-mail
  - Telefone
  - Endereço do imóvel
  - Data de entrada e data de saída
  - Valor do aluguel
  - Data do pagamento

## Painel de administração

Painel para gerenciar os cadastros e as locações:

- Adicionar locadores e locatários.
- Alterar informações das locações (datas, valores, e-mails).
- Remover locatários e locadores.
- Marcar a locação como **contrato rescindido** ou **fim da locação**.
