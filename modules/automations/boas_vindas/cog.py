import disnake
from disnake.ext import commands

from functions.emoji import emoji
from functions.message import message, embed_message
from functions.database import database as db
from modules.automations.boas_vindas import helpers


class BoasVindasConfig(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def Painel() -> list[disnake.ui.Container]:
        config = helpers.carregar_config()
        mensagem = config.get("mensagem", "")
        tempo = int(config.get("tempo_segundos", 0) or 0)
        modo = str(config.get("modo_envio", "v1"))
        ativado = bool(config.get("ativado", True))
        rota = str(config.get("rota_envio", "canal"))
        
        instrucoes = (
            "Configure as mensagens e opções de boas-vindas do servidor."
        )
        modo_label = 'Content' if modo == 'v1' else ('Componentes V2' if modo == 'v2' else 'Embed')
        resumo = (
            f"{emoji.on if ativado else emoji.off} **Status:** `{'Ativado' if ativado else 'Desativado'}`\n"
            f"{emoji.edit} **Mensagem atual:**\n`{(mensagem[:350] + '...') if len(mensagem) > 350 else mensagem or 'vazia'}`\n\n"
            f"{emoji.clock} **Duração:** `{tempo}` segundos\n"
            f"{emoji.reload} **Modo de envio:** `{modo_label}`\n"
            f"{emoji.route} **Caminho:** `{'Canal de boas-vindas' if rota == 'canal' else ('Canal de boas-vindas e DM' if rota == 'canal_dm' else 'DM')}`"
        )
        preview_disponivel = bool(mensagem and mensagem.strip())
        
        primary_color_hex = db.get_document("custom_colors").get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Automações > **Boas-Vindas**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay(instrucoes),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.TextDisplay(resumo),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="" if not ativado else "", style=disnake.ButtonStyle.grey, emoji=emoji.power, custom_id="BV_ToggleAtivo"),
                    disnake.ui.Button(label="Editar Mensagem", style=disnake.ButtonStyle.blurple, emoji=emoji.edit, custom_id="BV_EditMensagem", disabled=not ativado),
                    disnake.ui.Button(label="Editar Duração", style=disnake.ButtonStyle.green, emoji=emoji.clock, custom_id="BV_EditTempo", disabled=not ativado),
                ),
                disnake.ui.ActionRow(
                    disnake.ui.Button(label="Prévia", style=disnake.ButtonStyle.grey, emoji=emoji.search, custom_id="BV_Preview", disabled=not preview_disponivel or not ativado),
                    disnake.ui.Button(label="Trocar Estilo", style=disnake.ButtonStyle.grey, emoji=emoji.reload, custom_id="BV_AbrirModo", disabled=not ativado),
                    disnake.ui.Button(label="Mudar Caminho", style=disnake.ButtonStyle.grey, emoji=emoji.route, custom_id="BV_AbrirRota", disabled=not ativado),
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="VoltarAutomações"),
            ),
        ]

    @staticmethod
    def PainelEmbed() -> tuple[disnake.Embed, list[disnake.ui.ActionRow]]:
        config = helpers.carregar_config()
        mensagem = config.get("mensagem", "")
        tempo = int(config.get("tempo_segundos", 0) or 0)
        modo = str(config.get("modo_envio", "v1"))
        ativado = bool(config.get("ativado", True))
        rota = str(config.get("rota_envio", "canal"))
        
        modo_label = 'Content' if modo == 'v1' else ('Componentes V2' if modo == 'v2' else 'Embed')
        resumo = (
            f"{emoji.on if ativado else emoji.off} **Status:** `{'Ativado' if ativado else 'Desativado'}`\n"
            f"{emoji.clock} **Duração:** `{tempo}` segundos\n"
            f"{emoji.reload} **Modo de envio:** `{modo_label}`\n"
            f"{emoji.route} **Caminho:** `{'Canal de boas-vindas' if rota == 'canal' else ('Canal de boas-vindas e DM' if rota == 'canal_dm' else 'DM')}`"
        )
        mensagem_resumo = (mensagem[:350] + '...') if len(mensagem) > 350 else (mensagem or 'vazia')
        preview_disponivel = bool(mensagem and mensagem.strip())

        primary_color_hex = db.get_document("custom_colors").get("primary")
        embed = disnake.Embed(
            title=f"Boas-Vindas",
            description="Configure as mensagens e opções de boas-vindas do servidor."
        )
        if primary_color_hex:
            embed.color = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))
        
        embed.add_field(name="Configurações", value=resumo, inline=False)
        embed.add_field(name="Mensagem Atual", value=f"```{mensagem_resumo}```", inline=False)

        components = [
            disnake.ui.ActionRow(
                disnake.ui.Button(label="", style=disnake.ButtonStyle.grey, emoji=emoji.power, custom_id="BV_ToggleAtivo"),
                disnake.ui.Button(label="Editar Mensagem", style=disnake.ButtonStyle.blurple, emoji=emoji.edit, custom_id="BV_EditMensagem", disabled=not ativado),
                disnake.ui.Button(label="Editar Duração", style=disnake.ButtonStyle.green, emoji=emoji.clock, custom_id="BV_EditTempo", disabled=not ativado),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Prévia", style=disnake.ButtonStyle.grey, emoji=emoji.search, custom_id="BV_Preview", disabled=not preview_disponivel or not ativado),
                disnake.ui.Button(label="Trocar Estilo", style=disnake.ButtonStyle.grey, emoji=emoji.reload, custom_id="BV_AbrirModo", disabled=not ativado),
                disnake.ui.Button(label="Mudar Caminho", style=disnake.ButtonStyle.grey, emoji=emoji.route, custom_id="BV_AbrirRota", disabled=not ativado),
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="VoltarAutomações"),
            ),
        ]
        return embed, components

    @staticmethod
    def PainelSelecionarRota() -> list[disnake.ui.Container]:
        primary_color_hex = db.get_document("custom_colors").get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)
        cfg = helpers.carregar_config()
        rota_atual = str(cfg.get("rota_envio", "canal"))
        caminho_options = [
            disnake.SelectOption(label="Canal", value="canal", description="Enviar no canal de boas-vindas", default=(rota_atual in ("canal", "canal_dm"))),
            disnake.SelectOption(label="DM", value="dm", description="Enviar por mensagem direta", default=(rota_atual in ("dm", "canal_dm"))),
        ]
        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Automações > Boas-Vindas > **Selecionar Caminho**"),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(
                    disnake.ui.StringSelect(
                        custom_id="BV_SelectRota",
                        placeholder="Escolha o(s) caminho(s): Canal e/ou DM",
                        options=caminho_options,
                        min_values=1,
                        max_values=2,
                    )
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="BV_VoltarPainelBV"),
            ),
        ]

    @staticmethod
    def PainelSelecionarRotaEmbed() -> tuple[disnake.Embed, list[disnake.ui.ActionRow]]:
        cfg = helpers.carregar_config()
        rota_atual = str(cfg.get("rota_envio", "canal"))
        caminho_options = [
            disnake.SelectOption(label="Canal", value="canal", description="Enviar no canal de boas-vindas", default=(rota_atual in ("canal", "canal_dm"))),
            disnake.SelectOption(label="DM", value="dm", description="Enviar por mensagem direta", default=(rota_atual in ("dm", "canal_dm"))),
        ]
        
        primary_color_hex = db.get_document("custom_colors").get("primary")
        embed = disnake.Embed(
            title=f"Selecionar Caminho",
            description="Escolha onde as mensagens de boas-vindas serão enviadas."
        )
        if primary_color_hex:
            embed.color = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))

        components = [
            disnake.ui.ActionRow(
                disnake.ui.StringSelect(
                    custom_id="BV_SelectRota",
                    placeholder="Escolha o(s) caminho(s): Canal e/ou DM",
                    options=caminho_options,
                    min_values=1,
                    max_values=2,
                )
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="BV_VoltarPainelBV"),
            ),
        ]
        return embed, components

    @staticmethod
    def PainelSelecionarModo() -> list[disnake.ui.Container]:
        primary_color_hex = db.get_document("custom_colors").get("primary")
        container_kwargs = {}
        if primary_color_hex:
            primary_color = int(primary_color_hex.replace("#", ""), 16)
            container_kwargs["accent_colour"] = disnake.Colour(primary_color)
        cfg = helpers.carregar_config()
        modo = str(cfg.get("modo_envio", "v1"))
        modo_options = [
            disnake.SelectOption(label="Content", value="v1", default=(modo == "v1")),
            disnake.SelectOption(label="Componentes V2", value="v2", default=(modo == "v2")),
            disnake.SelectOption(label="Embed", value="embed", default=(modo == "embed")),
        ]
        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Automações > Boas-Vindas > **Selecionar Estilo**"),
                disnake.ui.Separator(spacing=disnake.SeparatorSpacing.small),
                disnake.ui.ActionRow(
                    disnake.ui.StringSelect(
                        custom_id="BV_SelectModo",
                        placeholder="Escolha o modo de envio",
                        options=modo_options,
                        min_values=1,
                        max_values=1,
                    )
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="BV_VoltarPainelBV"),
            ),
        ]

    @staticmethod
    def PainelSelecionarModoEmbed() -> tuple[disnake.Embed, list[disnake.ui.ActionRow]]:
        cfg = helpers.carregar_config()
        modo = str(cfg.get("modo_envio", "v1"))
        modo_options = [
            disnake.SelectOption(label="Content", value="v1", default=(modo == "v1")),
            disnake.SelectOption(label="Componentes V2", value="v2", default=(modo == "v2")),
            disnake.SelectOption(label="Embed", value="embed", default=(modo == "embed")),
        ]
        
        primary_color_hex = db.get_document("custom_colors").get("primary")
        embed = disnake.Embed(
            title=f"Selecionar Estilo",
            description="Escolha o formato da mensagem de boas-vindas."
        )
        if primary_color_hex:
            embed.color = disnake.Colour(int(primary_color_hex.replace("#", ""), 16))

        components = [
            disnake.ui.ActionRow(
                disnake.ui.StringSelect(
                    custom_id="BV_SelectModo",
                    placeholder="Escolha o modo de envio",
                    options=modo_options,
                    min_values=1,
                    max_values=1,
                )
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="BV_VoltarPainelBV"),
            ),
        ]
        return embed, components

    @commands.Cog.listener("on_button_click")
    async def BoasVindas_Button_Listener(self, inter: disnake.MessageInteraction):
        cid = inter.component.custom_id
        if not cid or not cid.startswith("BV_"):
            return

        if cid == "BV_EditMensagem":
            cfg = helpers.carregar_config()
            await inter.response.send_modal(EditarMensagemBVModal(str(cfg.get("modo_envio", "v1"))))
        elif cid == "BV_EditTempo":
            cfg = helpers.carregar_config()
            await inter.response.send_modal(EditarTempoBVModal(valor_atual=int(cfg.get("tempo_segundos", 0) or 0)))
        elif cid == "BV_Preview":
            await self._handle_preview(inter)
        elif cid == "BV_ToggleAtivo":
            cfg = helpers.carregar_config()
            novo = not bool(cfg.get("ativado", True))
            helpers.salvar_config({"ativado": novo})
            await self._update_panel(inter)
        elif cid in ("BV_AbrirRota", "BV_AbrirModo", "BV_VoltarPainelBV"):
            await self._update_panel(inter)

    async def _handle_preview(self, inter: disnake.MessageInteraction):
        cfg = helpers.carregar_config()
        mensagem = cfg.get("mensagem", "")
        if not mensagem or not mensagem.strip():
            await inter.response.send_message("Configure a mensagem antes de visualizar a prévia.", ephemeral=True)
            return
        
        membro_preview = inter.author if isinstance(inter.author, disnake.Member) else inter.guild.me
        conteudo = helpers.formatar_mensagem(mensagem, membro_preview)
        modo = str(cfg.get("modo_envio", "v1"))

        try:
            if modo == 'v2':
                await inter.response.send_message(
                    components=[helpers.montar_container_preview(conteudo, cfg), helpers.system_badge_row()],
                    flags=disnake.MessageFlags(is_components_v2=True),
                    ephemeral=True
                )
            elif modo == 'embed':
                embed = helpers.montar_embed_preview(conteudo, cfg)
                await inter.response.send_message(embed=embed, components=[helpers.system_badge_row()], ephemeral=True)
            else:
                kwargs = {"content": conteudo, "components": [helpers.system_badge_row()]}
                file = await helpers.baixar_imagem(cfg.get("v1_imagem_url"))
                if file:
                    kwargs["file"] = file
                await inter.response.send_message(**kwargs, ephemeral=True)
        except Exception:
            pass # Silencia erros de prévia

    async def _update_panel(self, inter: disnake.Interaction):
        if not inter.response.is_done():
            await inter.response.defer(with_message=False)
        
        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            await embed_message.wait(inter, send=False)
        else:
            await message.wait(inter, send=False)
        
        cid = ""
        if isinstance(inter, disnake.MessageInteraction):
            cid = inter.component.custom_id
        
        if mode == "embed":
            if cid == "BV_AbrirRota":
                embed, components = self.PainelSelecionarRotaEmbed()
            elif cid == "BV_AbrirModo":
                embed, components = self.PainelSelecionarModoEmbed()
            else: # Voltar, Toggle ou vindo de um Modal
                embed, components = self.PainelEmbed()
            await inter.edit_original_message(content=None, embed=embed, components=components)
        else:
            if cid == "BV_AbrirRota":
                components = self.PainelSelecionarRota()
            elif cid == "BV_AbrirModo":
                components = self.PainelSelecionarModo()
            else: # Voltar, Toggle ou vindo de um Modal
                components = self.Painel()
            await inter.edit_original_message(content=None, components=components)

    @commands.Cog.listener("on_dropdown")
    async def BoasVindas_Dropdown_Listener(self, inter: disnake.MessageInteraction):
        cid = inter.data.custom_id
        if not cid or not cid.startswith("BV_"):
            return

        if cid == "BV_SelectRota":
            valores = list(inter.values or [])
            if not valores:
                valores = ["canal"]
            
            if "canal" in valores and "dm" in valores:
                rota = "canal_dm"
            elif "dm" in valores:
                rota = "dm"
            else:
                rota = "canal"
            helpers.salvar_config({"rota_envio": rota})
        
        elif cid == "BV_SelectModo":
            modo = (inter.values or ["v1"])[0]
            if modo in ("v1", "v2", "embed"):
                helpers.salvar_config({"modo_envio": modo, "usar_componentes_v2": (modo == "v2")})
        
        await self._update_panel(inter)

