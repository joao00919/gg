# Correção do tópico do carrinho — 4.3.18

## Erro corrigido

```text
'Thread' object has no attribute 'create_thread'
```

O erro acontecia quando o botão de compra era usado dentro de um tópico do Discord. O fluxo tentava executar `create_thread()` no próprio objeto `Thread`.

## Comportamento novo

- Em canal de texto: o carrinho é criado normalmente nesse canal.
- Dentro de um tópico: o bot localiza o canal pai e cria o carrinho privado nele.
- Se o canal pai não puder ser localizado, o usuário recebe uma mensagem clara de configuração/permissão.
- O restante do fluxo de estoque, carrinho e pagamento permanece inalterado.

## Validação

- Teste de interação dentro de tópico.
- Teste de recuperação do canal pai por `parent_id`.
- Verificação de que não existe mais chamada direta `inter.channel.create_thread()` no checkout.
- Suíte completa: 112 testes aprovados.
