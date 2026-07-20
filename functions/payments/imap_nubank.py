"""
Sistema de pagamento PIX via Nubank com aprovação automática por IMAP
Gera QR Codes PIX e monitora emails do Nubank para aprovar pagamentos automaticamente
"""
import imaplib
import email
from email.header import decode_header
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import uuid
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor

from modules.loja.personalization.qr_customization import QRCodeGenerator
from functions.database import database as db


def _load_config() -> dict:
    """Carrega configurações de pagamento do database"""
    return db.get_document("payment_configs") or {}


def _sanitize_text(text: str, max_length: int) -> str:
    """Remove caracteres especiais e limita tamanho conforme padrão PIX"""
    import unicodedata
    
    # Normalizar unicode (remover acentos)
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ASCII', 'ignore').decode('ASCII')
    
    # Remover caracteres não permitidos (apenas letras, números, espaços e alguns símbolos)
    text = re.sub(r'[^A-Za-z0-9\s\.\-]', '', text)
    
    # Limitar tamanho
    return text[:max_length].strip()


def _generate_pix_payload(
    pix_key: str,
    merchant_name: str,
    merchant_city: str,
    amount: float,
    transaction_id: str,
    pix_key_type: Optional[str] = None,
    description: Optional[str] = None
) -> str:
    """
    Gera o payload PIX (EMV) padrão Banco Central
    
    Args:
        pix_key: Chave PIX do recebedor
        merchant_name: Nome do recebedor
        merchant_city: Cidade do recebedor
        amount: Valor da transação
        transaction_id: ID único da transação (máx 25 caracteres alfanuméricos)
        pix_key_type: Tipo da chave PIX (cpf, cnpj, email, telefone, aleatoria)
        description: Descrição opcional
    
    Returns:
        String do payload PIX (copia e cola)
    """
    def format_field(field_id: str, value: str) -> str:
        """Formata um campo no padrão EMV"""
        length = str(len(value)).zfill(2)
        return f"{field_id}{length}{value}"
    
    # Sanitizar textos
    merchant_name = _sanitize_text(merchant_name, 25)
    merchant_city = _sanitize_text(merchant_city, 15)
    
    # Limpar chave PIX baseado no tipo
    pix_key_clean = pix_key.strip()  # Sempre remover espaços no início/fim
    
    if pix_key_type == "cpf":
        # CPF: remover pontos e hífens, manter apenas números
        pix_key_clean = pix_key_clean.replace('.', '').replace('-', '').replace(' ', '')
    elif pix_key_type == "cnpj":
        # CNPJ: remover pontos, barras e hífens, manter apenas números
        pix_key_clean = pix_key_clean.replace('.', '').replace('-', '').replace('/', '').replace(' ', '')
    elif pix_key_type == "email":
        # Email: apenas remover espaços, manter pontos e arroba
        pix_key_clean = pix_key_clean.replace(' ', '').lower()
    elif pix_key_type == "telefone":
        # Telefone: remover parênteses, hífens e espaços, manter apenas números
        pix_key_clean = pix_key_clean.replace('(', '').replace(')', '').replace('-', '').replace(' ', '').replace('+', '')
    elif pix_key_type == "aleatoria":
        # Chave aleatória: apenas remover espaços
        pix_key_clean = pix_key_clean.replace(' ', '')
    else:
        # Fallback: tentar detectar automaticamente
        if '@' in pix_key_clean:
            # Parece email
            pix_key_clean = pix_key_clean.replace(' ', '').lower()
        elif len(pix_key_clean.replace('.', '').replace('-', '').replace('/', '').replace(' ', '')) == 11:
            # Parece CPF (11 dígitos)
            pix_key_clean = pix_key_clean.replace('.', '').replace('-', '').replace(' ', '')
        elif len(pix_key_clean.replace('.', '').replace('-', '').replace('/', '').replace(' ', '')) == 14:
            # Parece CNPJ (14 dígitos)
            pix_key_clean = pix_key_clean.replace('.', '').replace('-', '').replace('/', '').replace(' ', '')
        else:
            # Chave aleatória ou desconhecida: apenas remover espaços
            pix_key_clean = pix_key_clean.replace(' ', '')
    
    # TXID: apenas alfanuméricos, máximo 25 caracteres
    transaction_id = transaction_id.replace('-', '')[:25].upper()
    
    # Payload Format Indicator
    payload = format_field("00", "01")
    
    # Point of Initiation Method (12 = dinâmico, permite reutilização)
    payload += format_field("01", "12")
    
    # Merchant Account Information (PIX)
    gui = format_field("00", "br.gov.bcb.pix")
    key = format_field("01", pix_key_clean)
    if description:
        desc_clean = _sanitize_text(description, 25)
        if desc_clean:
            desc = format_field("02", desc_clean)
            merchant_account = format_field("26", gui + key + desc)
        else:
            merchant_account = format_field("26", gui + key)
    else:
        merchant_account = format_field("26", gui + key)
    payload += merchant_account
    
    # Merchant Category Code (0000 = não especificado)
    payload += format_field("52", "0000")
    
    # Transaction Currency (986 = BRL)
    payload += format_field("53", "986")
    
    # Transaction Amount
    if amount > 0:
        amount_str = f"{amount:.2f}"
        payload += format_field("54", amount_str)
    
    # Country Code
    payload += format_field("58", "BR")
    
    # Merchant Name
    payload += format_field("59", merchant_name)
    
    # Merchant City
    payload += format_field("60", merchant_city)
    
    # Additional Data Field Template
    txid = format_field("05", transaction_id)
    additional_data = format_field("62", txid)
    payload += additional_data
    
    # CRC16
    payload += "6304"
    crc = _calculate_crc16(payload)
    payload += crc
    
    return payload


