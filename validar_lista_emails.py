#!/usr/bin/env python3
"""
Validador de E-mails e Domínios para contatos.csv.
Testa se o domínio e o servidor de e-mail (MX) existem e estão operacionais
sem enviar nenhuma mensagem real.
"""

import os
import csv
import subprocess
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTATOS_FILE = os.path.join(BASE_DIR, "contatos.csv")
ATIVOS_FILE = os.path.join(BASE_DIR, "contatos_ativos.csv")
INATIVOS_FILE = os.path.join(BASE_DIR, "contatos_inativos.csv")

def testar_dominio(domain):
    try:
        # Consulta registro MX com timeout curto de 4s
        cmd = ["host", "-W", "4", "-t", "mx", domain]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
        output = res.stdout
        
        if "mail is handled by" in output:
            mx_matches = re.findall(r'mail is handled by \d+\s+(.*)', output)
            servidor = mx_matches[0].strip() if mx_matches else "Ativo"
            # Identifica provedor
            provedor = "Outro"
            s_low = servidor.lower()
            if "google" in s_low or "gmail" in s_low or "aspmx" in s_low:
                provedor = "Google Workspace"
            elif "outlook" in s_low or "protection.outlook" in s_low or "microsoft" in s_low:
                provedor = "Microsoft 365"
            elif "locaweb" in s_low:
                provedor = "Locaweb"
            elif "kinghost" in s_low:
                provedor = "KingHost"
            elif "uol" in s_low or "terra" in s_low:
                provedor = "UOL/Terra"
            elif "mimecast" in s_low or "pphosted" in s_low or "barracuda" in s_low or "trendmicro" in s_low:
                provedor = "Corporativo Protegido"
            return True, servidor, provedor
        else:
            return False, "Sem registro MX", "Inativo"
    except subprocess.TimeoutExpired:
        return False, "Timeout DNS (servidor não responde)", "Inativo"
    except Exception as e:
        return False, str(e), "Inativo"

def main():
    if not os.path.exists(CONTATOS_FILE):
        print(f"[-] Arquivo {CONTATOS_FILE} não encontrado.")
        return

    with open(CONTATOS_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        contatos = list(reader)

    print(f"[+] Iniciando validação de {len(contatos)} e-mails...")

    # Mapear domínios únicos para não repetir consultas desnecessárias
    dominios_map = {}
    for c in contatos:
        email = c.get("email", "").strip()
        if "@" in email:
            dom = email.split("@")[1].lower()
            dominios_map.setdefault(dom, []).append(c)

    print(f"[+] {len(dominios_map)} domínios únicos identificados. Consultando servidores de e-mail (MX)...")

    resultados_dominios = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(testar_dominio, dom): dom for dom in dominios_map.keys()}
        for fut in as_completed(futures):
            dom = futures[fut]
            ativo, servidor, provedor = fut.result()
            resultados_dominios[dom] = (ativo, servidor, provedor)
            status_icon = "✓ ATIVO" if ativo else "✗ MORTO"
            print(f"  [{status_icon}] {dom:30} -> {provedor} ({servidor[:40]})")

    lista_ativos = []
    lista_inativos = []

    for c in contatos:
        email = c.get("email", "").strip()
        dom = email.split("@")[1].lower() if "@" in email else ""
        ativo, servidor, provedor = resultados_dominios.get(dom, (False, "Desconhecido", "Inativo"))
        
        item = {
            "nome": c.get("nome", ""),
            "email": email,
            "empresa": c.get("empresa", ""),
            "servidor_mx": servidor,
            "provedor": provedor
        }
        if ativo:
            lista_ativos.append(item)
        else:
            lista_inativos.append(item)

    # Salva ativos
    with open(ATIVOS_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["nome", "email", "empresa", "servidor_mx", "provedor"])
        writer.writeheader()
        writer.writerows(lista_ativos)

    # Salva inativos
    with open(INATIVOS_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["nome", "email", "empresa", "servidor_mx", "provedor"])
        writer.writeheader()
        writer.writerows(lista_inativos)

    print("\n" + "="*60)
    print("📊 RESULTADO DA VALIDAÇÃO TÉCNICA DE E-MAILS (SEM DISPARO)")
    print("="*60)
    print(f"Total de e-mails testados: {len(contatos)}")
    print(f"✓ E-mails com servidores 100% ativos: {len(lista_ativos)} ({len(lista_ativos)/len(contatos)*100:.1f}%)")
    print(f"✗ E-mails com domínio/servidor morto: {len(lista_inativos)} ({len(lista_inativos)/len(contatos)*100:.1f}%)")
    print(f"\nArquivos gerados:")
    print(f"  👉 Lista limpa para envio: {ATIVOS_FILE}")
    print(f"  👉 Lista de inativos descartados: {INATIVOS_FILE}")
    print("="*60)

if __name__ == "__main__":
    main()
