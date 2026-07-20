# ZENYX Systems 4.3.18 — Configurar Loja: vídeo completo
Esta edição reconstrói o fluxo observável do vídeo completo da aba **Configurar Loja**, preservando o motor próprio do ZENYX e conectando os botões, selects e modais às rotinas locais.

Este pacote contém a reconstrução funcional da interface observável nos cinco vídeos enviados, com identidade `zenyx2`, painéis administrativos, produtos, carrinho, pagamentos e tickets. Consulte `MATRIZ_REFERENCIA_DOS_VIDEOS_4.3.18.md`.

Bot de vendas para Discord em Python 3.11+ e Disnake 2.12.

## Destaques

- `/criar` com cadastro guiado e painel completo de produto.
- Carrinho inicial limpo, sem atualizar/cancelar.
- Pagamento PIX com código copia e cola e cancelamento corrigido.
- PIX Manual disponível em todos os planos.
- Entrega automática na DM após confirmação do pagamento.
- Canal de logs de reinicialização escolhido pelo cliente.
- Logo e emoji online personalizados corrigidos.
- Integração com Manager, MongoDB e API de transcripts preservada.

## Início rápido

1. Copie `.env.example` para `.env`.
2. Preencha as credenciais do Discord e o servidor principal.
3. Execute `python -m pip install --no-cache-dir -r requirements.txt`.
4. Execute `python -u bot.py`.
5. No Discord, abra `/botconfig`.

Para detalhes desta correção, consulte `ATUALIZACAO_COMPLETA_4.3.18.md`.

---

# ZYNEX Systems 4.3.9 — Carrinho com Entrega por DM

Bot de vendas para Discord em Python 3.11+ e Disnake 2.12.

## Entrega desta versão

- Carteira Integrada conectada à API oficial da PurinCash.
- Credencial global no `.env`; nenhuma chave é informada pelo painel do Discord.
- PIX automático, consulta de pagamento, saldo, saque e webhook assinado.
- Taxa operacional e configuração existente da loja exibidas no painel, sem botão público para alterar a Taxa da Loja.
- Responsabilidade da taxa operacional selecionável entre Loja e Cliente.
- `/criar_painel` cria um painel Select Menu vazio e abre o gerenciador; não publica um produto já existente.
- `/config_painel` edita o painel e `/set_painel` publica no canal escolhido.
- Carrinho reorganizado, com resumo de taxas e botão **Ir para o carrinho** após adicionar produtos.
- Emojis padrão preservados; os emojis `on`, `off` e `config` usam os IDs fornecidos pelo proprietário.

## Fluxo 4.3.9

- Pagamento aprovado confirmado no mesmo canal do carrinho.
- Produto automático entregue exclusivamente na DM do comprador.
- Mensagem de entrega na DM agora suporta estilo `embed`, `components` ou `banner`.
- Mensagem de avaliação ficou mais completa, com layout configurável e botões de nota rápida de 1 a 5 estrelas.
- Painel Loja > Personalizar > Mensagens agora inclui configurações separadas para Entrega e Avaliação.
- Carrinho com visual premium no estilo das referências, com botões reorganizados e mais claros.
- Resumo do carrinho com seção **Detalhes da sua compra**, valor à vista em destaque e layout mais limpo.
- Tela de PIX refinada com resumo compacto, QR Code, código copia e cola e ações principais melhor organizadas.
- Botão **Ir para DM** abre diretamente a conversa privada.
- Carrinho bloqueado e arquivado 3 minutos após a aprovação.
- Temporizador restaurado automaticamente após reinício do bot.

## Instalação local

1. Instale Python 3.11 ou 3.12.
2. Execute `INSTALAR_LOCAL.bat`.
3. Copie `.env.example` para `.env`.
4. Preencha `DISCORD_TOKEN`, `DISCORD_CLIENT_ID`, IDs administrativos e as variáveis PurinCash.
5. Execute `INICIAR_LOCAL.bat`.

Diagnóstico sem conectar ao Discord:

```bat
python bot.py --check
```

## Carteira Integrada

Configuração mínima:

```env
PURINCASH_API_KEY=ps_test_ou_ps_live
PURINCASH_API_URL=https://api.purincash.com/v1
```

Para confirmação por webhook:

