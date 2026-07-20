# Validação da interface observável — ZENYX 4.3.18

## Referência analisada

- Arquivo de vídeo enviado pelo usuário: aproximadamente 10 minutos.
- Amostragem técnica: 150 quadros distribuídos ao longo do vídeo.
- O link externo do YouTube não pôde ser carregado nesta sessão; portanto, esta validação certifica o conteúdo do vídeo enviado diretamente, não trechos que existam somente no link externo.

## Contrato implementado

### Comandos públicos

O conjunto público permanece restrito aos 25 comandos observados:

`anunciar`, `botconfig`, `cleardm`, `conectar`, `config`, `config_painel`, `configcupom`, `criados`, `criar`, `criar_painel`, `criarcupom`, `dm`, `entregar`, `estatisticas`, `gerarpix`, `nuke`, `perfil`, `qrcode_personalizar`, `rank`, `rankprodutos`, `resetar`, `set`, `set_painel`, `stockid` e `sync_clients`.

Os nomes e descrições exibidos no seletor de comandos foram padronizados conforme a referência visual.

### Interfaces verificadas

- Editor `/anunciar`, incluindo mensagem, container, embed, imagens, botões, visualização, postagem e templates.
- Menu `/botconfig` e suas sete seções principais.
- Configurar Loja, Gerenciar Produtos, painéis select, Personalizar Loja e Preferências.
- Produto, estoque, Config.Extra, configurações avançadas e condições de compra.
- Carrinho de um ou vários produtos, termos, cupom, quantidade e formas de pagamento.
- PIX manual, código copia e cola, cancelamento e aprovação administrativa.
- Gerenciar Tickets, opções, mensagens, preferências, canais, cargos, categoria e publicação.
- ZenyxClous, proteção do servidor, backup, automações, configurações e sorteios.
- Emojis personalizados da aplicação e fallback Unicode seguro.

## Correções estruturais

- Selects opcionais em modais com `min_values=0` são enviados como `required=false`, evitando o erro Discord `50035`.
- Exceções não tratadas em listeners de botão, select ou modal são registradas e recebem resposta visível, evitando expiração silenciosa.
- A proteção é instalada antes do carregamento das extensões e também nos validadores locais.
- O editor de anúncios usa a mesma capitalização observada nos botões principais.

## Validação executada

- 168 testes automatizados aprovados.
- Compilação integral dos arquivos Python.
- Diagnóstico local do armazenamento aprovado.
- Validação offline de `/botconfig`, `/qrcode_personalizar` e `/criar`.
- Validação dos sete botões do menu principal.
- Validação das sete rotas do select Configurar Loja.
- Validação consolidada disponível em `VALIDAR_VIDEO_COMPLETO_LOCAL.bat`.

## Limites reais

Esta entrega é uma reimplementação das interfaces e funções observáveis. Ela não contém nem afirma conter o código-fonte proprietário de outro produto. Integrações externas, pagamentos reais, OAuth2, APIs de IA e permissões do servidor dependem das credenciais e configurações reais do ambiente do cliente e precisam de teste final no Discord.
