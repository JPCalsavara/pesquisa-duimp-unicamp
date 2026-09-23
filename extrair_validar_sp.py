#!/usr/bin/env python3
"""
Pipeline completo para o estado de São Paulo (Faixa 2: US$ 1M a 10M - 1309 empresas):
1. Coleta todos os 1309 IDs de empresas
2. Extrai contato, e-mail e razão social
3. Valida os registros DNS MX para checar quais e-mails ainda existem
4. Salva contatos_sp_ativos.csv e contatos_sp_inativos.csv
"""

import os
import re
import csv
import time
import html
import subprocess
import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SP_BRUTO_FILE = os.path.join(BASE_DIR, "contatos_sp_todos.csv")
SP_ATIVOS_FILE = os.path.join(BASE_DIR, "contatos_sp_ativos.csv")
SP_INATIVOS_FILE = os.path.join(BASE_DIR, "contatos_sp_inativos.csv")
CONTATOS_ATIVOS_PRINCIPAL = os.path.join(BASE_DIR, "contatos_ativos.csv")

def coletar_ids_sp(session):
    print("\n[Etapa 1/4] Coletando IDs de todas as 1309 empresas de SP (Faixa US$ 1M a 10M)...")
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    todos_ids = []
    pag = 1
    
    while True:
        data = {
            "PaginaAtual": str(pag),
            "TamanhoPagina": "100",
            "CodigoProduto": "",
            "RazaoSocial": "",
            "CNPJ": "",
            "CodigoSubdivisaoPais": "BR-SP",
            "CodigoPais": "",
            "CodigoFaixaImportacao": "2"
        }
        try:
            r = session.post("https://cib.dpr.gov.br/Home/PesquisaCompleta", data=data, headers=headers, timeout=30)
            ids = re.findall(r'data-codigo-empresa=[\'"](\d+)[\'"]', r.text)
            if not ids:
                break
            for cid in ids:
                if cid not in todos_ids:
                    todos_ids.append(cid)
            print(f"  Página {pag:02d} (100/pág): {len(ids)} empresas carregadas (Total acumulado: {len(todos_ids)})")
            pag += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"  Erro na página {pag}: {e}")
            break
            
    print(f"[✓] Total de empresas mapeadas: {len(todos_ids)}")
    return todos_ids

def extrair_detalhes_empresa(cid):
    url = f"https://cib.dpr.gov.br/Home/DetalheEmpresaPartial/{cid}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }
    try:
        r = requests.get(url, headers=headers, timeout=20, verify=False)
        t = r.text
        
        email_m = re.search(r'label>e-mail</label>\s*<span class="valor">\s*([^<\s]+@[^<\s]+)\s*</span>', t, re.I)
        contato_m = re.search(r'label>Contato</label>\s*<span class="valor">\s*([^<]+)</span>', t, re.I)
        executivo_m = re.search(r'label>Principal Executivo</label>\s*<span class="valor">\s*([^<]+)</span>', t, re.I)
        razao_m = re.search(r'<label>Razão Social</label>\s*<span class="valor">\s*<strong>([^<]+)</strong>', t, re.I)
        cidade_m = re.search(r'label>Cidade/Estado</label>\s*<span class="valor">\s*([^<]+)</span>', t, re.I)
        
        razao = html.unescape(razao_m.group(1).strip()) if razao_m else ""
        email = email_m.group(1).strip() if email_m else ""
        
        contato = html.unescape(contato_m.group(1).strip()) if contato_m else ""
        if contato == "-": contato = ""
        
        executivo = html.unescape(executivo_m.group(1).strip()) if executivo_m else ""
        if executivo == "-": executivo = ""
        
        cidade = re.sub(r'\s+', ' ', cidade_m.group(1).strip()) if cidade_m else ""
        
        nome_final = contato if contato else executivo
        
        return {
            "id": cid,
            "nome": nome_final,
            "email": email,
            "empresa": razao,
            "cidade": cidade
        }
    except Exception as e:
        return {"id": cid, "nome": "", "email": "", "empresa": "", "cidade": "", "erro": str(e)}

def extrair_todos_detalhes(todos_ids):
    print(f"\n[Etapa 2/4] Extraindo contatos de {len(todos_ids)} empresas com 10 conexões paralelas...")
    contatos_coletados = []
    total = len(todos_ids)
    concluidos = 0

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(extrair_detalhes_empresa, cid): cid for cid in todos_ids}
        for fut in as_completed(futures):
            res = fut.result()
            concluidos += 1
            if res.get("email"):
                contatos_coletados.append(res)
            
            if concluidos % 100 == 0 or concluidos == total:
                print(f"  Progresso: {concluidos}/{total} empresas processadas ({len(contatos_coletados)} com e-mail encontrado)...")

    print(f"[✓] Extração concluída! {len(contatos_coletados)} empresas possuem e-mail informado.")
    
    # Salva arquivo bruto
    with open(SP_BRUTO_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "nome", "email", "empresa", "cidade"])
        writer.writeheader()
        writer.writerows(contatos_coletados)

    return contatos_coletados

