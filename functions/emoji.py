import logging

from functions.database import database as db

logger = logging.getLogger("zynex.emojis")


# Aliases de compatibilidade. A identidade visual principal do bot agora usa
# o emoji "zenyx2", criado dentro da aplicação Discord de cada cliente.
_EMOJI_ALIASES = {
    "bad": "wrong",
    "error": "wrong",
    "info": "information",
    "mention": "message",
    "perm": "role",
    "sync": "reload",
    "custom_alert": "alert",
    "custom_primary": "announcement",
    "custom_secondary": "announcement2",
    "custom_success": "correct",
    "user": "member",
    "members": "members",
    "role": "role",
    "animated": "loading",
    "name": "textc",
    "py": "robot",
    "url": "website",

    # Identidade global ZENYX2.
    "z0": "zenyx2",
    "logo": "zenyx2",
    "zynx": "zenyx2",
    "sales_logo": "zenyx2",
    "store": "zenyx2",
    "zenyx": "zenyx2",
}

# Fallbacks só são usados durante o primeiro início, antes de a sincronização
# criar os emojis dentro da aplicação do cliente. Nunca gravamos IDs de outro bot.
_EMOJI_FALLBACKS = {
    "zenyx2": "✨",
    "online": "🟢",
    "on": "🟢",
    "off": "⚫",
    "config": "⚙️",
    "termos": "📋",
}

_REQUIRED_EMOJI_KEYS = set(_EMOJI_ALIASES.values()) | set(_EMOJI_FALLBACKS)


def _ensure_required_keys() -> None:
    """Garante que os assets críticos participem da sincronização por aplicação."""
    path = "database/emojis/emojis.json"
    data = db.obter(path) or {}
    changed = False
    for key in sorted(_REQUIRED_EMOJI_KEYS):
        if key not in data:
            data[key] = ""
            changed = True
    # Remove aliases antigos salvos com IDs externos inválidos. Os aliases são
    # resolvidos dinamicamente depois do carregamento.
    for alias in ("z0", "logo", "zynx", "sales_logo"):
        if alias in data:
            data.pop(alias, None)
            changed = True
    if changed:
        db.salvar(path, data)


def _apply_fallbacks(target) -> None:
    for key, fallback in _EMOJI_FALLBACKS.items():
        if not getattr(target, key, None):
            setattr(target, key, fallback)


def _apply_aliases(target) -> None:
    for alias, source in _EMOJI_ALIASES.items():
        value = getattr(target, source, None)
        if value:
            setattr(target, alias, value)


_ensure_required_keys()


class emoji:
    db = db.obter("database/emojis/emojis.json") or {}
    for key, value in db.items():
        locals()[key] = value


_apply_fallbacks(emoji)
_apply_aliases(emoji)




def activate_safe_emoji_fallbacks() -> None:
    """Substitui IDs customizados por Unicode quando a API não puder sincronizar.

    Isso mantém todos os botões, selects e painéis utilizáveis. Na próxima
    inicialização, a sincronização remota tenta restaurar os emojis personalizados.
    """
    try:
        from functions.interaction_runtime import _UNICODE_BY_NAME
    except Exception:
        _UNICODE_BY_NAME = {}
    for key in emoji.db:
        value = getattr(emoji, key, None)
        raw = str(value or "")
        if raw.startswith(("<:", "<a:")) or not raw:
            setattr(emoji, key, _UNICODE_BY_NAME.get(key, "✨"))
    _apply_aliases(emoji)
    logger.warning("Fallback Unicode ativado para a interface do bot.")

def reload_emoji_class():
    """Recarrega os emojis após a sincronização da aplicação Discord."""
    _ensure_required_keys()
    emoji.db = db.obter("database/emojis/emojis.json") or {}
    for key, value in emoji.db.items():
        setattr(emoji, key, value)
    _apply_fallbacks(emoji)
    _apply_aliases(emoji)
    print(f"[Emojis] Classe recarregada com {len(emoji.db)} emojis")


def init_on_startup(bot_token: str, app_id: str) -> None:
    """Sincroniza os emojis dentro da aplicação Discord de cada cliente.

    Cada aplicação recebe seus próprios IDs. Isso evita o problema de emojis
    invisíveis quando o pacote é instalado em outro bot.
    """
    print("[Emojis] Verificando identidade ZENYX2 e emojis da aplicação...")

    from functions.emojis import emojis as Emojis

    emoji_manager = Emojis(bot_token, app_id)
    if emoji_manager.needs_sync():
        print(f"[Emojis] Sincronização necessária: {len(emoji_manager.emojis_db)} emojis.")
        # Reutiliza o event loop principal preparado pelo bot. Usar asyncio.run()
        # aqui fecharia o loop atual e faria extensões/tasks falharem no Python 3.12+.
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            raise RuntimeError(
                "A sincronização inicial de emojis deve ocorrer antes de iniciar o bot."
            )
        try:
            loop.run_until_complete(emoji_manager.sync_all_async())
            reload_emoji_class()
        except Exception:
            # O bot continua operacional com fallback Unicode. O erro permanece
            # visível no console para que token/permissões sejam corrigidos.
            logger.exception(
                "Não foi possível sincronizar os emojis personalizados. "
                "Os painéis usarão emojis seguros até a próxima inicialização."
            )
            activate_safe_emoji_fallbacks()
    else:
        print("[Emojis] Emojis desta aplicação já estão sincronizados.")
