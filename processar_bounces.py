#!/usr/bin/env python3
"""
Script para identificar e-mails que retornaram erro de entrega (bounces / caixa inexistente)
acessando a caixa de entrada do Gmail via IMAP com as credenciais do config.json.
Remove os e-mails inexistentes de contatos_ativos.csv e move para contatos_inativos.csv.
"""

import os
import sys
import json
import csv
import imaplib
import email
from email.header import decode_header
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
CONTATOS_ATIVOS = os.path.join(BASE_DIR, "contatos_ativos.csv")
CONTATOS_INATIVOS = os.path.join(BASE_DIR, "contatos_inativos.csv")
ENVIADOS_FILE = os.path.join(BASE_DIR, "enviados.csv")

ENV_FILE = os.path.join(BASE_DIR, ".env")

def carregar_env():
    env_vars = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip("\"'")
    return env_vars

def carregar_config():
    env_data = carregar_env()
    config_json = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config_json = json.load(f)
        except Exception:
            pass

    email_remetente = os.environ.get("EMAIL_REMETENTE", env_data.get("EMAIL_REMETENTE", config_json.get("email_remetente", ""))).strip()
    senha = os.environ.get("EMAIL_SENHA", env_data.get("EMAIL_SENHA", os.environ.get("SENHA", env_data.get("SENHA", config_json.get("senha", ""))))).strip()

    if not email_remetente or not senha or "seu_email" in email_remetente or "sua_senha" in senha:
        print("[-] Configure seu e-mail e senha no arquivo '.env' ou 'config.json' antes de processar bounces.")
        sys.exit(1)

    return {
        "email_remetente": email_remetente,
        "senha": senha
    }

def extrair_emails_bounce(msg):
    """Extrai os e-mails com falha de entrega a partir de uma notificação do Mailer-Daemon."""
    emails_encontrados = set()
    
    # 1. Tentar encontrar via headers específicos de DSN
    for part in msg.walk():
        content_type = part.get_content_type()
        
        # message/delivery-status frequentemente traz o campo Final-Recipient
        if content_type == "message/delivery-status":
            payload = part.get_payload()
            if isinstance(payload, list):
                for subpart in payload:
                    texto = str(subpart)
                    matches = re.findall(r'Final-Recipient:\s*rfc822;\s*([^\s;]+)', texto, re.IGNORECASE)
                    for m in matches:
                        emails_encontrados.add(m.strip().lower())
            else:
                matches = re.findall(r'Final-Recipient:\s*rfc822;\s*([^\s;]+)', str(payload), re.IGNORECASE)
                for m in matches:
                    emails_encontrados.add(m.strip().lower())
        
        # 2. Varrer texto plano buscando padrões como:
        # "Your message wasn't delivered to xxx@domain.com because the address couldn't be found"
        # ou "550 ... <xxx@domain.com>"
        if content_type == "text/plain":
            try:
                texto = part.get_payload(decode=True).decode("utf-8", errors="ignore")
            except:
                texto = str(part.get_payload())
            
            # Padrões comuns do Gmail Delivery Status Notification
            padroes = [
                r"Your message wasn't delivered to\s+([^\s<]+@[^\s>]+)",
                r"The response from the remote server was:.*?([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
                r"Failed to deliver to\s*<?([^\s<]+@[^\s>]+)>?",
                r"Original-Recipient:\s*rfc822;\s*([^\s;]+)",
                r"Action: failed.*?Recipient: <?([^\s<]+@[^\s>]+)>?",
                r"<([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)>:\s*550",
                r"550.*?<([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)>"
            ]
            for p in padroes:
                for match in re.findall(p, texto, re.IGNORECASE | re.DOTALL):
                    emails_encontrados.add(match.strip().lower().rstrip(".,;)>"))
                    
    return emails_encontrados