def _calculate_crc16(payload: str) -> str:
    """Calcula o CRC16-CCITT do payload PIX"""
    crc = 0xFFFF
    polynomial = 0x1021
    
    for byte in payload.encode('utf-8'):
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ polynomial
            else:
                crc <<= 1
            crc &= 0xFFFF
    
    return f"{crc:04X}"


async def create_nubank_imap_payment(
    amount: float,
    cart_id: str,
    description: Optional[str] = None,
    merchant_name: str = "Loja",
    merchant_city: str = "Sao Paulo"
) -> Dict[str, Any]:
    """
    Cria um pagamento PIX via Nubank IMAP
    
    Args:
        amount: Valor do pagamento
        cart_id: ID do carrinho (usado como TXID para rastreamento)
        description: Descrição do pagamento
        merchant_name: Nome do estabelecimento
        merchant_city: Cidade do estabelecimento
    
    Returns:
        Dict com dados do pagamento incluindo QR code
    """
    config = _load_config()
    nubank_config = config.get("nubank_imap", {})
    
    if not nubank_config.get("enabled"):
        raise ValueError("Nubank IMAP não está habilitado")
    
    pix_key = nubank_config.get("pix_key")
    if not pix_key:
        raise ValueError("Chave PIX não configurada no Nubank IMAP")
    
    pix_key_type = nubank_config.get("pix_key_type")
    
    email_address = nubank_config.get("email")
    if not email_address:
        raise ValueError("Email não configurado no Nubank IMAP")
    
    # Usar o cart_id como TXID para rastreamento
    # Limpar e garantir que seja alfanumérico
    transaction_id = re.sub(r'[^A-Za-z0-9]', '', str(cart_id))[:25].upper()
    
    # Gerar payload PIX
    pix_payload = _generate_pix_payload(
        pix_key=pix_key,
        merchant_name=merchant_name,
        merchant_city=merchant_city,
        amount=amount,
        transaction_id=transaction_id,
        pix_key_type=pix_key_type,
        description=description
    )
    
    # Gerar QR Code usando o sistema de customização
    try:
        qr_bytes = await QRCodeGenerator.generate_custom_qr(pix_payload)
    except Exception as e:
        print(f"❌ Erro ao gerar QR customizado: {e}")
        # Fallback para QR simples se houver erro
        qr_bytes = await QRCodeGenerator.generate_simple_qr(pix_payload)
    
    # Salvar informações do pagamento pendente no database
    payment_data = {
        "payment_id": transaction_id,
        "cart_id": cart_id,
        "txid": transaction_id,
        "status": "pending",
        "amount": amount,
        "currency": "BRL",
        "pix_copia_cola": pix_payload,
        "pix_key": pix_key,
        "pix_key_type": nubank_config.get("pix_key_type"),
        "description": description,
        "created_at": datetime.utcnow().isoformat(),
        "payment_method": "nubank_imap",
        "requires_manual_approval": False,  # Será aprovado automaticamente pelo IMAP
        "imap_monitored": True
    }
    
    # Salvar no database para rastreamento
    _save_pending_payment(transaction_id, payment_data)
    
    return {
        **payment_data,
        "id": transaction_id,
        "copy_paste": pix_payload,
        "emv": pix_payload,
        "qr_code_base64": None,
        "qr_code_bytes": qr_bytes,
    }


def _save_pending_payment(payment_id: str, payment_data: Dict[str, Any]) -> None:
    """Salva um pagamento pendente no database"""
    pending_payments = db.get_document("nubank_pending_payments") or {}
    pending_payments[payment_id] = payment_data
    db.save_document("nubank_pending_payments", {}, pending_payments)