class EditarMensagemBVModal(disnake.ui.Modal):
    def __init__(self, modo: str):
        cfg = helpers.carregar_config()
        modo = str(modo or cfg.get("modo_envio", "v1"))
        base_inputs = [
            disnake.ui.TextInput(
                label="Mensagem de boas-vindas (Obrigatório)",
                placeholder="Use {user}, {nameserver}, {nameuser}, {servercount}",
                value=str(cfg.get("mensagem", ""))[:4000],
                custom_id="mensagem",
                style=disnake.TextInputStyle.paragraph,
                required=True,
            )
        ]
        
        if modo == 'v2':
            inputs = base_inputs + [
                disnake.ui.TextInput(label="Imagem URL (Opcional)", placeholder="https://...", value=str(cfg.get("v2_imagem_url", ""))[:4000], custom_id="v2_imagem_url", style=disnake.TextInputStyle.short, required=False),
                disnake.ui.TextInput(label="Cor do Container (Opcional) - hex #RRGGBB", placeholder="#5865F2", value=str(cfg.get("v2_cor_container", ""))[:16], custom_id="v2_cor_container", style=disnake.TextInputStyle.short, required=False),
            ]
            titulo = "Editar Mensagem (Componentes)"
        elif modo == 'embed':
            inputs = base_inputs + [
                disnake.ui.TextInput(label="Título (Opcional)", placeholder="Ex: Bem-vindo(a)!", value=str(cfg.get("embed_titulo", ""))[:256], custom_id="embed_titulo", style=disnake.TextInputStyle.short, required=False),
                disnake.ui.TextInput(label="Banner URL (Opcional)", placeholder="https://...", value=str(cfg.get("embed_banner_url", ""))[:4000], custom_id="embed_banner_url", style=disnake.TextInputStyle.short, required=False),
                disnake.ui.TextInput(label="Thumbnail URL (Opcional)", placeholder="https://...", value=str(cfg.get("embed_thumb_url", ""))[:4000], custom_id="embed_thumb_url", style=disnake.TextInputStyle.short, required=False),
                disnake.ui.TextInput(label="Cor do Embed (Opcional) - hex #RRGGBB", placeholder="#5865F2", value=str(cfg.get("embed_cor", ""))[:16], custom_id="embed_cor", style=disnake.TextInputStyle.short, required=False),
            ]
            titulo = "Editar Mensagem (Embed)"
        else: # v1
            inputs = base_inputs + [
                disnake.ui.TextInput(label="Imagem URL (Opcional)", placeholder="https://... (será enviada junto)", value=str(cfg.get("v1_imagem_url", ""))[:4000], custom_id="v1_imagem_url", style=disnake.TextInputStyle.short, required=False),
            ]
            titulo = "Editar Mensagem (Padrão)"

        super().__init__(title=titulo, custom_id="BV_EditarMensagem_Modal", components=inputs)

    async def callback(self, inter: disnake.ModalInteraction):
        valores = dict(inter.text_values)
        helpers.salvar_config(valores)
        cog = inter.bot.get_cog("BoasVindasConfig")
        if cog:
            await cog._update_panel(inter)

class EditarTempoBVModal(disnake.ui.Modal):
    def __init__(self, valor_atual: int = 0):
        components = [
            disnake.ui.TextInput(
                label="Tempo em segundos (0 = não apagar)",
                placeholder="Ex: 0, 1, 5, 10, 60",
                value=str(int(valor_atual or 0)),
                custom_id="tempo",
                style=disnake.TextInputStyle.short,
                required=True,
            )
        ]
        super().__init__(title="Editar Duração da Mensagem", custom_id="BV_EditarTempo_Modal", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        texto = inter.text_values.get("tempo", "0").strip()
        try:
            valor = int(texto)
            if valor < 0:
                valor = 0
            helpers.salvar_config({"tempo_segundos": valor})
            cog = inter.bot.get_cog("BoasVindasConfig")
            if cog:
                await cog._update_panel(inter)
        except Exception:
            try:
                await inter.response.send_message("Valor inválido para tempo.", ephemeral=True)
            except Exception:
                pass

def setup(bot: commands.Bot):
    bot.add_cog(BoasVindasConfig(bot))
