# ZENYX Systems 4.3.18 — Interface do vídeo completo

Esta versão reconstrói, dentro da base ZENYX existente, as telas e rotas observáveis no vídeo de referência enviado em 19/07/2026.

## Áreas ajustadas

- Menu principal e navegação de `botconfig`.
- Configurar Loja, produtos, painéis, personalização, preferências e extensões.
- Gerenciar Ticket, criação e edição de painéis, opções, mensagens e preferências.
- ZenyxClous/OAuth2, recuperação de membros, logs e credenciais.
- Proteção do Servidor e bloqueio de links.
- Backup e restauração.
- Automações, ZYNEX AI Chat e chave Groq.
- Configurações de moderação, notificações, bot, canais e cargos.
- Formas de pagamento sem Promisse Wallet.
- Sorteios com Modo Real/Modo Fake e painel direto de nome, prêmio, requisitos, cargos bônus, mensagem e envio.

## Correções funcionais preservadas

- Reconhecimento imediato das interações para evitar “O aplicativo não respondeu”.
- Carrinho criado corretamente quando o comprador está dentro de um tópico.
- Carrinho e pagamento reorganizados.
- Sincronização por aplicação dos emojis personalizados com fallback seguro.
- Event loop compatível com Python recente.

## Validação local

- Compilação de todos os arquivos Python.
- Suíte automatizada completa.
- Validação offline do menu principal, Configurar Loja, `/botconfig`, `/qrcode_personalizar` e `/criar`.
- Carregamento de extensões e comandos sem conexão com o Discord.

## Limites da validação

Integrações externas exigem credenciais válidas e teste no servidor real: Discord, OAuth2, Groq, Telegram, PIX, cartão, MongoDB, API de transcripts e ZenyxClous. Nenhum token ou segredo real está incluído no pacote.
