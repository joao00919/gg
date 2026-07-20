# Correção do menu principal — ZENYX 4.3.18

Alterações desta revisão:

- `PromisseCloud` foi substituído por `ZenyxClous` no menu principal.
- A saudação agora identifica o sistema como `ZENYX Bot`.
- O botão `Configurações` passou a ser roteado diretamente para o módulo carregado.
- O botão `Configurar Loja` passou a ser roteado diretamente para o módulo carregado.
- Os sete botões do menu principal agora reconhecem a interação antes do limite do Discord.
- Quando um módulo não estiver disponível no plano, o bot mostra um erro claro em vez de deixar a interação expirar.
- `Promisse Wallet` foi removido da lista de formas de pagamento e de suas rotas visíveis.
- A Carteira Integrada continua disponível como opção independente.
- O helper de interação agora usa `response.edit_message` para reconhecer cliques de botões e selects imediatamente.

## Validação local

Execute:

```bat
VALIDAR_BOTOES_MENU_LOCAL.bat
```

O teste verifica Configurar Loja, Gerenciar Ticket, ZenyxClous, Proteção do Servidor, Automações, Configurações, Sorteios e Formas de Pagamento.
