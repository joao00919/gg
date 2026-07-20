from disnake.ext import commands
import disnake
import json
from pathlib import Path
import aiohttp

from functions.database import database as db
from functions.emoji import emoji
from functions.message import message, embed_message
from functions import plan
from functions.permission_matrix import has_capability


class ConfigurarPagamentos(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def _providers():
        """Provedores que possuem fluxo implementado no bot."""
        return {
            "sync_wallet": ("Carteira Integrada", emoji.wallet),
            "misticpay": ("Mistic Pay", getattr(emoji, "diamond", emoji.pix)),
            "pix_manual": ("Semi-Automático", emoji.pix),
            "mercado_pago": ("Mercado Pago", emoji.mercado_pago),
            "efibank": ("Efi Bank", emoji.efi_bank),
            "pushinpay": ("Pushin Pay", emoji.pushin_pay),
        }

    @staticmethod
    def _providers_by_category():
        return {"pix": ["sync_wallet", "misticpay", "pix_manual", "mercado_pago", "efibank", "pushinpay"]}

    @staticmethod
    def _load_config() -> dict:
        """Carrega configurações de pagamento do database"""
        return db.get_document("payment_configs") or {}

    @classmethod
    def _get_provider_status(cls, key: str, config: dict, pagamentos: dict) -> tuple[bool, bool, str]:
        """Retorna (enabled, configured, status_text) para um provedor"""
        lookup_key = key
        entry = config.get(lookup_key)
        if isinstance(entry, dict):
            enabled = bool(entry.get("enabled", False))
            if key == "mercado_pago":
                configured = bool(entry.get("access_token"))
            elif key == "efibank":
                cert_path = entry.get("cert_file")
                cert_ok = bool(cert_path) and Path(cert_path).exists()
                has_client = bool(entry.get("client_id") or entry.get("client"))
                has_secret = bool(entry.get("client_secret") or entry.get("token"))
                has_pix = bool(entry.get("pix_key"))
                configured = bool(has_client and has_secret and has_pix and cert_ok)
            elif key in {"pagbank", "picpay", "pushinpay", "asaas", "stripe", "coinbase", "nowpayments"}:
                token_key = {
                    "pagbank": "token_pagbank",
                    "picpay": "token_picpay",
                    "pushinpay": "token_pushinpay",
                    "asaas": "token_asaas",
                    "stripe": "token_stripe",
                    "coinbase": "token_coinbase",
                    "nowpayments": "token_nowpayments",
                }[key]
                configured = bool(entry.get(token_key))
            elif key == "paypal":
                configured = bool(entry.get("client_id") and entry.get("client_secret"))
            elif key == "misticpay":
                configured = bool(entry.get("client_id") and entry.get("client_secret"))
            elif key == "pix_manual":
                configured = bool(entry.get("pix_key") and entry.get("pix_key_type"))
            elif key == "sync_wallet":
                from functions.payments.sync_wallet import global_wallet_is_configured
                configured = global_wallet_is_configured()
            else:
                configured = False
        elif isinstance(entry, bool):
            enabled = entry
            configured = False
        else:
            enabled = bool(pagamentos.get(lookup_key, False))
            configured = False
        
        if enabled:
            status_text = "Ativado"
        elif configured:
            status_text = "Desativado"
        else:
            status_text = "Não Configurado"
        
        return enabled, configured, status_text

    @classmethod
    def categoria_pagamentos_components(cls, inter: disnake.MessageInteraction) -> list[disnake.ui.Container]:
        """Abre diretamente a lista de formas de pagamento, como na interface de referência."""
        return cls.pagamentos_components(inter, "pix")

    @classmethod
    def categoria_pagamentos_embed(cls, inter: disnake.MessageInteraction):
        return cls.pagamentos_embed(inter, "pix")

    @classmethod
    def pagamentos_components(cls, inter: disnake.MessageInteraction, categoria: str = "pix") -> list[disnake.ui.Container]:
        pagamentos = db.get_document("pagamentos") or {}
        config = cls._load_config()
        colors = db.get_document("custom_colors") or {}
        container_kwargs = {}
        if colors.get("primary"):
            container_kwargs["accent_colour"] = disnake.Colour(int(colors["primary"].replace("#", ""), 16))

        options = []
        for key in cls._providers_by_category().get("pix", []):
            label, icon = cls._providers()[key]
            enabled, configured, status_text = cls._get_provider_status(key, config, pagamentos)
            options.append(disnake.SelectOption(label=label, value=key, emoji=icon, description=f"Status: {status_text}"))

        return [
            disnake.ui.Container(
                disnake.ui.TextDisplay(f"# {emoji.z0}\n-# Painel > Configurações > **Formas de Pagamento**"),
                disnake.ui.Separator(),
                disnake.ui.TextDisplay("Configure as formas de pagamento disponíveis para seus clientes."),
                disnake.ui.Separator(),
                disnake.ui.ActionRow(
                    disnake.ui.StringSelect(
                        custom_id="Configuracoes_Pagamentos_Select:pix",
                        placeholder="Selecione uma forma de pagamento",
                        options=options,
                    )
                ),
                **container_kwargs,
            ),
            disnake.ui.ActionRow(
                disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Painel_Configuracoes")
            ),
        ]

    @classmethod
    def pagamentos_embed(cls, inter: disnake.MessageInteraction, categoria: str = "pix"):
        pagamentos = db.get_document("pagamentos") or {}
        config = cls._load_config()
        colors = db.get_document("custom_colors") or {}
        embed = disnake.Embed(
            title="Formas de Pagamento",
            description="Configure as formas de pagamento disponíveis para seus clientes.",
        )
        if colors.get("primary"):
            embed.color = int(colors["primary"].replace("#", ""), 16)
        options = []
        for key in cls._providers_by_category().get("pix", []):
            label, icon = cls._providers()[key]
            enabled, configured, status_text = cls._get_provider_status(key, config, pagamentos)
            options.append(disnake.SelectOption(label=label, value=key, emoji=icon, description=f"Status: {status_text}"))
        components = [
            disnake.ui.ActionRow(disnake.ui.StringSelect(custom_id="Configuracoes_Pagamentos_Select:pix", placeholder="Selecione uma forma de pagamento", options=options)),
            disnake.ui.ActionRow(disnake.ui.Button(label="Voltar", style=disnake.ButtonStyle.grey, emoji=emoji.back, custom_id="Painel_Configuracoes")),
        ]
        return embed, components

    async def display_payments_panel(self, inter: disnake.MessageInteraction):
        mode = db.get_document("custom_mode").get("mode")

        if mode == "embed":
            await embed_message.wait(inter)
            embed, components = self.categoria_pagamentos_embed(inter)
            await inter.edit_original_message(content=None, embed=embed, components=components)
        else:
            await message.wait(inter)
            await inter.edit_original_message(components=self.categoria_pagamentos_components(inter))

    @commands.Cog.listener("on_button_click")
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id == "Configuracoes_Pagamentos":
            mode = db.get_document("custom_mode").get("mode")
            if mode == "embed":
                await embed_message.wait(inter, send=False)
                embed, components = self.categoria_pagamentos_embed(inter)
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await message.wait(inter, send=False)
                await inter.edit_original_message(components=self.categoria_pagamentos_components(inter))
        

    @commands.Cog.listener("on_dropdown")
    async def on_dropdown(self, inter: disnake.MessageInteraction):
        # Seleção de categoria
        if inter.component.custom_id == "Configuracoes_Pagamentos_Categoria_Select":
            categoria = inter.values[0]
            mode = db.get_document("custom_mode").get("mode")
            
            if mode == "embed":
                await embed_message.wait(inter, send=False)
                embed, components = self.pagamentos_embed(inter, categoria)
                await inter.edit_original_message(content=None, embed=embed, components=components)
            else:
                await message.wait(inter, send=False)
                await inter.edit_original_message(components=self.pagamentos_components(inter, categoria))
        
        # Seleção de provedor (pode ter categoria no custom_id)
        elif inter.component.custom_id.startswith("Configuracoes_Pagamentos_Select"):
            # Extrair categoria do custom_id se existir
            parts = inter.component.custom_id.split(":")
            categoria = parts[1] if len(parts) > 1 else None
            key = inter.values[0]
            
            if not has_capability(inter, "payments"):
                await inter.response.send_message(
                    f"{emoji.wrong} Você não possui permissão para gerenciar pagamentos.",
                    ephemeral=True,
                )
                return

            if key == "sync_wallet":
                await inter.response.defer()
                from .wallet_panel import GlobalWalletPanel
                await GlobalWalletPanel.edit(inter, display_name="Carteira Integrada", prefix="GlobalWallet")
                return

            # Verificar se o plano permite este provedor
            if not plan.should_allow_payment_provider(key):
                await inter.response.send_message(
                    f"{emoji.wrong} Este provedor não está disponível no plano atual.\n"
                    f"{emoji.arrow} Use o **PIX Manual**, que pode ser configurado diretamente neste painel.",
                    ephemeral=True
                )
                return
            
            await inter.response.send_modal(PaymentProviderModal(key, categoria))


class PaymentProviderModal(disnake.ui.Modal):
    def __init__(self, provider_key: str, categoria: str = None):
        self.provider_key = provider_key
        self.categoria = categoria

        config = ConfigurarPagamentos._load_config()
        entry = config.get(provider_key) or {}
        if isinstance(entry, bool):
            entry = {"enabled": bool(entry)}

        enabled = bool(entry.get("enabled", False))

        providers_dict = ConfigurarPagamentos._providers()
        label = providers_dict.get(provider_key, (provider_key.capitalize(), ""))[0]

        components = [
            disnake.ui.Label(
                text="Status do provedor",
                component=disnake.ui.StringSelect(
                    placeholder="Ativar ou desativar",
                    custom_id="payment_status",
                    required=True,
                    options=[
                        disnake.SelectOption(label="Ativado", description="O provedor ficará ativado",emoji=emoji.on , value="enabled_True", default=enabled),
                        disnake.SelectOption(label="Desativado", description="O provedor ficará desativado", emoji=emoji.off, value="enabled_False", default=not enabled),
                    ],
                ),
                description="Define se o provedor estará ativo.",
            ),
        ]

        if provider_key == "mercado_pago":
            components.append(
                disnake.ui.Label(
                    text="Token Access",
                    component=disnake.ui.TextInput(
                        placeholder="Cole o Access Token do MercadoPago",
                        custom_id="mercado_pago_access_token",
                        style=disnake.TextInputStyle.short,
                        required=False,
                        value=str(entry.get("access_token") or ""),
                    ),
                    description="Access Token da sua conta Mercado Pago.",
                )
            )
        elif provider_key == "efibank":
            components.append(
                disnake.ui.Label(
                    text="Client ID",
                    component=disnake.ui.TextInput(
                        placeholder="Informe o Client ID da Efi",
                        custom_id="efibank_client_id",
                        style=disnake.TextInputStyle.short,
                        required=False,
                        value=str(entry.get("client_id") or entry.get("client") or ""),
                    ),
                    description="Identificador do cliente (Client ID).",
                )
            )
            components.append(
                disnake.ui.Label(
                    text="Client Secret",
                    component=disnake.ui.TextInput(
                        placeholder="Informe o Client Secret da Efi",
                        custom_id="efibank_client_secret",
                        style=disnake.TextInputStyle.short,
                        required=False,
                        value=str(entry.get("client_secret") or entry.get("token") or ""),
                    ),
                    description="Segredo do cliente (Client Secret).",
                )
            )
            components.append(
                disnake.ui.Label(
                    text="Chave Pix Aleatória",
                    component=disnake.ui.TextInput(
                        placeholder="Informe a Chave Pix Aleatória",
                        custom_id="efibank_pix_key",
                        style=disnake.TextInputStyle.short,
                        required=False,
                        value=str(entry.get("pix_key") or ""),
                    ),
                    description="Sua chave Pix aleatória cadastrada na Efi.",
                )
            )
            # Adicionar campo de upload de arquivo para o certificado .p12
            cert_path = entry.get("cert_file")
            cert_exists = bool(cert_path) and Path(cert_path).exists()
            components.append(
                disnake.ui.Label(
                    text="Certificado .p12",
                    component=disnake.ui.FileUpload(
                        custom_id="efibank_cert_file",
                        required=False,
                    ),
                    description="Envie o arquivo de certificado .p12 da Efi. Deixe vazio para manter o atual." if cert_exists else "Envie o arquivo de certificado .p12 da Efi.",
                )
            )
        elif provider_key == "pagbank":
            components.append(
                disnake.ui.Label(
                    text="Token PagBank",
                    component=disnake.ui.TextInput(
                        placeholder="Informe o token do PagBank",
                        custom_id="pagbank_token",
                        style=disnake.TextInputStyle.short,
                        required=False,
                        value=str(entry.get("token_pagbank") or ""),
                    ),
                    description="Token de API do PagBank.",
                )
            )
        elif provider_key == "picpay":
            components.append(
                disnake.ui.Label(
                    text="Token PicPay",
                    component=disnake.ui.TextInput(
                        placeholder="Informe o token do PicPay",
                        custom_id="picpay_token",
                        style=disnake.TextInputStyle.short,
                        required=False,
                        value=str(entry.get("token_picpay") or ""),
                    ),
                    description="Token de API do PicPay.",
                )
            )
        elif provider_key == "pushinpay":
            components.append(
                disnake.ui.Label(
                    text="Token PushinPay",
                    component=disnake.ui.TextInput(
                        placeholder="Informe o token do PushinPay",
                        custom_id="pushinpay_token",
                        style=disnake.TextInputStyle.short,
                        required=False,
                        value=str(entry.get("token_pushinpay") or ""),
                    ),
                    description="Token de API do PushinPay.",
                )
            )
        elif provider_key == "misticpay":
            components.append(
                disnake.ui.Label(
                    text="Client ID",
                    component=disnake.ui.TextInput(
                        placeholder="Informe o Client ID do MisticPay",
                        custom_id="misticpay_client_id",
                        style=disnake.TextInputStyle.short,
                        required=False,
                        value=str(entry.get("client_id") or ""),
                    ),
                    description="Client ID do MisticPay.",
                )
            )
            components.append(
                disnake.ui.Label(
                    text="Client Secret",
                    component=disnake.ui.TextInput(
                        placeholder="Informe o Client Secret do MisticPay",
                        custom_id="misticpay_client_secret",
                        style=disnake.TextInputStyle.short,
                        required=False,
                        value=str(entry.get("client_secret") or ""),
                    ),
                    description="Client Secret do MisticPay.",
                )
            )
        elif provider_key == "asaas":
            components.append(
                disnake.ui.Label(
                    text="Token Asaas",
                    component=disnake.ui.TextInput(
                        placeholder="Informe o token do Asaas",
                        custom_id="asaas_token",
                        style=disnake.TextInputStyle.short,
                        required=False,
                        value=str(entry.get("token_asaas") or ""),
                    ),
                    description="Token de API do Asaas.",
                )
            )
        elif provider_key == "stripe":
            components.append(
                disnake.ui.Label(
                    text="Token Stripe",
                    component=disnake.ui.TextInput(
                        placeholder="Informe o token do Stripe",
                        custom_id="stripe_token",
                        style=disnake.TextInputStyle.short,
                        required=False,
                        value=str(entry.get("token_stripe") or ""),
                    ),
                    description="Token de API do Stripe.",
                )
            )
        elif provider_key == "coinbase":
            components.append(
                disnake.ui.Label(
                    text="Token Coinbase",
                    component=disnake.ui.TextInput(
                        placeholder="Informe o token do Coinbase",
                        custom_id="coinbase_token",
                        style=disnake.TextInputStyle.short,
                        required=False,
                        value=str(entry.get("token_coinbase") or ""),
                    ),
                    description="Token de API do Coinbase.",
                )
            )
        elif provider_key == "nowpayments":
            components.append(
                disnake.ui.Label(
                    text="Token NOWPayments",
                    component=disnake.ui.TextInput(
                        placeholder="Informe o token do NOWPayments",
                        custom_id="nowpayments_token",
                        style=disnake.TextInputStyle.short,
                        required=False,
                        value=str(entry.get("token_nowpayments") or ""),
                    ),
                    description="Token de API do NOWPayments.",
                )
            )
        elif provider_key == "paypal":
            components.append(
                disnake.ui.Label(
                    text="Client ID",
                    component=disnake.ui.TextInput(
                        placeholder="Informe o Client ID do PayPal",
                        custom_id="paypal_client_id",
                        style=disnake.TextInputStyle.short,
                        required=False,
                        value=str(entry.get("client_id") or ""),
                    ),
                    description="Client ID do PayPal.",
                )
            )
            components.append(
                disnake.ui.Label(
                    text="Client Secret",
                    component=disnake.ui.TextInput(
                        placeholder="Informe o Client Secret do PayPal",
                        custom_id="paypal_client_secret",
                        style=disnake.TextInputStyle.short,
                        required=False,
                        value=str(entry.get("client_secret") or ""),
                    ),
                    description="Client Secret do PayPal.",
                )
            )
        elif provider_key == "sync_wallet":
            cover_fee = bool(entry.get("cover_fee", False))
            components.append(
                disnake.ui.Label(
                    text="Responsabilidade da taxa",
                    component=disnake.ui.StringSelect(
                        placeholder="Selecione quem assume a taxa",
                        custom_id="sync_wallet_cover_fee",
                        required=True,
                        options=[
                            disnake.SelectOption(
                                label="Loja assume a taxa",
                                description="A taxa é descontada do valor recebido.",
                                value="false",
                                default=not cover_fee,
                            ),
                            disnake.SelectOption(
                                label="Cliente assume a taxa",
                                description="A taxa é acrescentada ao valor cobrado.",
                                value="true",
                                default=cover_fee,
                            ),
                        ],
                    ),
                    description="A conexão é protegida e gerenciada pelo operador do sistema.",
                )
            )
        elif provider_key == "pix_manual":
            components.append(
                disnake.ui.Label(
                    text="Chave PIX",
                    component=disnake.ui.TextInput(
                        placeholder="Digite sua chave PIX",
                        custom_id="pix_manual_key",
                        style=disnake.TextInputStyle.short,
                        required=False,
                        max_length=50,
                        value=str(entry.get("pix_key") or ""),
                    ),
                    description="Sua chave PIX para receber pagamentos.",
                )
            )
            components.append(
                disnake.ui.Label(
                    text="Tipo da Chave PIX",
                    component=disnake.ui.StringSelect(
                        placeholder="Selecione o tipo da chave",
                        custom_id="pix_manual_key_type",
                        required=False,
                        options=[
                            disnake.SelectOption(label="Email", value="email", emoji=emoji.mail2, default=entry.get("pix_key_type") == "email"),
                            disnake.SelectOption(label="Telefone", value="telefone", emoji=emoji.mobile, default=entry.get("pix_key_type") == "telefone"),
                            disnake.SelectOption(label="CPF", value="cpf", emoji=emoji.member, default=entry.get("pix_key_type") == "cpf"),
                            disnake.SelectOption(label="CNPJ", value="cnpj", emoji=emoji.store, default=entry.get("pix_key_type") == "cnpj"),
                            disnake.SelectOption(label="Aleatória", value="aleatoria", emoji=emoji.link, default=entry.get("pix_key_type") == "aleatoria"),
                        ],
                    ),
                    description="Tipo da chave PIX informada.",
                )
            )

        super().__init__(title=f"Configurar {label}", components=components, custom_id=f"payment_provider_modal:{provider_key}")

    async def callback(self, inter: disnake.ModalInteraction):
        if not has_capability(inter, "payments"):
            return await inter.response.send_message(
                f"{emoji.wrong} Você não possui permissão para gerenciar pagamentos.",
                ephemeral=True,
            )
        # Use the correct wait function based on mode to avoid Components V2 conflicts
        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            await embed_message.wait(inter, send=False)
        else:
            await message.wait(inter)

        valores = inter.resolved_values

        status_value = valores.get("payment_status")
        if isinstance(status_value, (list, tuple)):
            status_value = status_value[0] if status_value else None
        enabled = True if status_value == "enabled_True" else False

        access_token = valores.get("mercado_pago_access_token") if self.provider_key == "mercado_pago" else None
        efibank_client_id = valores.get("efibank_client_id") if self.provider_key == "efibank" else None
        efibank_client_secret = valores.get("efibank_client_secret") if self.provider_key == "efibank" else None
        efibank_pix_key = valores.get("efibank_pix_key") if self.provider_key == "efibank" else None
        efibank_cert_file = None
        cert_path = None  # Inicializar cert_path no escopo correto
        if self.provider_key == "efibank":
            # Processar arquivo de certificado se fornecido
            # Em modais, arquivos são acessados através de resolved_values
            cert_file_value = valores.get("efibank_cert_file")
            if cert_file_value:
                # Pode ser um único arquivo ou uma lista
                if isinstance(cert_file_value, (list, tuple)):
                    efibank_cert_file = cert_file_value[0] if cert_file_value else None
                else:
                    efibank_cert_file = cert_file_value
        pagbank_token = valores.get("pagbank_token") if self.provider_key == "pagbank" else None
        picpay_token = valores.get("picpay_token") if self.provider_key == "picpay" else None
        pushinpay_token = valores.get("pushinpay_token") if self.provider_key == "pushinpay" else None
        misticpay_client_id = valores.get("misticpay_client_id") if self.provider_key == "misticpay" else None
        misticpay_client_secret = valores.get("misticpay_client_secret") if self.provider_key == "misticpay" else None
        asaas_token = valores.get("asaas_token") if self.provider_key == "asaas" else None
        stripe_token = valores.get("stripe_token") if self.provider_key == "stripe" else None
        coinbase_token = valores.get("coinbase_token") if self.provider_key == "coinbase" else None
        nowpayments_token = valores.get("nowpayments_token") if self.provider_key == "nowpayments" else None
        paypal_client_id = valores.get("paypal_client_id") if self.provider_key == "paypal" else None
        paypal_client_secret = valores.get("paypal_client_secret") if self.provider_key == "paypal" else None
        sync_wallet_cover_fee = valores.get("sync_wallet_cover_fee") if self.provider_key == "sync_wallet" else None
        if isinstance(sync_wallet_cover_fee, (list, tuple)):
            sync_wallet_cover_fee = sync_wallet_cover_fee[0] if sync_wallet_cover_fee else None
        pix_manual_key = valores.get("pix_manual_key") if self.provider_key == "pix_manual" else None
        pix_manual_key_type = valores.get("pix_manual_key_type") if self.provider_key == "pix_manual" else None
        if isinstance(pix_manual_key_type, (list, tuple)):
            pix_manual_key_type = pix_manual_key_type[0] if pix_manual_key_type else None
        configured = False
        error_text = None
        
        if self.provider_key == "sync_wallet":
            from functions.payments.sync_wallet import global_wallet_is_configured
            configured = global_wallet_is_configured()
            if enabled and not configured:
                enabled = False
                error_text = (
                    "A Carteira Integrada não está disponível nesta instalação. "
                    "Ative o PIX Manual ou outro provedor já configurado."
                )

        if self.provider_key == "mercado_pago":
            if access_token:
                # Validação via API oficial do Mercado Pago
                try:
                    timeout = aiohttp.ClientTimeout(total=10)
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        headers = {"Authorization": f"Bearer {access_token}"}
                        async with session.get("https://api.mercadopago.com/users/me", headers=headers) as resp:
                            if resp.status == 200:
                                configured = True
                            else:
                                configured = False
                                error_text = "Token do Mercado Pago inválido ou expirado. Não foi possível ativar."
                except Exception:
                    configured = False
                    error_text = "Erro ao validar o token do Mercado Pago. Tente novamente."
            else:
                configured = False
                if enabled:
                    error_text = "Para ativar o Mercado Pago, informe um Access Token válido."
        if self.provider_key == "efibank":
            config = ConfigurarPagamentos._load_config()
            current = config.get(self.provider_key) or {}
            cert_path = current.get("cert_file")
            cert_exists = bool(cert_path) and Path(cert_path).exists()
            
            # Processar arquivo de certificado se fornecido
            if efibank_cert_file:
                try:
                    # Validar que é um arquivo .p12
                    if not efibank_cert_file.filename.lower().endswith(".p12"):
                        error_text = "O arquivo deve ser um certificado .p12"
                        configured = False
                    else:
                        # Salvar o arquivo
                        base_dir = Path(__file__).resolve().parents[3] / "database" / "payments" / "certs" / "efibank"
                        base_dir.mkdir(parents=True, exist_ok=True)
                        save_path = base_dir / f"cert_{inter.author.id}.p12"
                        data = await efibank_cert_file.read()
                        with save_path.open("wb") as fp:
                            fp.write(data)
                        cert_path = str(save_path)
                        cert_exists = True
                except Exception as e:
                    error_text = f"Erro ao processar o certificado: {str(e)}"
                    configured = False
            
            have_client = bool((efibank_client_id or current.get("client_id") or current.get("client")))
            have_secret = bool((efibank_client_secret or current.get("client_secret") or current.get("token")))
            have_pix = bool((efibank_pix_key or current.get("pix_key")))
            configured = bool(have_client and have_secret and have_pix and cert_exists)
            if enabled and not configured:
                enabled = False
                if not error_text:
                    error_text = "Para ativar a Efi, forneça Client ID, Client Secret, Chave Pix e o certificado .p12."

        elif self.provider_key in {"pagbank", "picpay", "pushinpay", "asaas", "stripe", "coinbase", "nowpayments"}:
            existing = ConfigurarPagamentos._load_config().get(self.provider_key) or {}
            token_key = {
                "pagbank": "token_pagbank",
                "picpay": "token_picpay",
                "pushinpay": "token_pushinpay",
                "asaas": "token_asaas",
                "stripe": "token_stripe",
                "coinbase": "token_coinbase",
                "nowpayments": "token_nowpayments",
            }[self.provider_key]
            token_value = {
                "pagbank": pagbank_token,
                "picpay": picpay_token,
                "pushinpay": pushinpay_token,
                "asaas": asaas_token,
                "stripe": stripe_token,
                "coinbase": coinbase_token,
                "nowpayments": nowpayments_token,
            }[self.provider_key]
            configured = bool((token_value is not None and token_value) or existing.get(token_key))
            if enabled and not configured:
                enabled = False
                error_text = "Informe o token para ativar este provedor."

        elif self.provider_key == "paypal":
            existing = ConfigurarPagamentos._load_config().get("paypal") or {}
            have_client = bool(paypal_client_id or existing.get("client_id"))
            have_secret = bool(paypal_client_secret or existing.get("client_secret"))
            configured = bool(have_client and have_secret)
            if enabled and not configured:
                enabled = False
                error_text = "Para ativar o PayPal, informe Client ID e Client Secret."

        elif self.provider_key == "misticpay":
            existing = ConfigurarPagamentos._load_config().get("misticpay") or {}
            have_client = bool(misticpay_client_id or existing.get("client_id"))
            have_secret = bool(misticpay_client_secret or existing.get("client_secret"))
            configured = bool(have_client and have_secret)
            
            # Se tem credenciais e está sendo ativado, validar com a API
            if enabled and configured:
                try:
                    from functions.payments.misticpay import create_misticpay_payment
                    import uuid
                    
                    # Usar credenciais novas ou existentes
                    client_id = misticpay_client_id or existing.get("client_id")
                    client_secret = misticpay_client_secret or existing.get("client_secret")
                    
                    # Tentar criar um pagamento de teste (valor mínimo)
                    try:
                        await create_misticpay_payment(
                            client_id=client_id,
                            client_secret=client_secret,
                            amount=1.0,  # Valor mínimo para teste
                            payer_name="Teste",
                            payer_document="12345678901",
                            description="Teste de configuração",
                            transaction_id=str(uuid.uuid4())
                        )
                        # Se chegou aqui, as credenciais estão válidas
                        configured = True
                    except RuntimeError as e:
                        error_msg = str(e)
                        # Verificar se é erro de IP não autorizado
                        if "IP não autorizado" in error_msg or "não está na lista de permissões" in error_msg or "IP" in error_msg and "permissões" in error_msg:
                            configured = False
                            enabled = False
                            
                            error_text = (
                                f"{emoji.wrong} **IP não autorizado**\n"
                                f"**Para resolver:**\n"
                                f"1. Ative a verificação de 2 fatores na sua conta MisticPay\n"
                                f"2. Libere todos os IPs nas configurações de segurança\n"
                                f"Após configurar, tente novamente."
                            )
                        else:
                            # Outro erro, mas as credenciais podem estar corretas
                            # Não bloquear a ativação, apenas avisar
                            configured = True  # Permitir ativar mesmo com erro (pode ser temporário)
                    except Exception as e:
                        # Erro inesperado, não bloquear
                        configured = True
                except Exception as e:
                    # Erro ao importar ou validar, não bloquear
                    configured = True
            
            if enabled and not configured:
                enabled = False
                if not error_text:
                    error_text = "Para ativar o MisticPay, informe Client ID e Client Secret."

        elif self.provider_key == "pix_manual":
            import re
            existing = ConfigurarPagamentos._load_config().get("pix_manual") or {}
            key = pix_manual_key or existing.get("pix_key")
            key_type = pix_manual_key_type or existing.get("pix_key_type")
            
            if key and key_type:
                # Validar formato da chave PIX
                key = key.strip()
                is_valid = False
                
                if key_type == "email":
                    is_valid = bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", key))
                    if not is_valid:
                        error_text = "Email inválido! Formato esperado: usuario@dominio.com"
                elif key_type == "telefone":
                    clean_phone = re.sub(r"[^\d]", "", key)
                    is_valid = len(clean_phone) >= 10 and len(clean_phone) <= 11
                    if not is_valid:
                        error_text = "Telefone inválido! Use formato: (11) 98765-4321 ou 11987654321"
                elif key_type == "cpf":
                    clean_cpf = re.sub(r"[^\d]", "", key)
                    is_valid = len(clean_cpf) == 11
                    if is_valid:
                        # Validar dígitos verificadores do CPF
                        cpf_digits = [int(d) for d in clean_cpf]
                        # Primeiro dígito
                        sum1 = sum(cpf_digits[i] * (10 - i) for i in range(9))
                        digit1 = 0 if (sum1 % 11) < 2 else 11 - (sum1 % 11)
                        # Segundo dígito
                        sum2 = sum(cpf_digits[i] * (11 - i) for i in range(10))
                        digit2 = 0 if (sum2 % 11) < 2 else 11 - (sum2 % 11)
                        is_valid = cpf_digits[9] == digit1 and cpf_digits[10] == digit2
                    if not is_valid:
                        error_text = "CPF inválido! Use 11 dígitos: 123.456.789-00 ou 12345678900"
                elif key_type == "cnpj":
                    clean_cnpj = re.sub(r"[^\d]", "", key)
                    is_valid = len(clean_cnpj) == 14
                    if is_valid:
                        # Validar dígitos verificadores do CNPJ
                        cnpj_digits = [int(d) for d in clean_cnpj]
                        weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
                        sum1 = sum(cnpj_digits[i] * weights1[i] for i in range(12))
                        digit1 = 0 if (sum1 % 11) < 2 else 11 - (sum1 % 11)
                        weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
                        sum2 = sum(cnpj_digits[i] * weights2[i] for i in range(13))
                        digit2 = 0 if (sum2 % 11) < 2 else 11 - (sum2 % 11)
                        is_valid = cnpj_digits[12] == digit1 and cnpj_digits[13] == digit2
                    if not is_valid:
                        error_text = "CNPJ inválido! Use 14 dígitos: 12.345.678/0001-00 ou 12345678000100"
                elif key_type == "aleatoria":
                    # Chave aleatória: geralmente UUID ou string alfanumérica
                    is_valid = len(key) >= 8 and len(key) <= 50
                    if not is_valid:
                        error_text = "Chave aleatória inválida! Deve ter entre 8 e 50 caracteres"
                
                configured = is_valid
                if enabled and not configured:
                    enabled = False
                    if not error_text:
                        error_text = "Chave PIX inválida para o tipo selecionado."
            else:
                configured = False
                if enabled:
                    enabled = False
                    error_text = "Para ativar o PIX Manual, informe a chave PIX e o tipo."

        config = ConfigurarPagamentos._load_config()
        entry = config.get(self.provider_key)
        if not isinstance(entry, dict):
            entry = {}
        old_token = str(entry.get("access_token") or "")
        entry["enabled"] = enabled
        if self.provider_key == "mercado_pago":
            final_token = old_token
            if access_token is not None:
                if access_token == "":
                    # user cleared the token
                    final_token = ""
                elif configured:
                    # new valid token provided
                    final_token = access_token
                else:
                    # invalid/new token provided - keep old one
                    final_token = old_token
            entry["access_token"] = final_token
        elif self.provider_key == "efibank":
            if efibank_client_id is not None:
                entry["client_id"] = efibank_client_id
            if efibank_client_secret is not None:
                entry["client_secret"] = efibank_client_secret
            if efibank_pix_key is not None:
                entry["pix_key"] = efibank_pix_key
            # Salvar caminho do certificado se foi processado
            if cert_path:
                entry["cert_file"] = cert_path
        elif self.provider_key == "sync_wallet":
            entry.pop("api_key", None)
            if sync_wallet_cover_fee is not None:
                entry["cover_fee"] = sync_wallet_cover_fee == "true"
        elif self.provider_key in {"pagbank", "picpay", "pushinpay", "asaas", "stripe", "coinbase", "nowpayments"}:
            token_key = {
                "pagbank": "token_pagbank",
                "picpay": "token_picpay",
                "pushinpay": "token_pushinpay",
                "asaas": "token_asaas",
                "stripe": "token_stripe",
                "coinbase": "token_coinbase",
                "nowpayments": "token_nowpayments",
            }[self.provider_key]
            new_value = {
                "pagbank": pagbank_token,
                "picpay": picpay_token,
                "pushinpay": pushinpay_token,
                "asaas": asaas_token,
                "stripe": stripe_token,
                "coinbase": coinbase_token,
                "nowpayments": nowpayments_token,
            }[self.provider_key]
            old_value = str(entry.get(token_key) or "")
            final_value = old_value
            if new_value is not None:
                if new_value == "":
                    final_value = ""
                else:
                    final_value = new_value
            entry[token_key] = final_value
        elif self.provider_key == "paypal":
            if paypal_client_id is not None:
                entry["client_id"] = paypal_client_id
            if paypal_client_secret is not None:
                entry["client_secret"] = paypal_client_secret
        elif self.provider_key == "misticpay":
            if misticpay_client_id is not None:
                entry["client_id"] = misticpay_client_id
            if misticpay_client_secret is not None:
                entry["client_secret"] = misticpay_client_secret
        elif self.provider_key == "pix_manual":
            if pix_manual_key is not None:
                entry["pix_key"] = pix_manual_key.strip() if pix_manual_key else ""
            if pix_manual_key_type is not None:
                entry["pix_key_type"] = pix_manual_key_type
        config[self.provider_key] = entry

        # Salvar configurações no database
        db.save_document("payment_configs", config)

        # Atualizar status de habilitado no documento pagamentos
        pagamentos = db.get_document("pagamentos") or {}
        pagamentos[self.provider_key] = enabled
        db.save_document("pagamentos", {}, pagamentos)

        mode = db.get_document("custom_mode").get("mode")
        if mode == "embed":
            embed, components = ConfigurarPagamentos.pagamentos_embed(inter, self.categoria)
            await inter.edit_original_message(content=None, embed=embed, components=components)
        else:
            await inter.edit_original_message(components=ConfigurarPagamentos.pagamentos_components(inter, self.categoria))

        # Feedback ao usuário (ephemeral) se houve problema na validação
        if error_text:
            await message.error(inter, error_text, followup=True)


def setup(bot: commands.Bot):
    bot.add_cog(ConfigurarPagamentos(bot))