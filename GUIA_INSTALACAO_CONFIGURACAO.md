# Guia de instalação e configuração

## 1. Preparação

Use uma pasta nova e preserve uma cópia do ZIP original, do `.env` e do banco de produção. Python 3.11 ou superior é recomendado.

## 2. Instalação no Windows

```bat
INSTALAR_LOCAL.bat
```

O script cria `.venv`, instala `requirements.txt` e copia `.env.example` para `.env` quando necessário.

Inicialização:

```bat
INICIAR_LOCAL.bat
```

## 3. Instalação em Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python bot.py --check
python bot.py
```

## 4. Discord

Configure no `.env`:

```env
DISCORD_TOKEN=
DISCORD_CLIENT_ID=
DISCORD_TEST_GUILD_ID=
MAIN_GUILD_ID=
BOT_OWNER_IDS=
BOT_ADMIN_IDS=
ALLOW_GUILD_ADMIN=true
```

Durante desenvolvimento, use um servidor de teste. O registro local por guild costuma ser mais rápido que o registro global.

## 5. Banco

### Modo local

```env
STORAGE_DRIVER=local
LOCAL_DATABASE_PATH=data/local_database.json
```

### MongoDB

```env
STORAGE_DRIVER=mongo
MONGO_URL=
MONGO_DATABASE=zynex_sales
MONGO_TIMEOUT_MS=15000
```

### Automático

```env
STORAGE_DRIVER=auto
```

Nesse modo, MongoDB é usado quando `MONGO_URL` está preenchido; caso contrário, o banco JSON local é usado.

## 6. Permissões

- `BOT_OWNER_IDS`: proprietários autorizados, separados por vírgula;
- `BOT_ADMIN_IDS`: administradores adicionais;
- `ALLOW_GUILD_ADMIN=true`: permite administradores do servidor;
- o dono do servidor continua reconhecido pelo sistema atual.

A visibilidade de um botão não substitui a validação no backend.

## 7. Comandos públicos

Mantenha:

```env
ZYNEX_STRICT_COMMAND_SET=true
```

Esse modo garante o conjunto exato solicitado e remove comandos extras do registro público após o carregamento das extensões.

## 8. Operação

```env
ZYNEX_AUTOMATIC_BACKUP=true
ZYNEX_BACKUP_DIR=backups
ZYNEX_BACKUP_ROTATION=10
ZYNEX_MIGRATION_BACKUP=true
ZYNEX_MONTHLY_REPORT=true
OWNER_ID=
```

`OWNER_ID` é usado para o relatório mensal por DM quando configurado.

## 9. Carteira Integrada PurinCash

Configure no `.env`:

```env
PURINCASH_API_KEY=
PURINCASH_API_URL=https://api.purincash.com/v1
PURINCASH_CALLBACK_URL=
PURINCASH_WEBHOOK_SECRET=
PURINCASH_PIX_KEY=
PURINCASH_OPERATION_FEE_PERCENT=0.60
PURINCASH_OPERATION_FEE_FIXED=0.25
```

O botão de definição da Taxa da Loja foi removido do painel **Carteira Integrada**. A chave da API continua global e não é exibida no Discord.

## 10. Verificação

```bash
python bot.py --check
python -m pytest -q
```

Depois, inicie o bot em um servidor de teste e valide manualmente comandos, painéis, produtos, carrinhos, pagamentos e entregas.
