# Limitações reais

Esta entrega foi validada localmente e não deve ser interpretada como homologação financeira ou operacional em produção.

## Não executado por ausência de credenciais/ambiente

- conexão real com Discord;
- registro global de comandos na aplicação do usuário;
- pagamento real ou sandbox na conta PurinCash do usuário;
- callback/webhook externo real;
- MongoDB de produção;
- DM real do relatório mensal;
- publicação e sincronização em canais reais;
- carga com múltiplas instâncias distribuídas.

## Funcionalidades com base implementada, mas dependentes do fluxo atual

- resgate de pontos não ganhou um comando público novo, para respeitar a lista exata de comandos;
- avaliação de compra possui persistência e validação, mas sua exposição depende dos painéis/ações pós-entrega já usados pelo servidor;
- ticket relacionado a compra depende dos dados históricos disponíveis na base antiga;
- promoções são configuráveis por campo no painel de produto e validadas no backend, mas não alteram produtos antigos que não possuam campos válidos;
- reserva antecipada de estoque e de cupom continua seguindo a arquitetura original; não foi imposta uma política financeira nova;
- backup lógico não substitui snapshot nativo e armazenamento externo;
- identificadores técnicos antigos permanecem quando necessários à compatibilidade.

## Recomendação de homologação

Use um servidor Discord separado e uma cópia do banco. Teste cada comando, produto, tipo de entrega, cupom, promoção, ticket e provedor de pagamento antes de migrar produção.
