#!/usr/bin/env python3
"""
Script auxiliar para extrair contatos (Nome, Email, Empresa) diretamente do portal CIB / DPR:
https://cib.dpr.gov.br/Home/PesquisaCompleta

Salva os resultados diretamente em contatos.csv.
"""

import os
import re
import csv
import time
import html
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTATOS_FILE = os.path.join(BASE_DIR, "contatos.csv")

def extrair_detalhes_empresa(session, id_empresa):
    url = f"https://cib.dpr.gov.br/Home/DetalheEmpresaPartial/{id_empresa}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    r = session.get(url, headers=headers, timeout=20)
    if r.status_code != 200:
        return None
        
    html = r.text
    
    # Extrair Razão Social
    razao_m = re.search(r'<label>Razão Social</label>\s*<span class="valor">\s*<strong>([^<]+)</strong>', html, re.I)
    razao = html.unescape(razao_m.group(1).strip()) if razao_m else ""
    
    # Extrair e-mail
    email_m = re.search(r'<label>e-mail</label>\s*<span class="valor">\s*([^<\s]+@[^<\s]+)\s*</span>', html, re.I)
    email = email_m.group(1).strip() if email_m else ""
    
    # Extrair Contato
    contato_m = re.search(r'<label>Contato</label>\s*<span class="valor">\s*([^<]+)</span>', html, re.I)
    contato = html.unescape(contato_m.group(1).strip()) if contato_m else ""
    if contato == "-":
        contato = ""
        
    # Se contato estiver vazio, tenta "Principal Executivo"
    if not contato:
        exec_m = re.search(r'<label>Principal Executivo</label>\s*<span class="valor">\s*([^<]+)</span>', html, re.I)
        if exec_m:
            val = html.unescape(exec_m.group(1).strip())
            if val and val != "-":
                contato = val

    if not email:
        return None

    return {
        "nome": contato,
        "email": email,
        "empresa": razao
    }

def buscar_empresas_cib(sh="850151", faixa="2", max_paginas=5):
    """
    Busca empresas por Código SH e Faixa de importação:
    sh: Código NCM/SH do produto (ex: '850151')
    faixa:
      1: até US$ 1 milhão
      2: de US$ 1 milhão a US$ 10 milhões
      3: de US$ 10 milhões a US$ 50 milhões
      4: acima de US$ 50 milhões
    """
    session = requests.Session()
    session.verify = False
    
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # Carregar contatos já existentes para não duplicar
    existentes = set()
    if os.path.exists(CONTATOS_FILE):
        with open(CONTATOS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                e = r.get("email", "").strip().lower()
                if e:
                    existentes.add(e)

    print(f"[+] Iniciando busca no CIB DPR (Código SH: '{sh}', Faixa: {faixa}, até {max_paginas} páginas)...")
    
    novos = []
    
    for pag in range(1, max_paginas + 1):
        print(f"\n--- Página {pag} ---")
        data = {
            "PaginaAtual": str(pag),
            "TamanhoPagina": "10",
            "CodigoProduto": str(sh) if sh else "",
            "RazaoSocial": "",
            "CNPJ": "",
            "CodigoSubdivisaoPais": "",
            "CodigoPais": "",
            "CodigoFaixaImportacao": str(faixa)
        }
        
        try:
            r = session.post("https://cib.dpr.gov.br/Home/PesquisaCompleta", data=data, headers=headers, timeout=30)
        except Exception as e:
            print(f"[-] Erro ao carregar página {pag}: {e}")
            break

        ids = re.findall(r'data-codigo-empresa=[\'"](\d+)[\'"]', r.text)
        if not ids:
            print("[!] Nenhuma empresa encontrada ou fim dos resultados.")
            break
            
        print(f"[+] Encontradas {len(ids)} empresas na página {pag}.")
        
        for id_emp in ids:
            try:
                dados = extrair_detalhes_empresa(session, id_emp)
                if dados and dados["email"]:
                    e_low = dados["email"].lower()
                    if e_low in existentes:
                        print(f"  [-] Já existe: {dados['email']}")
                        continue
                    
                    existentes.add(e_low)
                    novos.append(dados)
                    print(f"  [✓] Capturado: {dados['nome'] or 'Sem nome'} | {dados['email']} | {dados['empresa']}")
                else:
                    print(f"  [-] Empresa ID {id_emp} sem e-mail cadastrado.")
                time.sleep(0.2)
            except Exception as ex:
                print(f"  [-] Erro ID {id_emp}: {ex}")

    if novos:
        # Salva em contatos.csv
        file_exists = os.path.exists(CONTATOS_FILE)
        with open(CONTATOS_FILE, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["nome", "email", "empresa"])
            for item in novos:
                writer.writerow([item["nome"], item["email"], item["empresa"]])
        print(f"\n[✓] Sucesso! {len(novos)} novos contatos adicionados ao '{CONTATOS_FILE}'.")
    else:
        print("\n[!] Nenhum novo contato foi capturado nesta execução.")

if __name__ == "__main__":
    import sys
    sh = sys.argv[1] if len(sys.argv) > 1 else "850151"
    faixa = sys.argv[2] if len(sys.argv) > 2 else "2"
    paginas = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    buscar_empresas_cib(sh=sh, faixa=faixa, max_paginas=paginas)
