import os
import re
import sys
import asyncio
import aiohttp
import json
import hashlib
import logging
from pathlib import Path

from .database import load_emojis, save_emojis
from .upload import upload_emoji_async

logger = logging.getLogger("zynex.emojis")


class emojis:
    DB_PATH = "database/emojis/emojis.json"
    DATA_PATH = "database/emojis/emojis_data.json"
    ASSETS_PATH = "database/emojis/assets"
    BRAND_EMOJI_NAME = "zenyx2"
    BRAND_EMOJI_ID = "1527921690292785272"
    BRAND_EMOJI_URL = (
        f"https://cdn.discordapp.com/emojis/{BRAND_EMOJI_ID}.png"
        "?size=128&quality=lossless"
    )

    def __init__(self, bot_token: str, app_id: str):
        self.bot_token = bot_token
        self.app_id = str(app_id)
        self.emojis_db = load_emojis()
        self._ensure_emojis_structure()
        self.emojis_db = load_emojis()

    @property
    def token_fingerprint(self) -> str:
        return hashlib.sha256(self.bot_token.encode("utf-8")).hexdigest()[:16]

    def _asset_fingerprint(self) -> str:
        parts = []
        assets = Path(self.ASSETS_PATH)
        if assets.exists():
            for path in sorted(assets.iterdir(), key=lambda p: p.name.lower()):
                if path.suffix.lower() not in {".png", ".gif"}:
                    continue
                try:
                    parts.append(f"{path.name}:{path.stat().st_size}")
                except OSError:
                    parts.append(path.name)
        # Inclui o asset remoto mesmo antes do primeiro download.
        parts.append(f"remote:{self.BRAND_EMOJI_NAME}:{self.BRAND_EMOJI_ID}")
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]

    def _load_sync_state(self) -> dict:
        try:
            with open(self.DATA_PATH, "r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _load_emoji_config(self) -> dict:
        try:
            with open("configs/config_emoji.json", "r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _static_catalog_ready(self) -> bool:
        config = self._load_emoji_config()
        if not config.get("isConfigured"):
            return False
        mode = str(config.get("mode", "")).lower()
        owner_application_id = str(config.get("ownerApplicationId") or "")
        use_catalog = mode == "static" or (mode == "auto" and owner_application_id == self.app_id)
        if not use_catalog:
            return False
        # Na aplicação proprietária, os IDs enviados pelo proprietário são a fonte
        # da verdade. Em outra aplicação, os assets são recriados com os mesmos nomes.
        required = ("zenyx2", "online", "on", "off", "config", "cart", "pix", "ticket")
        return all(str(self.emojis_db.get(name) or "").startswith(("<:", "<a:")) for name in required)

    def needs_sync(self) -> bool:
        """Indica se o catálogo deve ser conferido na aplicação atual.

        A verificação remota é ativada por padrão. IDs salvos em um pacote podem
        pertencer a outra aplicação e não são considerados válidos sem a listagem
        oficial da API do Discord.
        """
        verify = os.getenv("VERIFY_APPLICATION_EMOJIS_ON_STARTUP", "true").strip().lower()
        if verify in {"1", "true", "yes", "sim", "on"}:
            return True
        state = self._load_sync_state()
        return (
            state.get("configured") != "True"
            or state.get("tokenFingerprint") != self.token_fingerprint
            or state.get("assetFingerprint") != self._asset_fingerprint()
            or state.get("applicationId") != self.app_id
            or not self.emojis_db.get(self.BRAND_EMOJI_NAME)
        )

    def get(self, name: str) -> str | None:
        return self.emojis_db.get(name)

    def list(self) -> dict:
        return self.emojis_db

    def save(self):
        save_emojis(self.emojis_db)

    def _ensure_emojis_structure(self):
        """Inclui no banco todo asset existente, sem apagar IDs já válidos."""
        os.makedirs(self.ASSETS_PATH, exist_ok=True)
        changed = False
        data = dict(self.emojis_db or {})
        for filename in os.listdir(self.ASSETS_PATH):
            if filename.lower().endswith((".png", ".gif")):
                name = os.path.splitext(filename)[0]
                if name not in data:
                    data[name] = ""
                    changed = True
        if self.BRAND_EMOJI_NAME not in data:
            data[self.BRAND_EMOJI_NAME] = ""
            changed = True
        if changed or not os.path.exists(self.DB_PATH):
            self.emojis_db = data
            self.save()

    async def _ensure_brand_asset(self, session: aiohttp.ClientSession) -> bool:
        path = Path(self.ASSETS_PATH) / f"{self.BRAND_EMOJI_NAME}.png"
        if path.is_file() and path.stat().st_size > 0:
            return True
        try:
            async with session.get(self.BRAND_EMOJI_URL) as response:
                if response.status != 200:
                    print(
                        f"[Emojis] Não foi possível baixar o emoji ZENYX2: HTTP {response.status}"
                    )
                    return False
                content = await response.read()
                if not content:
                    return False
                path.write_bytes(content)
                print("[Emojis] Emoji ZENYX2 baixado para esta aplicação.")
                return True
        except Exception as exc:
            print(f"[Emojis] Falha ao baixar o emoji ZENYX2: {exc}")
            return False

    async def _list_application_emojis(self, session: aiohttp.ClientSession) -> list:
        url = f"https://discord.com/api/v10/applications/{self.app_id}/emojis"
        headers = {"Authorization": f"Bot {self.bot_token}"}
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                payload = await response.json()
                return payload.get("items", [])
            text = await response.text()
            raise RuntimeError(
                f"Falha ao listar emojis da aplicação: HTTP {response.status} - {text[:300]}"
            )

    @staticmethod
    def _tag(name: str, emoji_id: str, animated: bool = False) -> str:
        return f"<{'a' if animated else ''}:{name}:{emoji_id}>"

    async def sync_all_async(self, progress_callback=None):
        # Nunca confia cegamente nos IDs distribuídos no ZIP. Primeiro confirma
        # quais emojis realmente existem na aplicação ligada ao token atual.
        print("[Emojis] Verificando e sincronizando emojis na aplicação atual...")
        connector = aiohttp.TCPConnector(limit=4)
        async with aiohttp.ClientSession(connector=connector) as session:
            await self._ensure_brand_asset(session)
            self._ensure_emojis_structure()
            self.emojis_db = load_emojis()

            existing = await self._list_application_emojis(session)
            by_name = {str(item.get("name")): item for item in existing if item.get("name")}
            total = len(self.emojis_db)
            success = 0
            added = 0

            # Identidade e estados essenciais são sincronizados primeiro para
            # que o menu inicial nunca fique sem logo/indicador online.
            priority_names = ["zenyx2", "online", "on", "off", "config"]
            ordered_names = [name for name in priority_names if name in self.emojis_db]
            ordered_names.extend(
                name for name in sorted(self.emojis_db) if name not in ordered_names
            )

            for index, name in enumerate(ordered_names, start=1):
                item = by_name.get(name)
                if item and item.get("id"):
                    self.emojis_db[name] = self._tag(
                        name, str(item["id"]), bool(item.get("animated", False))
                    )
                    success += 1
                else:
                    gif_path = os.path.join(self.ASSETS_PATH, f"{name}.gif")
                    png_path = os.path.join(self.ASSETS_PATH, f"{name}.png")
                    asset_path = gif_path if os.path.isfile(gif_path) else png_path
                    if not os.path.isfile(asset_path):
                        print(f"[Emojis] Asset ausente: {name}")
                        self.emojis_db[name] = ""
                    else:
                        try:
                            new_id = await upload_emoji_async(
                                session,
                                name,
                                asset_path,
                                self.app_id,
                                self.bot_token,
                            )
                            animated = asset_path.lower().endswith(".gif")
                            self.emojis_db[name] = self._tag(name, str(new_id), animated)
                            by_name[name] = {
                                "id": str(new_id),
                                "name": name,
                                "animated": animated,
                            }
                            success += 1
                            added += 1
                            await asyncio.sleep(0.35)
                        except Exception as exc:
                            print(f"[Emojis] Erro ao criar {name}: {exc}")
                            self.emojis_db[name] = ""

                if progress_callback:
                    progress_callback(success, total)
                if index % 20 == 0:
                    self.save()

        self.save()
        print(
            f"[Emojis] Sincronização concluída: {success}/{total}; novos: {added}."
        )

        if success == total:
            self._save_sync_state()
            print("[Emojis] Todos os emojis estão prontos nesta aplicação.")
            if added > 0:
                print("[Emojis] Reiniciando o bot para carregar os novos IDs...")
                os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            print("[Emojis] Alguns emojis falharam; uma nova tentativa ocorrerá no próximo início.")

        return success, total

    def _save_sync_state(self):
        os.makedirs(os.path.dirname(self.DATA_PATH), exist_ok=True)
        data = {
            "configured": "True",
            "applicationId": self.app_id,
            "tokenFingerprint": self.token_fingerprint,
            "assetFingerprint": self._asset_fingerprint(),
        }
        with open(self.DATA_PATH, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    def sync_all(self, progress_callback=None):
        return asyncio.run(self.sync_all_async(progress_callback))