def _get_pending_payment(payment_id: str) -> Optional[Dict[str, Any]]:
    """Recupera um pagamento pendente do database"""
    pending_payments = db.get_document("nubank_pending_payments") or {}
    return pending_payments.get(payment_id)


def _update_payment_status(payment_id: str, status: str, extra_data: Optional[Dict] = None) -> None:
    """Atualiza o status de um pagamento"""
    pending_payments = db.get_document("nubank_pending_payments") or {}
    if payment_id in pending_payments:
        pending_payments[payment_id]["status"] = status
        pending_payments[payment_id]["updated_at"] = datetime.utcnow().isoformat()
        if extra_data:
            pending_payments[payment_id].update(extra_data)
        db.save_document("nubank_pending_payments", {}, pending_payments)


def _connect_imap(email_address: str, password: str) -> imaplib.IMAP4_SSL:
    """
    Conecta ao servidor IMAP do Gmail
    
    Args:
        email_address: Endereço de email
        password: Senha de app do Gmail
    
    Returns:
        Conexão IMAP
    """
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(email_address, password)
        return mail
    except Exception as e:
        raise RuntimeError(f"Erro ao conectar ao IMAP: {str(e)}")


def _decode_email_header(header: str) -> str:
    """Decodifica header de email que pode estar em formato encoded"""
    if not header:
        return ""
    
    decoded_parts = []
    for part, encoding in decode_header(header):
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(encoding or 'utf-8', errors='ignore'))
        else:
            decoded_parts.append(str(part))
    return ''.join(decoded_parts)


def _extract_email_body(msg: email.message.Message) -> str:
    """Extrai o corpo de texto de um email"""
    body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            # Procurar por texto plano ou HTML
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode('utf-8', errors='ignore')
                        break
                except Exception:
                    continue
            elif content_type == "text/html" and not body and "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode('utf-8', errors='ignore')
                except Exception:
                    continue
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode('utf-8', errors='ignore')
        except Exception:
            pass
    
    return body


