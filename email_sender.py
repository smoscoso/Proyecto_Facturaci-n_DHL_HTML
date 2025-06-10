import smtplib
import os
import logging
import mimetypes
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class EmailSender:
    def __init__(self, email: str, password: str, smtp_server: str = 'smtp.gmail.com', port: int = 587):
        self.email = email
        self.password = password
        self.smtp_server = smtp_server
        self.port = port
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    def send_email(self, to: str, subject: str, body: str, file_path: str = None, is_html: bool = False) -> bool:
        """Envía un email con o sin adjunto."""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email
            msg['To'] = to
            msg['Subject'] = subject

            content_type = 'html' if is_html else 'plain'
            msg.attach(MIMEText(body, content_type, 'utf-8'))

            if file_path:
                self._attach_file(msg, file_path)

            with smtplib.SMTP(self.smtp_server, self.port) as server:
                server.starttls()
                server.login(self.email, self.password)
                server.send_message(msg)

            logging.info(f"Email enviado a {to} con asunto '{subject}'")
            return True
        except Exception as e:
            logging.error(f"Error enviando email: {str(e)}")
            return False

    def _attach_file(self, msg: MIMEMultipart, file_path: str) -> None:
        """Adjunta un archivo al mensaje"""
        filename = os.path.basename(file_path)
        file_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        main_type, sub_type = file_type.split('/', 1)
        
        with open(file_path, "rb") as f:
            part = MIMEBase(main_type, sub_type)
            part.set_payload(f.read())
        
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        msg.attach(part)

    def send_email_with_binary(self, to: str, subject: str, body: str, file_data: bytes, file_name: str, is_html: bool = False) -> None:
        """Envía un email con datos binarios como adjunto"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email
            msg['To'] = to
            msg['Subject'] = subject
            
            content_type = 'html' if is_html else 'plain'
            msg.attach(MIMEText(body, content_type, 'utf-8'))
            
            # Determinar el tipo MIME basado en la extensión del archivo
            file_ext = os.path.splitext(file_name)[1].lower()
            if file_ext in ['.pdf']:
                main_type, sub_type = 'application', 'pdf'
            elif file_ext in ['.jpg', '.jpeg']:
                main_type, sub_type = 'image', 'jpeg'
            elif file_ext in ['.png']:
                main_type, sub_type = 'image', 'png'
            else:
                main_type, sub_type = 'application', 'octet-stream'
            
            # Adjuntar datos binarios
            part = MIMEBase(main_type, sub_type)
            part.set_payload(file_data)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{file_name}"')
            msg.attach(part)
            
            with smtplib.SMTP(self.smtp_server, self.port) as server:
                server.starttls()
                server.login(self.email, self.password)
                server.send_message(msg)
            
            logging.info(f"Email con adjunto '{file_name}' enviado a {to}")
            return True
        except Exception as e:
            logging.error(f"Error enviando email con adjunto: {str(e)}")
            raise
