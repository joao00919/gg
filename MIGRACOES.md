# Migrações incluídas

## `001_zynex_applications_no_api_v4`

Arquivo: `migrations/zynex_no_api.py`

Tipo: aditiva e idempotente.

### Ações

- registra a competência da migração;
- cria backup lógico opcional;
- completa o schema de produtos antigos;
- inicializa documentos de auditoria, alertas, relatórios, fidelidade, avaliações e promoções;
- mantém banco, IDs e registros existentes;
- não modifica documentos de pagamento;
- informa `payment_api_changed: false` no resultado.

### Rollback

Não existe rollback destrutivo automático. O rollback operacional é a restauração do backup anterior, conforme `GUIA_BACKUP_RESTAURACAO.md`.
