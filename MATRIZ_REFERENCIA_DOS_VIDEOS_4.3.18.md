# Matriz de referência — cinco vídeos — ZENYX 4.3.18

Esta matriz relaciona a interface observável nos vídeos enviados com a implementação
incluída no pacote. A reconstrução foi feita pela interface e pelo comportamento
visível; nenhum código-fonte do bot exibido nos vídeos foi utilizado.

| Área observada | Componentes reconstruídos | Validação |
|---|---|---|
| Menu `/botconfig` | Logo zenyx2, saudação e grade 3x3: Loja, Ticket, Cloud, Rendimento, Personalização, Automações, Proteção, Sorteios e Configurações | teste dinâmico dos componentes |
| `/criar nome:` | Opção `nome`, criação direta, mensagem de sucesso e abertura do produto | teste de comando e schema |
| Produto | Informações, preço, estoque, entrega, descrição, condições, cargos e oito ações | teste dinâmico do painel |
| Config.Extra | Editar Valores, Resetar Cargos e select de cargos | teste de regressão da interface |
| Configurações avançadas | Banner, Miniatura, Cargo, Cor Embed, Categoria e cupons | teste de regressão da interface |
| Estoque | Adicionar, Fantasma, Upload .txt, Ver estoque, Infinito e Limpar | teste de regressão e listeners existentes |
| Painel select | Configurar Embed/Produtos, publicar, excluir, adicionar/remover produtos, emoji, sequência e sincronização | teste dinâmico e custom IDs |
| Carrinho com um item | Ir para pagamento, Editar quantidade, cupom e termos | teste dinâmico das linhas |
| Carrinho com vários itens | Ir para pagamento, select de gerenciamento, cupom e termos | teste dinâmico do select |
| Escolha de pagamento | Pix, cartão e voltar | teste de regressão do fluxo |
| Pagamento PIX | Copiar código, atualizar status, cancelar e aprovação manual | testes de contrato e fluxo |
| Tickets | Edição de opções/mensagens, modo, horário, IA, preferências, canais/cargos, publicação e exclusões | teste dinâmico e handlers |
| Emojis | IDs fornecidos, logo global e assets locais para sincronização | teste de catálogo/asset |
| Inicialização | armazenamento local/Mongo, extensões, política de comandos e diagnóstico | `python bot.py --check` |

## Dependências externas que não podem vir preenchidas

O pacote não inclui token do Discord, segredo de webhook, senha de MongoDB ou chave
de pagamento. Para validar em produção, o proprietário precisa preencher `.env`,
ativar os intents, convidar o bot com as permissões necessárias e configurar os
provedores de pagamento.

## Comando de validação

No Windows, execute `VALIDAR_REFERENCIA_VIDEO.bat`. Em qualquer sistema:

```bash
python -m pytest -q
python bot.py --check
```