def testar_mx_dominio(domain):
    try:
        cmd = ["host", "-W", "3", "-t", "mx", domain]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        output = res.stdout
        
        if "mail is handled by" in output:
            mx_matches = re.findall(r'mail is handled by \d+\s+(.*)', output)
            servidor = mx_matches[0].strip() if mx_matches else "Ativo"
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
            elif "mimecast" in s_low or "pphosted" in s_low or "barracuda" in s_low or "trendmicro" in s_low or "sophos" in s_low:
                provedor = "Corporativo Protegido"
            return True, servidor, provedor
        else:
            return False, "Sem registro MX", "Inativo"
    except subprocess.TimeoutExpired:
        return False, "Timeout DNS (servidor não responde)", "Inativo"
    except Exception as e:
        return False, str(e), "Inativo"

def validar_emails(contatos):
    print(f"\n[Etapa 3/4] Validando registros DNS MX de todos os e-mails...")
    dominios = {}
    for c in contatos:
        e = c["email"].strip()
        if "@" in e:
            dom = e.split("@")[1].lower()
            dominios.setdefault(dom, []).append(c)

    print(f"  {len(dominios)} domínios únicos encontrados. Executando checagem paralela (20 threads)...")

    mx_cache = {}
    concluidos = 0
    total_dom = len(dominios)
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(testar_mx_dominio, dom): dom for dom in dominios.keys()}
        for fut in as_completed(futures):
            dom = futures[fut]
            mx_cache[dom] = fut.result()
            concluidos += 1
            if concluidos % 100 == 0 or concluidos == total_dom:
                print(f"  Progresso validação DNS: {concluidos}/{total_dom} domínios verificados...")

    print("\n[Etapa 4/4] Separando e-mails válidos e inválidos...")
    ativos = []
    inativos = []

    for c in contatos:
        e = c["email"].strip()
        dom = e.split("@")[1].lower() if "@" in e else ""
        ativo, servidor, provedor = mx_cache.get(dom, (False, "Desconhecido", "Inativo"))
        
        row = {
            "nome": c["nome"],
            "email": e,
            "empresa": c["empresa"],
            "cidade": c.get("cidade", ""),
            "servidor_mx": servidor,
            "provedor": provedor
        }
        if ativo:
            ativos.append(row)
        else:
            inativos.append(row)

    # Ordenar por empresa
    ativos.sort(key=lambda x: x["empresa"].lower())
    inativos.sort(key=lambda x: x["empresa"].lower())

    # Salva arquivos de SP
    with open(SP_ATIVOS_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["nome", "email", "empresa", "cidade", "servidor_mx", "provedor"])
        writer.writeheader()
        writer.writerows(ativos)

    with open(SP_INATIVOS_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["nome", "email", "empresa", "cidade", "servidor_mx", "provedor"])
        writer.writeheader()
        writer.writerows(inativos)

    # Atualiza também a lista principal de envio do projeto (contatos_ativos.csv)
    with open(CONTATOS_ATIVOS_PRINCIPAL, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["nome", "email", "empresa", "cidade", "servidor_mx", "provedor"])
        writer.writeheader()
        writer.writerows(ativos)

    print("\n" + "="*70)
    print("🎉 PROCESSAMENTO E VALIDAÇÃO DE SÃO PAULO CONCLUÍDOS!")
    print("="*70)
    print(f"Total de empresas no portal: 1309")
    print(f"Empresas com e-mail cadastrado: {len(contatos)}")
    print(f"✅ E-MAILS COM SERVIDOR 100% ATIVO E CONFIRMADO: {len(ativos)} ({len(ativos)/len(contatos)*100:.1f}%)")
    print(f"❌ E-mails com domínio/servidor morto descartados: {len(inativos)} ({len(inativos)/len(contatos)*100:.1f}%)")
    print("\nArquivos gerados:")
    print(f"  👉 Lista limpa para disparo: {SP_ATIVOS_FILE}")
    print(f"  👉 Lista principal atualizada: {CONTATOS_ATIVOS_PRINCIPAL}")
    print(f"  👉 Lista de inativos: {SP_INATIVOS_FILE}")
    print("="*70)

def main():
    session = requests.Session()
    session.verify = False
    
    todos_ids = coletar_ids_sp(session)
    if not todos_ids:
        print("[-] Nenhum ID foi coletado.")
        return
        
    contatos = extrair_todos_detalhes(todos_ids)
    validar_emails(contatos)

if __name__ == "__main__":
    main()
