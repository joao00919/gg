# Guia de migração

## Objetivo

A migração `001_zynex_applications_no_api_v4` é aditiva. Ela atualiza documentos de configuração e produtos para a estrutura ZYNEX sem apagar registros existentes e sem alterar documentos financeiros.

## Antes da migração

1. pare todas as instâncias do bot;
2. faça backup do banco atual;
3. guarde uma cópia do projeto anterior;
4. valide o `.env`;
5. execute `python bot.py --check`;
6. teste em uma cópia do banco quando possível.

## Execução

A migração é executada na inicialização por `migrations/zynex_no_api.py`. Com:

```env
ZYNEX_MIGRATION_BACKUP=true
```

um backup lógico é criado antes da alteração.

## Campos aditivos principais

Produtos antigos recebem valores padrão compatíveis para:

- `internal_id`;
- `active`;
- `product_type`;
- avaliações;
- promoção;
- auditoria;
- timestamps ISO;
- preferências de exibição.

Também são inicializados documentos de suporte para auditoria, alertas, relatórios, fidelidade, avaliações e promoções.

## Proteções

- nenhuma exclusão de coleção/tabela;
- nenhuma alteração de URL ou variável do gateway;
- documentos de pagamento não são modificados;
- migração identificada para evitar reaplicação destrutiva;
- defaults compatíveis com produtos antigos.

## Retorno operacional

Caso a inicialização apresente problema:

1. pare o bot;
2. preserve o banco que apresentou problema para análise;
3. restaure o backup criado antes da migração;
4. volte ao projeto anterior;
5. revise logs sanitizados antes de tentar novamente.

Não restaure um backup sobre uma base ativa com múltiplas instâncias conectadas.