def buscar_bounces_no_gmail(config):
    print("[+] Conectando ao Gmail via IMAP (imap.gmail.com)...")
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(config["email_remetente"], config["senha"])
        mail.select("INBOX")
        print("[✓] Login no Gmail realizado com sucesso!")
    except Exception as e:
        print(f"[-] Erro ao conectar no IMAP: {e}")
        return set()

    # Buscar e-mails do Mailer-Daemon ou notificações de entrega nas mensagens recentes
    bounced_emails = set()
    
    # Critérios de busca
    queries = [
        'FROM "mailer-daemon@googlemail.com"',
        'FROM "Mail Delivery Subsystem"',
        'SUBJECT "Delivery Status Notification (Failure)"',
        'SUBJECT "Undelivered Mail Returned to Sender"'
    ]

    message_ids = set()
    for q in queries:
        status, data = mail.search(None, q)
        if status == "OK" and data[0]:
            for mid in data[0].split():
                message_ids.add(mid)

    print(f"[+] Total de notificações de bounce identificadas: {len(message_ids)}")

    for mid in message_ids:
        status, data = mail.fetch(mid, "(RFC822)")
        if status != "OK" or not data or not data[0]:
            continue
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        
        encontrados = extrair_emails_bounce(msg)
        for em in encontrados:
            bounced_emails.add(em)

    mail.logout()
    return bounced_emails

def limpar_contatos(bounced_emails):
    if not bounced_emails:
        print("[!] Nenhum e-mail de bounce foi detectado.")
        return

    print(f"\n[+] E-mails detectados como inexistentes ({len(bounced_emails)}):")
    for em in sorted(bounced_emails):
        print(f"  ✗ {em}")

    # 1. Carregar contatos_ativos.csv e filtrar
    if not os.path.exists(CONTATOS_ATIVOS):
        print(f"[-] {CONTATOS_ATIVOS} não existe.")
        return

    with open(CONTATOS_ATIVOS, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        contatos_ativos = list(reader)

    total_antes = len(contatos_ativos)
    novos_ativos = []
    removidos = []

    for c in contatos_ativos:
        email_limpo = c.get("email", "").strip().lower()
        if email_limpo in bounced_emails:
            removidos.append(c)
        else:
            novos_ativos.append(c)

    print(f"\n[+] Contatos em contatos_ativos.csv:")
    print(f"    Antes: {total_antes}")
    print(f"    Removidos: {len(removidos)}")
    print(f"    Restantes: {len(novos_ativos)}")

    # Sobrescrever contatos_ativos.csv
    with open(CONTATOS_ATIVOS, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(novos_ativos)
    print(f"[✓] {CONTATOS_ATIVOS} atualizado com sucesso!")

    # 2. Adicionar aos inativos
    if removidos:
        inativos_existem = os.path.exists(CONTATOS_INATIVOS)
        with open(CONTATOS_INATIVOS, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if not inativos_existem:
                writer.writerow(["nome", "email", "empresa", "servidor_mx", "provedor"])
            for r in removidos:
                writer.writerow([
                    r.get("nome", ""),
                    r.get("email", ""),
                    r.get("empresa", ""),
                    "Caixa Inexistente (550 / Bounce)",
                    "Inativo"
                ])
        print(f"[✓] {len(removidos)} contatos movidos para {CONTATOS_INATIVOS}.")

    # 3. Atualizar status em enviados.csv se aplicável
    if os.path.exists(ENVIADOS_FILE):
        with open(ENVIADOS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            env_fieldnames = reader.fieldnames
            linhas_env = list(reader)

        atualizados = 0
        for l in linhas_env:
            em = l.get("email", "").strip().lower()
            if em in bounced_emails:
                l["status"] = "BOUNCE / EMAIL INEXISTENTE"
                atualizados += 1

        with open(ENVIADOS_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=env_fieldnames)
            writer.writeheader()
            writer.writerows(linhas_env)
        print(f"[✓] {atualizados} registros atualizados em {ENVIADOS_FILE} como BOUNCE.")

def main():
    config = carregar_config()
    bounces = buscar_bounces_no_gmail(config)
    limpar_contatos(bounces)

if __name__ == "__main__":
    main()
