import asyncio
import time
from collections import deque

import disnake
from disnake.ext import commands

from modules.automations.boas_vindas import helpers


class BoasVindasTask(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._send_semaphore = asyncio.Semaphore(10)
        self._dm_semaphore = asyncio.Semaphore(3)
        self._dm_lock = asyncio.Lock()
        self._dm_window_seconds = 60
        self._dm_max_per_window = 20
        self._dm_timestamps = deque()

    async def _try_acquire_dm_slot(self) -> bool:
        """Verifica e adquire um slot para envio de DM, respeitando os limites."""
        agora = time.time()
        async with self._dm_lock:
            while self._dm_timestamps and (agora - self._dm_timestamps[0]) > self._dm_window_seconds:
                self._dm_timestamps.popleft()
            if len(self._dm_timestamps) >= self._dm_max_per_window:
                return False
            self._dm_timestamps.append(agora)
            return True

    async def _enviar_dm_boas_vindas(self, member: disnake.Member, conteudo: str, config: dict) -> None:
        """Envia a mensagem de boas-vindas na DM do membro."""
        if not member:
            return
        try:
            dm = await member.create_dm()
        except Exception:
            return
        modo = str(config.get("modo_envio", "v1"))
        try:
            if modo == 'v2':
                container = helpers.montar_container_preview(conteudo, config)
                await dm.send(components=[container, helpers.system_badge_row()], flags=disnake.MessageFlags(is_components_v2=True))
            elif modo == 'embed':
                embed = helpers.montar_embed_preview(conteudo, config)
                await dm.send(embed=embed, components=[helpers.system_badge_row()])
            else:
                file = await helpers.baixar_imagem(config.get("v1_imagem_url"))
                if file:
                    await dm.send(content=conteudo, file=file, components=[helpers.system_badge_row()])
                else:
                    await dm.send(content=conteudo, components=[helpers.system_badge_row()])
        except Exception:
            return

    async def _enviar_boas_vindas(self, member: disnake.Member) -> None:
        """Lida com o envio da mensagem de boas-vindas no canal e/ou DM."""
        if not member or not getattr(member, "guild", None):
            return
        
        config = helpers.carregar_config()
        if not bool(config.get("ativado", True)):
            return
            
        conteudo = helpers.formatar_mensagem(config.get("mensagem", ""), member)
        if not conteudo:
            return

        rota = str(config.get("rota_envio", "canal"))
        
        # Enviar no canal
        if rota in ("canal", "canal_dm"):
            canal = helpers.obter_canal_boas_vindas(member.guild)
            if canal:
                async with self._send_semaphore:
                    tentativa = 0
                    while tentativa < 3:
                        try:
                            modo = str(config.get("modo_envio", "v1"))
                            msg = None
                            if modo == "v2":
                                container = helpers.montar_container_preview(conteudo, config)
                                msg = await canal.send(
                                    components=[container, helpers.system_badge_row()],
                                    flags=disnake.MessageFlags(is_components_v2=True),
                                )
                            elif modo == "embed":
                                embed = helpers.montar_embed_preview(conteudo, config)
                                msg = await canal.send(embed=embed, components=[helpers.system_badge_row()])
                            else: # v1
                                file = await helpers.baixar_imagem(config.get("v1_imagem_url"))
                                if file:
                                    msg = await canal.send(content=conteudo, file=file, components=[helpers.system_badge_row()])
                                else:
                                    msg = await canal.send(content=conteudo, components=[helpers.system_badge_row()])
                            
                            tempo = int(config.get("tempo_segundos", 0) or 0)
                            if msg and tempo > 0:
                                async def _apagar_depois(m: disnake.Message, segundos: int):
                                    try:
                                        await asyncio.sleep(max(1, segundos))
                                        await m.delete()
                                    except Exception:
                                        pass
                                asyncio.create_task(_apagar_depois(msg, tempo))
                            break 
                        except Exception:
                            await asyncio.sleep(0.5 * (2 ** tentativa))
                            tentativa += 1
        
        # Enviar por DM
        if rota in ("dm", "canal_dm"):
            if await self._try_acquire_dm_slot():
                async with self._dm_semaphore:
                    await self._enviar_dm_boas_vindas(member, conteudo, config)

    @commands.Cog.listener()
    async def on_member_join(self, member: disnake.Member):
        """Disparado quando um membro entra no servidor."""
        try:
            await self._enviar_boas_vindas(member)
        except Exception:
            return

def setup(bot: commands.Bot):
    bot.add_cog(BoasVindasTask(bot))
