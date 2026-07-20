# 4.3.18 — Set, produtos e tickets corrigidos

- `/set` passou a cadastrar produtos completos.
- Descrições adicionadas aos produtos e selects.
- Nova seção Configurar Mensagens.
- Layout do painel de tickets estabilizado.

# Changelog — ZENYX Systems 4.3.18

## 4.3.18 — Configurar Loja no formato da referência

- Menu da loja com Gerenciar Produtos, Personalizar Loja, Preferências e Extensões.
- Sistema de Saldo, Cashback e Programa de Indicação mantidos no mesmo menu.
- Botão Ligar/Desligar Vendas conectado ao checkout.
- Templates da loja com salvamento e aplicação de configurações.
- Produtos e painéis reunidos em um painel paginado.
- Personalização com quatro mensagens separadas.
- Preferências com estilo do carrinho, dúvidas, termos, blacklist, estoque, ranking e avaliações.
- 123 testes automatizados aprovados.

## 4.3.18 — Painéis organizados, PIX Manual e cancelamento corrigido

- `/criar` reorganizado em cinco etapas.
- Painel de produto com visão geral, próximos passos e ações separadas por função.
- Carrinho inicial sem Atualizar carrinho e Cancelar compra.
- Pagamento com Código copia e cola e Cancelar pagamento.
- Cancelamento compatível com carrinhos antigos e novos.
- PIX Manual liberado em todos os planos.
- Mensagens técnicas de PURINCASH_API_KEY removidas da interface.
- Logo do Bot de Vendas e emoji online fixados.
- Reinicialização enviada somente ao canal configurado pelo cliente.
- 90 testes automatizados aprovados.

# Changelog — ZYNEX Systems 4.3.3

## 4.3.3 — Entrega por DM e fechamento automático

- Pagamento aprovado confirmado no mesmo canal do carrinho.
- Itens automáticos entregues exclusivamente na DM do comprador.
- Botão **Ir para DM** aponta para o canal privado criado pelo bot.
- Carrinho bloqueado e arquivado três minutos após a aprovação.
- Recuperação do temporizador de fechamento após reinício do bot.
- Aviso claro quando a DM do comprador está bloqueada.


## 4.3.2 — Carrinho Premium

- Interface reorganizada com progresso de revisão, pagamento e entrega.
- Botões Ir para Pagamento, Editar Itens, Adicionar Produtos, Cupom, Saldo, Termos, Atualizar, Ajuda e Cancelar.
- Adição de novos produtos e opções no mesmo carrinho, com quantidade e validação de estoque.
- Edição de itens movida para menu privado para manter o carrinho limpo.
- Ajuda contextual integrada aos painéis de ticket comuns ativos.
- Entrega no mesmo carrinho preservada.

## 4.3.2 — Entrega no mesmo carrinho

- Produto automático entregue diretamente no tópico privado do carrinho.
- DM mantida apenas como comprovante e contingência.
- Removido o redirecionamento “Ir para o pedido entregue”.
- Avaliação liberada no próprio carrinho.
- Carrinho não é mais apagado após poucos minutos; é arquivado após 24 horas.


## 4.3.2 — Carrinho avançado e checkout PIX completo

- Carrinho redesenhado com resumo detalhado, estoque, tipo de entrega e total final.
- Seletor compacto para gerenciar produtos sem exceder o limite de componentes do Discord.
- Botões para cupom, saldo, termos, atualização, pagamento e cancelamento.
- Checkout PIX com produtos, resumo, código copia e cola, QR Code e status.
- Botão Cancelar pagamento ao lado do Código copia e cola.
- Consulta manual de status com proteção contra spam, mantendo o monitor automático.

## 4.2.9 — Compra aprovada, avaliação e tickets por pedido

- Envia confirmação de pagamento e entrega na DM do comprador.
- Adiciona botão **Abrir minha DM** no carrinho aprovado.
- Libera o botão **Avaliar compra** com nota de 1 a 5 e comentário.
- Publica avaliações no canal de feedback quando configurado.
- Impede avaliação duplicada e valida o comprador no backend.
- Repara automaticamente compras aprovadas que não entraram no histórico.
- O ticket vinculado à compra passa a localizar pedidos do checkout, saldo e PIX.
- Mantém proteção contra pedidos duplicados por carrinho/pagamento.

## Carteira Integrada

- Saque reorganizado no padrão solicitado: **Chave Pix**, **Valor do Saque** e **Estilo de Saque**.
- Único estilo disponível: **Retirada Turbo (R$ 1,50) — Imediata**.
- Validação de saldo considera o valor solicitado e a taxa Turbo.
- Removida a explicação “A Taxa da Loja é somada à cobrança...”.
- O botão **Exibir Extrato** permanece removido.

## ZYNEX Cloud

- Verificação local por botão funcionando para membros.
- Cargo de verificado configurável pelo painel.
- Validação de `Gerenciar Cargos` e da hierarquia do cargo do bot.
- Registro da verificação e restauração do cargo ao membro retornar, quando a persistência estiver ativa.
- Módulo disponível também no plano básico.

## Carrinho

- Corrigido o erro que impedia **Continuar para Pagamento** de identificar o carrinho.
- Loading imediato ao preparar o PIX.
- Proteção contra clique duplo e cobranças duplicadas.
- Recuperação automática de trava antiga após 120 segundos.
- Erros de pagamento agora são informados ao cliente e o carrinho é liberado para nova tentativa.
- Botões de atualizar, editar quantidade, remover item, cupom, forma de pagamento, saldo, cancelar e continuar.
- Resumo com itens, opções, quantidade, subtotal, descontos, taxas e total do PIX.

## Terminologia

- O nome público **Campo** foi substituído por **Opção do Produto** ou **Opção**.
- Identificadores internos foram preservados para manter compatibilidade com dados e botões existentes.

## Qualidade

- 64 testes automatizados aprovados.
- Compilação integral aprovada.
- Diagnóstico local aprovado.
- 191 cogs e 45 comandos slash carregados sem conexão ao Discord.

## 4.2.8 — Loading animado e correção do ZYNEX Cloud

- Loading global alterado para `<a:1389945080172904539:1527386782776164392>`.
- Removida a ampulheta estática das mensagens centrais de carregamento.
- Corrigido o travamento ao abrir o painel ZYNEX Cloud quando `emoji.user` não existia.
- Corrigida a seleção do gerenciador WebSocket compatível com o módulo Cloud.

## 4.2.8 — Correção dos comandos de publicação

- `/set` agora publica um produto já criado e não abre mais o cadastro de produto.
- `/set_painel` publica exclusivamente um painel Select Menu já criado.
- Ambos possuem autocomplete e seleção opcional de canal.
- Loading global utiliza `<a:1389945080172904539:1527386782776164392>`.
- Corrigido o painel ZYNEX Cloud e a ponte do WebSocket.
## 4.3.18 — validação do vídeo enviado

- Descrições dos 25 comandos ajustadas ao seletor visual da referência.
- Capitalização do editor de anúncios alinhada ao vídeo.
- Proteção global contra selects opcionais inválidos em modais.
- Fallback global para erros não tratados em botões, selects e modais.
- Validador consolidado `VALIDAR_VIDEO_COMPLETO_LOCAL.py/.bat`.
- Contrato completo do vídeo adicionado à suíte de testes.
