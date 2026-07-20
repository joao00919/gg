# Guia de backup e restauração

## Backup automático

Configuração:

```env
ZYNEX_AUTOMATIC_BACKUP=true
ZYNEX_BACKUP_DIR=backups
ZYNEX_BACKUP_ROTATION=10
```

`tasks/zynex_operations.py` agenda a rotina operacional. `functions/database_backup.py` gera exportação JSON sanitizada, checksum SHA-256, timestamp e rotação.

## Dados sensíveis

O exportador mascara chaves comuns como token, senha, segredo e API key. O `.env` não é incluído. Na restauração, marcadores sanitizados preservam o segredo já existente na base e não criam credenciais novas. Mesmo assim, trate todo backup como arquivo privado.

## Backup manual em Python

```python
from functions.database_backup import create_database_backup

result = create_database_backup(backup_dir="backups", rotation=10)
print(result)
```

## Validação

```python
from functions.database_backup import validate_database_backup

print(validate_database_backup("backups/NOME_DO_ARQUIVO.json"))
```

A validação verifica estrutura e integridade declarada.

## Restauração

A restauração exige confirmação explícita e cria um backup de segurança antes de substituir dados. Pare todas as instâncias do bot antes de restaurar.

```python
from functions.database_backup import restore_database_backup

restore_database_backup(
    "backups/NOME_DO_ARQUIVO.json",
    confirmation="RESTAURAR",
)
```

## Procedimento recomendado

1. interrompa o bot;
2. copie o banco atual;
3. valide o arquivo de backup;
4. restaure em ambiente de teste;
5. execute `python bot.py --check`;
6. valide produtos, estoque, vendas e configurações;
7. somente então aplique em produção.

## Limitação

O backup lógico protege dados da aplicação, mas não substitui snapshot nativo do MongoDB nem política externa de retenção. Em produção, combine ambos.
