import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functions.database import database as db
import re

def is_valid_email(email: str) -> bool:
    """Valida se uma string é um email válido."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))

async def send_notification_email(subject: str, body_text: str, body_html: str = None):
    """
    Envia um email de notificação baseado nas configurações do banco de dados.
    """
    config = db.get_document("notifications_email_config")
    if not config or not config.get("enabled"):
        return False, "Notificações por email desativadas."

    dest_email = config.get("email")
    smtp_server = config.get("smtp_server")
    smtp_port = config.get("smtp_port")
    smtp_user = config.get("smtp_user")
    smtp_pass = config.get("smtp_pass")

    if not all([dest_email, smtp_server, smtp_port, smtp_user, smtp_pass]):
        return False, "Configurações de SMTP incompletas."

    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = smtp_user
        message["To"] = dest_email

        # Adicionar parte texto
        part1 = MIMEText(body_text, "plain")
        message.attach(part1)

        # Adicionar parte HTML se fornecida
        if body_html:
            part2 = MIMEText(body_html, "html")
            message.attach(part2)

        context = ssl.create_default_context()
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if config.get("use_tls", True):
                server.starttls(context=context)
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, dest_email, message.as_string())
            
        return True, "Email enviado com sucesso."
    except Exception as e:
        return False, f"Erro ao enviar email: {str(e)}"