```env
PRIVATE_API_ENABLED=true
PRIVATE_API_PORT=8080
PURINCASH_CALLBACK_URL=https://seu-dominio.com/webhooks/purincash
PURINCASH_WEBHOOK_SECRET=segredo_configurado_na_purincash
```

A URL pública deve encaminhar HTTPS para a porta definida em `PRIVATE_API_PORT`.

No Discord:

`/botconfig` → **Configurações** → **Formas de Pagamento** → **Carteira Integrada**

O botão **Definir Taxa da Loja** foi removido. O botão **Responsabilidade Taxa** continua controlando quem cobre a taxa operacional exibida no painel.

## Painel Select Menu

- `/criar_painel nome:<nome>` cria o painel.
- Adicione ou remova produtos pelos seletores do gerenciador.
- Publique usando o seletor de canal ou `/set_painel`.
- `/config_painel` reabre um painel existente.

## Segurança

- Não publique `.env`, tokens, chaves ou segredos de webhook.
- Use uma chave de teste antes da produção.
- Use HTTPS no callback.
- O webhook valida `X-Webhook-Signature` e evita processamento duplicado por `X-Webhook-Id`.

## Emojis padrão

Esta versão restaurou os emojis originais do bot. Na primeira execução, mantenha `SYNC_APPLICATION_EMOJIS=true`. Caso esteja reutilizando um `.env` antigo, execute `RESTAURAR_EMOJIS_PADRAO.bat` uma vez.


## Compra aprovada e suporte vinculado

Após a confirmação do pagamento, o comprador recebe um comprovante na DM, botão para avaliar a compra e o carrinho mostra um botão para abrir a conversa privada. O sistema de tickets recupera automaticamente pedidos aprovados que não tenham sido indexados por versões anteriores.

## Carrinho avançado

- Resumo completo com produtos, opções, quantidades, estoque, entrega, descontos, taxas e total.
- Seletor **Gerenciar produto, opção ou quantidade** para editar ou remover itens.
- Controles de cupom, saldo, termos, atualização, pagamento e cancelamento.
- Checkout PIX com código copia e cola, QR Code, atualização manual de status e monitor automático.
- O botão **Cancelar pagamento** fica ao lado de **Código copia e cola**.

- Layout dos botões do carrinho reorganizado para ficar mais próximo da referência enviada.
- Primeiras ações destacadas: Ir para pagamento e Editar quantidade.
- Segunda linha com Usar cupom de desconto e Ler Termos e Condições.

- Entrega na DM reformulada no estilo profissional das referências: pedido, itens, produto liberado e botão Avaliar Produto.
- Avaliação aberta pelo botão da entrega, com painel de 1 a 5 estrelas.
- Confirmação no carrinho reformulada com Informações da Compra, código, status, entrega e botão Ir para DM.

- O código da compra foi removido das mensagens exibidas ao cliente.
- A entrega na DM agora usa apenas o título **Entrega do Produto**, sem “PEDIDO #CÓDIGO”.
- O carrinho aprovado mostra produto, quantidade, valor e status, sem identificador interno.

- A mensagem “Compra aprovada com sucesso, entregando produtos...” só aparece após a confirmação real do pagamento.
- Após a entrega, a mesma mensagem é editada com o botão para abrir a DM.
## Correção do menu principal 4.3.18

A revisão `MENU_FUNCIONAL` corrige o reconhecimento dos botões principais, troca o rótulo da nuvem para **ZenyxClous** e remove **Promisse Wallet** das formas de pagamento. Para validar offline, execute `VALIDAR_BOTOES_MENU_LOCAL.bat`.

## Gerenciar Tickets — vídeo completo

A revisão `GERENCIAR_TICKETS_VIDEO_COMPLETO` reorganiza o módulo de tickets conforme o vídeo de referência. Consulte `ATUALIZACAO_GERENCIAR_TICKETS_VIDEO_COMPLETO_4.3.18.md` para a matriz de funções implementadas.

## Validação completa da interface do vídeo

Execute `VALIDAR_VIDEO_COMPLETO_LOCAL.bat` no Windows para conferir, sem conectar ao Discord, os comandos públicos, contratos visuais, botões principais, Configurar Loja, interações críticas e compatibilidade dos modais. Os detalhes e limites estão em `VALIDACAO_VIDEO_ENVIADO_4.3.18.md`.
