#!/usr/bin/env python3
"""
Script para extrair TODAS as empresas e contatos cadastrados no CIB DPR para:
- Código SH: 850151
- Faixa de Importação: 2 (de US$ 1 milhão a US$ 10 milhões)

Salva diretamente em contatos.csv.
"""

import os
import re
import csv
import time
import html
import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTATOS_FILE = os.path.join(BASE_DIR, "contatos.csv")

def extrair_detalhes(session, cid, pag, total):
    url = f"https://cib.dpr.gov.br/Home/DetalheEmpresaPartial/{cid}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }
    try:
        r = session.get(url, headers=headers, timeout=20)
        t = r.text
        
        email_m = re.search(r'label>e-mail</label>\s*<span class="valor">\s*([^<\s]+@[^<\s]+)\s*</span>', t, re.I)
        contato_m = re.search(r'label>Contato</label>\s*<span class="valor">\s*([^<]+)</span>', t, re.I)
        executivo_m = re.search(r'label>Principal Executivo</label>\s*<span class="valor">\s*([^<]+)</span>', t, re.I)
        razao_m = re.search(r'<label>Razão Social</label>\s*<span class="valor">\s*<strong>([^<]+)</strong>', t, re.I)
        
        razao = html.unescape(razao_m.group(1).strip()) if razao_m else ""
        email = email_m.group(1).strip() if email_m else ""
        
        contato = html.unescape(contato_m.group(1).strip()) if contato_m else ""
        if contato == "-": contato = ""
        
        executivo = html.unescape(executivo_m.group(1).strip()) if executivo_m else ""
        if executivo == "-": executivo = ""
        
        nome_final = contato if contato else executivo
        
        return {
            "id": cid,
            "nome": nome_final,
            "email": email,
            "empresa": razao
        }
    except Exception as e:
        return {"id": cid, "nome": "", "email": "", "empresa": "", "erro": str(e)}

def main():
    session = requests.Session()
    session.verify = False
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print("[1/2] Mapeando todas as páginas e IDs da busca (SH 850151 | Faixa 2)...")
    todos_ids = []
    pag = 1
    
    while True:
        data = {
            "PaginaAtual": str(pag),
            "TamanhoPagina": "10",
            "CodigoProduto": "850151",
            "RazaoSocial": "",
            "CNPJ": "",
            "CodigoSubdivisaoPais": "",
            "CodigoPais": "",
            "CodigoFaixaImportacao": "2"
        }
        try:
            r = session.post("https://cib.dpr.gov.br/Home/PesquisaCompleta", data=data, headers=headers, timeout=30)
            cids = re.findall(r'data-codigo-empresa=[\'"](\d+)[\'"]', r.text)
            if not cids:
                break
            for cid in cids:
                if cid not in todos_ids:
                    todos_ids.append(cid)
            print(f"  Página {pag:02d}: {len(cids)} empresas (acumulado: {len(todos_ids)})")
            pag += 1
        except Exception as e:
            print(f"  Erro na página {pag}: {e}")
            break

    total_empresas = len(todos_ids)
    print(f"\n[2/2] Extraindo detalhes e contatos de todas as {total_empresas} empresas...")

    resultados = []
    sem_email = 0

    # Usamos ThreadPoolExecutor para ser ágil e confiável
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(extrair_detalhes, session, cid, i, total_empresas): cid for i, cid in enumerate(todos_ids, 1)}
        for future in as_completed(futures):
            res = future.result()
            if res.get("email"):
                resultados.append(res)
                print(f"  [✓] {res['nome'] or 'Sem nome'} | {res['email']} | {res['empresa']}")
            else:
                sem_email += 1
                if res.get("empresa"):
                    print(f"  [-] Sem e-mail cadastrado: {res['empresa']}")

    # Ordenar por nome da empresa
    resultados.sort(key=lambda x: x["empresa"].lower())

    # Salvar em contatos.csv
    with open(CONTATOS_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["nome", "email", "empresa"])
        for r in resultados:
            writer.writerow([r["nome"], r["email"], r["empresa"]])

    print("\n" + "="*60)
    print(f"✓ EXTRAÇÃO COMPLETA FINALIZADA COM SUCESSO!")
    print(f"  Total de empresas analisadas: {total_empresas}")
    print(f"  Contatos válidos com e-mail: {len(resultados)}")
    print(f"  Empresas sem e-mail cadastrado no CIB: {sem_email}")
    print(f"  Arquivo salvo: {CONTATOS_FILE}")
    print("="*60)

if __name__ == "__main__":
    main()
