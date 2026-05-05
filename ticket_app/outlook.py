# ticket_app/outlook.py
import imaplib
import email
from email.header import decode_header
from typing import List, Dict, Optional
import os
from pathlib import Path

class OutlookClient:
    def __init__(self, email: str, password: str, server: str = "imap Outlook.com"):
        self.imap = imaplib.IMAP4_SSL(server)
        self.imap.login(email, password)
        self.imap.select("INBOX")

    def download_eju_attachments(self, date_str: str) -> List[Path]:
        """Загружает все EJU-файлы за указанную дату в папку EJU/Download/ДД.ММ.ГГГГ"""
        date_folder = f"EJU/Download/{date_str}"
        os.makedirs(date_folder, exist_ok=True)

        # Формат даты для IMAP: 02-May-2026
        search_date = self._format_date(date_str)
        status, messages = self.imap.search(None, f'SINCE {search_date}')
        if status != "OK":
            return []

        paths = []
        for num in messages[0].split():
            status, msg_data = self.imap.fetch(num, "(RFC822)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subject, _ = decode_header(msg["Subject"])[0]
            if "Ежедневный учёт" not in subject:
                continue

            for part in msg.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                if part.get("Content-Disposition") is None:
                    continue
                filename = part.get_filename()
                if not filename or not filename.endswith('.xlsb'):
                    continue
                # Дата из названия файла (доп.)
                if date_str.replace('.', '') not in filename:
                    continue
                filepath = Path(date_folder) / filename
                with open(filepath, 'wb') as f:
                    f.write(part.get_payload(decode=True))
                paths.append(filepath)
        return paths

    def _format_date(self, date_str: str) -> str:
        """ДД.ММ.ГГГГ → 02-May-2026"""
        from datetime import datetime
        dt = datetime.strptime(date_str, "%d.%m.%Y")
        return dt.strftime("%d-%b-%Y").upper()
