# Correção `/set`, descrições e estilos — ZENYX 4.3.18

## Alterações

- O comando `/set` voltou a publicar um produto existente.
- O usuário seleciona o produto e, opcionalmente, o canal.
- Antes da publicação, o bot oferece cinco estilos:
  - Modo Texto Simples
  - Modo Legacy
  - Modo Legacy (Personalizado)
  - Container V2 com imagem fora
  - Container V2 com imagem dentro
- Produtos antigos com descrição vazia são normalizados usando a descrição do produto ou da primeira opção cadastrada.
- O comando `/criar` permite informar uma descrição já no cadastro.
- As opções criadas pelo formulário herdam a descrição do produto.
- O comando `/set_painel` também abre a seleção de estilo antes de publicar.
- Painéis agora permitem configurar título, descrição, banner e cor hexadecimal.
- As publicações de painéis suportam Texto, Legacy, Legacy personalizado e Container V2.
- A sincronização de mensagens preserva o estilo usado em cada publicação.

## Validação

- 176 testes automatizados aprovados.
- Compilação integral concluída.
- Validadores locais de comandos, loja e botões principais concluídos.
