# Correção dos botões de Proteção — ZENYX 4.3.18

## Problema corrigido

Os botões **Cargos Imunes** e **Canais Imunes** abriam modais inválidos no Discord. Os selects permitiam zero itens (`min_values=0`), mas permaneciam marcados como obrigatórios (`required=true`). O Discord recusava o modal com o erro `50035 Invalid Form Body`.

## Correção

- `RoleSelect` de cargos imunes agora usa `required=False`.
- `ChannelSelect` de canais imunes agora usa `required=False`.
- A seleção vazia continua válida e serve para remover toda a lista de imunidades.
- Adicionado teste de regressão que examina todos os modais do projeto e impede novos selects opcionais marcados como obrigatórios.

## Validação local

- Serialização dos dois modais validada conforme o formato aceito pelo Discord.
- Suíte completa: 160 testes aprovados.
- Compilação integral dos arquivos Python concluída.
