import disnake
from disnake.ext import commands, tasks
from datetime import datetime, timedelta
import pytz

from modules.automations.msg_auto import helpers
from modules.automations.msg_auto.cog import MsgAutoCog
from commands.admin.anunciar.builder import Builder

class MsgAutoTask(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.msg_auto_task.is_running():
            self.msg_auto_task.start()

    def cog_unload(self):
        self.msg_auto_task.cancel()

    @tasks.loop(minutes=1)
    async def msg_auto_task(self):
        config = helpers.carregar_config()
        if not config.get("ativado", False):
            return

        agora = datetime.now(pytz.timezone('America/Sao_Paulo'))
        mensagens = config.get("mensagens", {})
        
        for msg_id, msg_data in mensagens.items():
            try:
                channel_id = msg_data.get("channel_id")
                intervalo = msg_data.get("intervalo_minutos")
                ultima_enviada_str = msg_data.get("ultima_enviada")
                editor_data = msg_data.get("editor_data", {})

                if not any(editor_data.get(k) for k in ["content", "embed", "container", "externalImage", "botoes"]):
                    continue

                if not all([channel_id, intervalo]):
                    continue

                ultima_enviada = datetime.fromisoformat(ultima_enviada_str).astimezone(pytz.timezone('America/Sao_Paulo')) if ultima_enviada_str else None

                if ultima_enviada:
                    proximo_envio = ultima_enviada + timedelta(minutes=intervalo)
                    if agora < proximo_envio:
                        continue
                
                canal = self.bot.get_channel(int(channel_id))
                if not canal:
                    continue

                # Apagar mensagem anterior
                last_message_id = msg_data.get("last_message_id")
                if last_message_id:
                    try:
                        old_message = await canal.fetch_message(int(last_message_id))
                        await old_message.delete()
                    except (disnake.NotFound, disnake.Forbidden):
                        pass

                # Montar e enviar a nova mensagem
                data_to_build = editor_data.copy()
                if "botoes" in data_to_build and data_to_build["botoes"]:
                    data_to_build["buttons"] = data_to_build.pop("botoes")
                else:
                    data_to_build["buttons"] = [{
                        "id": "sync_auto_msg_disabled",
                        "label": "Mensagem Automática",
                        "button": {"type": "disabled", "style": "gray"}
                    }]
                
                built_message = await self.bot.loop.run_in_executor(None, Builder.build_from_cfg, {"message": data_to_build})
                new_message = await MsgAutoCog._send_built_message(canal, built_message)

                # Atualizar a configuração com o novo estado
                config = helpers.carregar_config() # Recarrega para evitar race condition
                current_msg_data = config.get("mensagens", {}).get(msg_id)
                if current_msg_data:
                    current_msg_data["ultima_enviada"] = agora.isoformat()
                    if new_message:
                        current_msg_data["last_message_id"] = new_message.id
                    helpers.salvar_config(config)

            except Exception as e:
                continue
    
    @msg_auto_task.before_loop
    async def before_msg_auto_task(self):
        await self.bot.wait_until_ready()

def setup(bot: commands.Bot):
    bot.add_cog(MsgAutoTask(bot))
