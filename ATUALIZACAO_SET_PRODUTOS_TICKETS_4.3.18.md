# Atualização 4.3.18 — /set, produtos, mensagens e tickets

## /set

- O comando `/set` não publica mais um produto existente.
- Agora abre o cadastro completo com nome, descrição, valor e banner opcional.
- A descrição pública do comando foi alterada para `Cadastra um novo produto no bot`.

## Produtos

- Produtos novos exigem descrição no cadastro manual.
- Produtos antigos sem descrição recebem uma descrição segura de fallback na interface.
- Select menus de produtos exibem a descrição real do produto e o emoji configurado.
- Painéis públicos e publicações individuais exibem descrição mesmo em cadastros antigos.

## Configurar mensagens

Foi adicionada a seção **Configurar Mensagens** em Configurações, com os canais:

- Compras
- DMs
- Feedbacks
- Saques
- Saldo Adicionado

Cada canal pode ser editado individualmente pelo select menu.

## Tickets

- O painel principal mantém o mesmo alinhamento de três botões.
- O controle global permanece visível e fica desativado quando não existe painel.
- Foram preservadas as correções de logs, callbacks, modais e proteção.

## Validação

- Compilação completa.
- 173 testes aprovados.
- Validação local das interações críticas concluída.
