# Atualização Configurar Loja — vídeo completo — 4.3.18

## Fluxos reconstruídos

- Página Loja com Gerenciar Produtos, Personalizar Loja, Preferências, Extensões, Sistema de Saldo, Cashback e Programa de Indicação.
- Gerenciador conjunto de produtos e painéis, com paginação, criação e seleção.
- Criação manual e assistida de produto.
- Painel de produto com edição, estoque, estilo de entrega, configurações extras, sincronização e exclusão.
- Painéis de produtos com embed, produtos, emoji, sequência e sincronização.
- Personalização da mensagem de compra, redefinição e sincronização das publicações.
- Mensagem de compra aprovada com estilo, importação JSON, visualização, variáveis e botões Comprar/Feedbacks.
- Mensagem de primeira compra e mensagem após compra com destino, atraso e botão opcional.
- Preferências de carrinho, dúvidas, termos, blacklist, solicitação de estoque, ranking e avaliações.
- Editor de solicitação de estoque com mensagem, embed, imagem, visualização e postagem.

## Correções funcionais

- As interações são reconhecidas antes de operações demoradas, evitando “O aplicativo não respondeu”.
- A mensagem interna de pontos/VIP não é mais publicada no carrinho após a aprovação.
- A mensagem aprovada configurada é aplicada à confirmação enviada ao comprador.
- Mensagens de primeira compra e pós-compra são persistidas e utilizadas pelo fluxo de pós-pagamento.

## Validação

- Compilação integral dos arquivos Python.
- Suíte automatizada com 132 testes.
- Carregamento local de cogs e comandos slash.
- Simulação dos comandos críticos e inspeção estrutural dos painéis do vídeo.

A validação local não substitui o teste final em um servidor Discord com token, permissões, canais e provedores reais.