def _parse_nubank_pix_email(subject: str, body: str) -> Optional[Dict[str, Any]]:
    """
    Extrai informações de um email de PIX recebido do Nubank
    Melhorado para capturar melhor os dados dos emails do Nubank
    
    Args:
        subject: Assunto do email
        body: Corpo do email
    
    Returns:
        Dict com informações extraídas ou None se não for um email de PIX
    """
    # Verificar se é um email de PIX recebido
    subject_lower = subject.lower()
    body_lower = body.lower()
    
    if "pix" not in subject_lower and "pix" not in body_lower:
        return None
    
    # Verificar se é sobre recebimento (não envio) - mais flexível
    # Aceita se tiver qualquer indicação de recebimento OU se não tiver indicação de envio
    has_received = (
        "recebido" in subject_lower or 
        "recebeu" in body_lower or 
        "entrou" in body_lower or
        "creditado" in body_lower or
        "depositado" in body_lower
    )
    
    has_sent = (
        "enviado" in subject_lower or 
        "enviou" in body_lower or
        "pagou" in subject_lower
    )
    
    # Se tem indicação de envio mas não de recebimento, pular
    if has_sent and not has_received:
        return None
    
    # Se não tem nenhuma indicação, assumir que é recebimento (mais comum)
    
    info = {}
    
    # Extrair valor (formatos específicos do Nubank + genéricos)
    # Formato Nubank: "Valor Recebido: R$ 1,00" ou "R$ 1,00"
    value_patterns = [
        # Padrão específico do Nubank: "Valor Recebido: R$ X,XX"
        r'Valor\s+Recebido[:\s]*R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',
        r'Valor\s+Recebido[:\s]*R\$\s*(\d+(?:,\d{2})?)',
        # Padrões genéricos
        r'R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',  # R$ 1.234,56 ou R$ 10,50
        r'R\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # R$ 1,234.56 (formato US)
        r'R\$\s*(\d+(?:[.,]\d{2})?)',  # R$ 10,50 ou R$ 10.50
        r'valor[:\s]*R\$\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',
        r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*reais?',
        r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*R\$',
        # Padrões mais genéricos
        r'(\d{1,3}(?:\.\d{3})*,\d{2})',  # 1.234,56
        r'(\d{1,3}(?:,\d{3})*\.\d{2})',  # 1,234.56
        r'(\d+,\d{2})',  # 10,50
        r'(\d+\.\d{2})',  # 10.50
    ]
    
    all_values = []
    for pattern in value_patterns:
        matches = re.findall(pattern, body, re.IGNORECASE)
        if matches:
            all_values.extend(matches if isinstance(matches, list) else [matches])
    
    # Processar todos os valores encontrados e pegar o maior (geralmente é o correto)
    for value_str in all_values:
        if isinstance(value_str, tuple):
            value_str = value_str[0] if value_str else ""
        
        # Normalizar formato
        original = value_str
        # Formato brasileiro: 1.234,56
        if '.' in value_str and ',' in value_str:
            # Contar dígitos após vírgula
            parts = value_str.split(',')
            if len(parts) == 2 and len(parts[1]) == 2:
                # Formato: 1.234,56
                value_str = value_str.replace('.', '').replace(',', '.')
            else:
                # Tentar outro formato
                value_str = value_str.replace(',', '')
        # Formato US: 1,234.56
        elif ',' in value_str and '.' in value_str:
            parts = value_str.split('.')
            if len(parts) == 2 and len(parts[1]) == 2:
                # Formato: 1,234.56
                value_str = value_str.replace(',', '')
        # Apenas vírgula: 10,50
        elif ',' in value_str:
            value_str = value_str.replace(',', '.')
        # Apenas ponto: verificar se são decimais
        elif '.' in value_str:
            parts = value_str.split('.')
            if len(parts) == 2 and len(parts[1]) == 2:
                # Formato: 10.50 (decimais)
                pass
            elif len(parts[-1]) > 2:
                # Formato: 1.234 (milhar) - remover pontos
                value_str = value_str.replace('.', '')
        
        try:
            amount = float(value_str)
            # Validar: valor deve ser razoável (entre 0.01 e 1.000.000)
            if 0.01 <= amount <= 1000000:
                info['amount'] = amount
                break
        except (ValueError, TypeError):
            continue
    
    # Extrair TXID / ID da transação (padrões mais flexíveis)
    # O TXID pode estar em vários formatos no email do Nubank
    txid_patterns = [
        r'ID[:\s]*([A-Z0-9]{8,32})',
        r'transa[çc][ãa]o[:\s]*([A-Z0-9]{8,32})',
        r'identificador[:\s]*([A-Z0-9]{8,32})',
        r'c[óo]digo[:\s]*([A-Z0-9]{8,32})',
        r'txid[:\s]*([A-Z0-9]{8,32})',
        r'endtoendid[:\s]*([A-Z0-9]{8,32})',
        r'E2E[:\s]*([A-Z0-9]{8,32})',
        # Padrão genérico: sequência de letras/números após "ID" ou similar
        r'(?:ID|Código|Identificador)[:\s]*([A-Z0-9]{10,25})',
    ]
    
    for pattern in txid_patterns:
        matches = re.findall(pattern, body, re.IGNORECASE)
        if matches:
            # Pegar o primeiro match válido
            txid = matches[0] if isinstance(matches, list) else matches
            if len(txid) >= 8:  # TXID geralmente tem pelo menos 8 caracteres
                info['txid'] = txid.upper().strip()
                break
    
    # Se não encontrou TXID no corpo, tentar extrair do assunto
    if 'txid' not in info:
        txid_subject_patterns = [
            r'([A-Z0-9]{10,25})',
        ]
        for pattern in txid_subject_patterns:
            match = re.search(pattern, subject)
            if match:
                potential_txid = match.group(1).upper()
                if len(potential_txid) >= 10:
                    info['txid'] = potential_txid
                    break
    
    # Extrair nome do pagador (padrões específicos do Nubank + genéricos)
    # Formato Nubank: "Você recebeu um Pix de [NOME]"
    name_patterns = [
        # Padrão específico do Nubank: "Você recebeu um Pix de [NOME]"
        r'Você\s+recebeu\s+um\s+Pix\s+de\s+([A-Za-zÀ-ÿ\s]{3,80}?)(?:\s+e\s+o\s+valor|\.|$)',
        r'recebeu\s+um\s+Pix\s+de\s+([A-Za-zÀ-ÿ\s]{3,80}?)(?:\s+e\s+o\s+valor|\.|$)',
        # Padrões genéricos
        r'De[:\s]+([A-Za-zÀ-ÿ\s]{3,50}?)(?:\n|<br|R\$|$)',
        r'Pagador[:\s]+([A-Za-zÀ-ÿ\s]{3,50}?)(?:\n|<br|R\$|$)',
        r'Origem[:\s]+([A-Za-zÀ-ÿ\s]{3,50}?)(?:\n|<br|R\$|$)',
        r'Recebido de[:\s]+([A-Za-zÀ-ÿ\s]{3,50}?)(?:\n|<br|R\$|$)',
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Limpar nome (remover espaços extras, números, etc)
            name = re.sub(r'\s+', ' ', name)
            if len(name) >= 3 and not name.isdigit():
                info['payer_name'] = name
                break
    
    # Se encontrou pelo menos o valor, considerar válido
    if 'amount' in info:
        return info
    
    return None


def _check_imap_for_payments(email_address: str, password: str) -> List[Dict[str, Any]]:
    """
    Verifica emails não lidos em busca de notificações de PIX do Nubank
    Otimizado para filtrar apenas emails do Nubank e processar rapidamente
    
    Args:
        email_address: Email configurado
        password: Senha de app
    
    Returns:
        Lista de pagamentos detectados
    """
    detected_payments = []
    processed_ids = []
    
    try:
        mail = _connect_imap(email_address, password)
        mail.select("inbox")
        
        # Buscar emails do Nubank - tentar múltiplas abordagens
        from datetime import datetime, timedelta
        all_mail_ids = []
        
        # Tentar diferentes estratégias de busca (incluindo emails lidos)
        search_strategies = [
            # Estratégia 1: Buscar TODOS os emails do Nubank (lidos E não lidos, sem filtro de data)
            ('(FROM "todomundo@nubank.com.br")', 'Todos os emails do Nubank (lidos + não lidos)'),
            
            # Estratégia 2: Buscar emails LIDOS do Nubank (últimas 24h)
            (f'(SEEN SINCE {(datetime.now() - timedelta(days=1)).strftime("%d-%b-%Y")} FROM "todomundo@nubank.com.br")', 'Emails lidos (últimas 24h)'),
            
            # Estratégia 3: Buscar não lidos do Nubank
            ('(UNSEEN FROM "todomundo@nubank.com.br")', 'Emails não lidos do Nubank'),
            
            # Estratégia 4: Buscar com data (últimas 24h) - inclui lidos e não lidos
            (f'(SINCE {(datetime.now() - timedelta(days=1)).strftime("%d-%b-%Y")} FROM "todomundo@nubank.com.br")', 'Últimas 24h (lidos + não lidos)'),
            
            # Estratégia 5: Buscar com data (últimos 7 dias) - inclui lidos e não lidos
            (f'(SINCE {(datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")} FROM "todomundo@nubank.com.br")', 'Últimos 7 dias (lidos + não lidos)'),
            
            # Estratégia 6: Buscar sem aspas (alguns servidores IMAP são sensíveis)
            ('(FROM todomundo@nubank.com.br)', 'Sem aspas'),
        ]
        
        for search_query, description in search_strategies:
            try:
                print(f"🔍 Tentando busca: {description}...")
                status, messages = mail.search(None, search_query)
                
                if status == "OK" and messages[0]:
                    found_ids = messages[0].split()
                    if found_ids:
                        # Adicionar IDs únicos
                        for mid in found_ids:
                            if mid not in all_mail_ids:
                                all_mail_ids.append(mid)
                        print(f"   ✅ Encontrados {len(found_ids)} email(s) com esta estratégia")
                        # Se encontrou muitos, pode parar aqui (mas continua para pegar mais)
                        if len(all_mail_ids) >= 100:
                            print(f"   ℹ️ Limite de 100 emails atingido, parando busca")
                            break
                    else:
                        print(f"   ⚠️ Nenhum email encontrado")
                else:
                    print(f"   ⚠️ Status: {status}, Mensagens: {messages}")
                    
            except Exception as e:
                print(f"   ⚠️ Erro na busca '{description}': {e}")
                continue
        
        # Remover duplicatas e ordenar (mais recentes primeiro)
        # Converter para set de strings para remover duplicatas
        unique_ids = set()
        for mid in all_mail_ids:
            unique_ids.add(mid.decode() if isinstance(mid, bytes) else str(mid))
        
        # Converter de volta para bytes e ordenar
        mail_ids = [mid.encode() if isinstance(mid, str) else mid for mid in unique_ids]
        # Ordenar por ID numérico (IDs maiores = mais recentes)
        try:
            mail_ids.sort(key=lambda x: int(x.decode() if isinstance(x, bytes) else x), reverse=True)
        except:
            # Se falhar, manter ordem original
            pass
        
        if mail_ids:
            print(f"📧 Total único: {len(mail_ids)} email(s) do Nubank encontrado(s)")
        else:
            print(f"⚠️ Nenhum email do Nubank encontrado em nenhuma estratégia")
            # Tentar uma busca mais genérica para debug
            try:
                status, messages = mail.search(None, '(FROM "nubank")')
                if status == "OK" and messages[0]:
                    generic_ids = messages[0].split()
                    print(f"   ℹ️ Encontrados {len(generic_ids)} email(s) com 'nubank' no remetente (busca genérica)")
            except:
                pass
        
        if not mail_ids:
            mail.close()
            mail.logout()
            return detected_payments
        
        print(f"📬 Nubank IMAP: {len(mail_ids)} email(s) do Nubank encontrado(s)")
        
        # Processar apenas os primeiros 100 emails para não travar (inclui lidos e não lidos)
        mail_ids = mail_ids[:100]
        print(f"📋 Processando {len(mail_ids)} email(s) mais recente(s) (lidos e não lidos)")
        nubank_count = 0
        pix_count = 0
        
        for mail_id in mail_ids:
            try:
                # Buscar apenas headers primeiro (mais rápido) - usa PEEK para não marcar como lido
                status, headers = mail.fetch(mail_id, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)] FLAGS)')
                
                if status != "OK":
                    continue
                
                # Parse rápido do header
                header_data = headers[0][1].decode('utf-8', errors='ignore')
                
                # Verificar se email está lido ou não (para log)
                try:
                    flags_data = str(headers[0][0]) if len(headers) > 0 else ""
                    is_read = '\\Seen' in flags_data
                    read_status = "📖 Lido" if is_read else "📬 Não lido"
                except:
                    read_status = "📧 Status desconhecido"
                
                # Verificar se é do Nubank e contém PIX
                if "nubank" not in header_data.lower() or "todomundo@nubank.com.br" not in header_data.lower():
                    continue
                
                # Verificar assunto rapidamente
                subject_match = re.search(r'Subject:\s*(.+)', header_data, re.IGNORECASE)
                if not subject_match:
                    continue
                
                subject = subject_match.group(1).strip()
                subject_decoded = _decode_email_header(subject)
                
                # Verificar se é sobre PIX (mais flexível)
                subject_lower = subject_decoded.lower()
                is_pix_email = (
                    "pix" in subject_lower or 
                    "recebido" in subject_lower or 
                    "recebeu" in subject_lower or
                    "entrou" in subject_lower
                )
                
                if not is_pix_email:
                    continue
                
                nubank_count += 1
                print(f"   📧 Email do Nubank encontrado ({read_status}): {subject_decoded[:80]}...")
                
                # Agora buscar o corpo completo apenas se passar pelos filtros
                # Usa PEEK para não marcar como lido mesmo após processar
                status, msg_data = mail.fetch(mail_id, '(BODY.PEEK[])')
                
                if status != "OK":
                    continue
                
                # Parse do email
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # Extrair informações
                sender = _decode_email_header(msg.get("from", ""))
                body = _extract_email_body(msg)
                
                # Debug: mostrar parte do corpo para entender o formato
                body_preview = body[:300].replace('\n', ' ').replace('\r', ' ') if body else ""
                print(f"   📄 Preview do corpo ({len(body)} chars): {body_preview}...")
                
                # Tentar extrair informações de pagamento PIX
                payment_info = _parse_nubank_pix_email(subject_decoded, body)
                
                # Debug: mostrar o que foi extraído
                if payment_info:
                    print(f"   ✅ Parsing OK: amount={payment_info.get('amount')}, txid={payment_info.get('txid')}, payer={payment_info.get('payer_name')}")
                else:
                    print(f"   ❌ Parsing falhou - verificando motivo...")
                    # Verificar se tem valor no texto
                    import re
                    value_test = re.search(r'R\$\s*(\d+[.,]\d{2})', body, re.IGNORECASE)
                    if value_test:
                        print(f"      ⚠️ Valor encontrado no texto: {value_test.group(0)} mas não foi parseado")
                    else:
                        print(f"      ⚠️ Nenhum valor encontrado no padrão R$")
                
                if payment_info:
                    payment_info['email_id'] = mail_id.decode()
                    payment_info['received_at'] = datetime.utcnow().isoformat()
                    detected_payments.append(payment_info)
                    processed_ids.append(mail_id)
                    pix_count += 1
                    
                    txid = payment_info.get('txid', 'N/A')
                    amount = payment_info.get('amount', 0)
                    payer = payment_info.get('payer_name', 'N/A')
                    print(f"   ✅ PIX detectado: TXID={txid}, Valor=R${amount:.2f}, Pagador={payer}")
                else:
                    # Log detalhado para debug
                    body_lower_check = body.lower() if body else ""
                    has_pix_keyword = "pix" in subject_lower or "pix" in body_lower_check
                    has_received_keyword = "recebido" in subject_lower or "recebeu" in body_lower_check or "entrou" in body_lower_check
                    
                    if has_pix_keyword:
                        print(f"   ⚠️ Email PIX não parseado!")
                        print(f"      Assunto: {subject_decoded}")
                        print(f"      Tem 'recebido'? {has_received_keyword}")
                        print(f"      Corpo tem {len(body)} caracteres")
                        
                        # Tentar encontrar valor manualmente para debug
                        import re
                        value_matches = re.findall(r'R\$\s*(\d+[.,]\d{2})', body, re.IGNORECASE)
                        if value_matches:
                            print(f"      Valores encontrados no texto: {value_matches}")
                        else:
                            print(f"      Nenhum valor encontrado no padrão R$")
            
            except Exception as e:
                print(f"⚠️ Erro ao processar email {mail_id}: {e}")
                continue
        
        # Não marcar emails como lidos automaticamente
        # Isso permite processar emails lidos e não lidos sem alterar seu status
        # Apenas logar quantos foram processados
        if processed_ids:
            print(f"   ✅ {len(processed_ids)} email(s) de PIX processado(s) (mantendo status original)")
        
        if nubank_count > 0:
            print(f"📊 Processados: {nubank_count} email(s) do Nubank, {pix_count} PIX detectado(s)")
        
        mail.close()
        mail.logout()
    
    except Exception as e:
        import traceback
        print(f"❌ Erro ao verificar IMAP: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
    
    return detected_payments


async def check_nubank_imap_payment(payment_id: str) -> Dict[str, Any]:
    """
    Verifica status de um pagamento PIX via Nubank IMAP
    
    Esta função monitora emails do Nubank em busca de confirmação de pagamento
    
    Args:
        payment_id: ID do pagamento (TXID)
    
    Returns:
        Dict com status do pagamento
    """
    # Buscar informações do pagamento pendente
    payment_data = _get_pending_payment(payment_id)
    
    if not payment_data:
        return {
            "payment_id": payment_id,
            "status": "not_found",
            "payment_status": "not_found",
            "error": "Pagamento não encontrado"
        }
    
    # Se já foi aprovado, retornar status
    if payment_data.get("status") == "approved":
        return {
            "payment_id": payment_id,
            "status": "approved",
            "payment_status": "approved",
            "approved_at": payment_data.get("approved_at"),
            "amount": payment_data.get("amount")
        }
    
    # Verificar emails em busca de confirmação
    config = _load_config()
    nubank_config = config.get("nubank_imap", {})
    
    email_address = nubank_config.get("email")
    password = nubank_config.get("password")
    
    if not email_address or not password:
        return {
            "payment_id": payment_id,
            "status": "pending",
            "payment_status": "pending",
            "error": "Credenciais IMAP não configuradas"
        }
    
    # Executar verificação IMAP em thread separada para não bloquear
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        detected_payments = await loop.run_in_executor(
            executor,
            _check_imap_for_payments,
            email_address,
            password
        )
    
    # Procurar por pagamento correspondente
    expected_amount = payment_data.get("amount")
    
    for detected in detected_payments:
        detected_txid = detected.get("txid", "")
        detected_amount = detected.get("amount")
        
        # Verificar se o TXID ou valor correspondem
        if detected_txid == payment_id or (detected_amount == expected_amount):
            # Pagamento confirmado!
            _update_payment_status(
                payment_id,
                "approved",
                {
                    "approved_at": datetime.utcnow().isoformat(),
                    "payer_name": detected.get("payer_name"),
                    "detected_amount": detected_amount
                }
            )
            
            return {
                "payment_id": payment_id,
                "status": "approved",
                "payment_status": "approved",
                "approved_at": datetime.utcnow().isoformat(),
                "amount": detected_amount or expected_amount,
                "payer_name": detected.get("payer_name")
            }
    
    # Ainda pendente
    return {
        "payment_id": payment_id,
        "status": "pending",
        "payment_status": "pending",
        "amount": expected_amount
    }


async def monitor_nubank_imap_payments() -> List[Dict[str, Any]]:
    """
    Monitora continuamente emails do Nubank em busca de pagamentos
    
    Esta função deve ser executada periodicamente (ex: a cada 30 segundos)
    
    Returns:
        Lista de pagamentos aprovados nesta verificação
    """
    config = _load_config()
    nubank_config = config.get("nubank_imap", {})
    
    if not nubank_config.get("enabled"):
        return []
    
    email_address = nubank_config.get("email")
    password = nubank_config.get("password")
    
    if not email_address or not password:
        print("⚠️ Nubank IMAP: credenciais não configuradas")
        return []
    
    try:
        # Verificar emails em thread separada
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            detected_payments = await loop.run_in_executor(
                executor,
                _check_imap_for_payments,
                email_address,
                password
            )
        
        if detected_payments:
            print(f"📧 Nubank IMAP: {len(detected_payments)} email(s) de PIX detectado(s)")
        
        approved_payments = []
        
        # Buscar pagamentos pendentes
        pending_payments = db.get_document("nubank_pending_payments") or {}
        pending_list = [
            (payment_id, data)
            for payment_id, data in pending_payments.items()
            if isinstance(data, dict) and data.get("status") == "pending"
        ]
        pending_count = len(pending_list)
        
        if pending_count > 0:
            print(f"🔍 Nubank IMAP: Comparando {len(detected_payments)} PIX detectado(s) com {pending_count} pagamento(s) pendente(s)...")
        
        # Se não há emails detectados nem pendentes, retornar vazio
        if not detected_payments and not pending_list:
            return approved_payments
        
        # Criar índice de pagamentos pendentes para busca rápida
        # Índice por valor (mais comum)
        pending_by_amount = {}
        # Índice por TXID
        pending_by_txid = {}
        # Lista completa para fallback
        pending_full_list = []
        
        for payment_id, payment_data in pending_list:
            amount = payment_data.get("amount")
            txid = payment_data.get("txid") or payment_data.get("payment_id")
            
            if amount:
                amount_key = f"{amount:.2f}"
                if amount_key not in pending_by_amount:
                    pending_by_amount[amount_key] = []
                pending_by_amount[amount_key].append((payment_id, payment_data))
            
            if txid:
                txid_clean = re.sub(r'[^A-Z0-9]', '', str(txid).upper())
                if txid_clean:
                    pending_by_txid[txid_clean] = (payment_id, payment_data)
            
            pending_full_list.append((payment_id, payment_data))
        
        # Processar pagamentos detectados em batch
        for detected in detected_payments:
            detected_txid = detected.get("txid")
            detected_amount = detected.get("amount")
            
            print(f"   📨 Processando PIX: TXID={detected_txid or 'N/A'}, Valor=R${detected_amount:.2f}")
            
            # Normalizar TXID detectado
            detected_txid_clean = re.sub(r'[^A-Z0-9]', '', str(detected_txid or '').upper())
            
            matched_payment = None
            match_type = None
            
            # Busca rápida por TXID primeiro (mais preciso)
            if detected_txid_clean:
                # Match exato por TXID
                if detected_txid_clean in pending_by_txid:
                    matched_payment = pending_by_txid[detected_txid_clean]
                    match_type = "TXID (exato)"
                else:
                    # Match parcial (últimos 8 caracteres)
                    if len(detected_txid_clean) >= 8:
                        txid_suffix = detected_txid_clean[-8:]
                        for txid_key, payment_data in pending_by_txid.items():
                            if len(txid_key) >= 8 and txid_key[-8:] == txid_suffix:
                                matched_payment = payment_data
                                match_type = "TXID (parcial)"
                                break
            
            # Se não encontrou por TXID, buscar por valor
            if not matched_payment and detected_amount:
                amount_key = f"{detected_amount:.2f}"
                if amount_key in pending_by_amount:
                    # Se houver múltiplos com mesmo valor, pegar o primeiro pendente
                    matched_payment = pending_by_amount[amount_key][0]
                    match_type = "Valor"
            
            # Se encontrou correspondência
            if matched_payment:
                payment_id, payment_data = matched_payment
                expected_amount = payment_data.get("amount")
                expected_txid = payment_data.get("txid") or payment_data.get("payment_id")
                expected_txid_clean = re.sub(r'[^A-Z0-9]', '', str(expected_txid or '').upper())
                
                print(f"   ✅ Correspondência por {match_type}! Payment ID: {payment_id}")
                print(f"      Esperado: TXID={expected_txid_clean}, Valor=R${expected_amount:.2f}")
                print(f"      Detectado: TXID={detected_txid_clean}, Valor=R${detected_amount:.2f}")
                
                # Aprovar pagamento
                _update_payment_status(
                    payment_id,
                    "approved",
                    {
                        "approved_at": datetime.utcnow().isoformat(),
                        "payer_name": detected.get("payer_name"),
                        "detected_amount": detected_amount,
                        "detected_txid": detected_txid
                    }
                )
                
                approved_payments.append({
                    "payment_id": payment_id,
                    "cart_id": payment_data.get("cart_id"),
                    "amount": detected_amount or expected_amount,
                    "payer_name": detected.get("payer_name"),
                    "approved_at": datetime.utcnow().isoformat()
                })
                
                print(f"✅ Pagamento aprovado automaticamente: {payment_id}")
                
                # Remover do índice para não processar novamente
                if detected_txid_clean in pending_by_txid:
                    del pending_by_txid[detected_txid_clean]
                if detected_amount:
                    amount_key = f"{detected_amount:.2f}"
                    if amount_key in pending_by_amount:
                        pending_by_amount[amount_key] = [
                            p for p in pending_by_amount[amount_key] 
                            if p[0] != payment_id
                        ]
            else:
                print(f"   ⚠️ Nenhum pagamento pendente correspondente encontrado para este PIX")
        
        return approved_payments
    
    except Exception as e:
        import traceback
        print(f"❌ Erro ao monitorar Nubank IMAP: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        return []


__all__ = [
    "create_nubank_imap_payment",
    "check_nubank_imap_payment",
    "monitor_nubank_imap_payments",
]

