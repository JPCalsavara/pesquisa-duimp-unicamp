#!/usr/bin/env python3
"""
Script de automação para envio de e-mails da pesquisa acadêmica Unicamp.
Lê os contatos de contatos.csv, personaliza a mensagem e envia via SMTP.
Garante que nenhum e-mail seja enviado duas vezes (salva em enviados.csv).
"""

import os
import sys
import csv
import time
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
CONTATOS_ATIVOS = os.path.join(BASE_DIR, "contatos_ativos.csv")
CONTATOS_PADRAO = os.path.join(BASE_DIR, "contatos.csv")
CONTATOS_FILE = CONTATOS_ATIVOS if os.path.exists(CONTATOS_ATIVOS) else CONTATOS_PADRAO
ENVIADOS_FILE = os.path.join(BASE_DIR, "enviados.csv")

ASSUNTO_PADRAO = "Você aceita melhorar a eficiência operacional das importações junto aos alunos da Unicamp?"

ENV_FILE = os.path.join(BASE_DIR, ".env")

CORPO_TEMPLATE = """{saudacao}

Meu nome é {nome_remetente}, sou estudante de Análise e Desenvolvimento de Sistemas na Unicamp. Nosso grupo está desenvolvendo um projeto de pesquisa acadêmica sobre os principais desafios operacionais que empresas que operam com importação internacional enfrentam, possíveis atritos com exigência de dados e integração com o Siscomex.

Um feedback de quem conhece o processo de verdade é fundamental para o nosso levantamento. Não se trata de nenhuma oferta comercial, venda de produto ou afins, nosso objetivo é simplesmente compreender sobre os fluxos reais de trabalho.

A fim de sermos objetivos e economizar tempo, preparamos 4 perguntas curtas. Se aceitar participar voluntariamente deste levantamento, basta respondê-las diretamente por este e-mail (as perguntas estão logo abaixo). Suas respostas nos guiarão profundamente:

1. Perfil da Operação: Vocês realizam o cadastro no Catálogo DUIMP internamente ou delegam essa etapa para um despachante aduaneiro?
R:

2. Gargalo Operacional: No cadastro de lotes com muitos itens, onde a equipe mais gasta tempo e esforço: classificação correta dos NCMs, ou na busca e preenchimento dos atributos? Este processo é manual?
R:

3. Origem dos Dados: No dia a dia, a Invoice e o Packing List enviados pelos fornecedores trazem todos os detalhes técnicos que o catálogo da DUIMP exige (Atributos por NCM), ou a equipe precisa buscar dados em catálogos, fichas técnicas (datasheets) ou sites de fabricantes?
R:

4. Ferramentas Atuais: Como vocês fazem a gestão e o preenchimento do catálogo DUIMP? Preencher diretamente no sistema de forma manual? Utilizam planilhas? Utilizam software para agilizar o processo de preenchimento?
R:

---

Possibilidade de Aprofundamento:
Caso faça sentido para você, poderíamos agendar um bate-papo curto de ~10 minutos (ou trocar áudios por WhatsApp) para entender melhor sobre o processo?

Além disso, para a etapa prática do estudo na Unicamp, uma contribuição adicional seria o compartilhamento de um exemplo de invoice ou planilha, 100% descaracterizada e sem nenhum dado confidencial, apenas para modelarmos os atributos na pesquisa acadêmica.

Agradeço desde já pela atenção e pelo apoio à pesquisa acadêmica da Unicamp.

Atenciosamente,

{nome_remetente}
Faculdade de Tecnologia - Unicamp"""

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

    # Variáveis de ambiente ou .env têm prioridade; fallback para config.json
    email_remetente = os.environ.get("EMAIL_REMETENTE", env_data.get("EMAIL_REMETENTE", config_json.get("email_remetente", ""))).strip()
    senha = os.environ.get("EMAIL_SENHA", env_data.get("EMAIL_SENHA", os.environ.get("SENHA", env_data.get("SENHA", config_json.get("senha", ""))))).strip()
    nome_remetente = os.environ.get("NOME_REMETENTE", env_data.get("NOME_REMETENTE", config_json.get("nome_remetente", "João Calsavara"))).strip()
    smtp_server = os.environ.get("SMTP_SERVER", env_data.get("SMTP_SERVER", config_json.get("smtp_server", "smtp.gmail.com"))).strip()
    
    try:
        smtp_port = int(os.environ.get("SMTP_PORT", env_data.get("SMTP_PORT", config_json.get("smtp_port", 587))))
    except (ValueError, TypeError):
        smtp_port = 587

    try:
        delay_segundos = int(os.environ.get("DELAY_SEGUNDOS", env_data.get("DELAY_SEGUNDOS", config_json.get("delay_segundos", 2))))
    except (ValueError, TypeError):
        delay_segundos = 2

    try:
        limite_diario = int(os.environ.get("LIMITE_DIARIO", env_data.get("LIMITE_DIARIO", config_json.get("limite_diario", 300))))
    except (ValueError, TypeError):
        limite_diario = 300

    if not email_remetente or not senha or "seu_email" in email_remetente or "sua_senha" in senha or "xxxx" in senha:
        print("[!] ATENÇÃO: Configure seu e-mail e senha no arquivo '.env' ou 'config.json' antes de enviar.")
        print("[!] Veja os modelos '.env.example' e 'config.example.json' para preencher com seus dados.")
        return None

    return {
        "email_remetente": email_remetente,
        "senha": senha,
        "nome_remetente": nome_remetente,
        "smtp_server": smtp_server,
        "smtp_port": smtp_port,
        "delay_segundos": delay_segundos,
        "limite_diario": limite_diario
    }

def carregar_enviados():
    enviados = set()
    if os.path.exists(ENVIADOS_FILE):
        with open(ENVIADOS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                status = row.get("status", "").strip()
                # Erros não contam como enviados (para que possam ser tentados novamente)
                if status.startswith("ERRO"):
                    continue
                email = row.get("email", "").strip().lower()
                if email:
                    enviados.add(email)
    return enviados

def contar_envios_24h(email_remetente=None):
    """
    Conta quantos e-mails foram enviados com sucesso nas últimas 24 horas.
    Permite filtrar por remetente específico para equipes trabalhando em conjunto.
    """
    if not os.path.exists(ENVIADOS_FILE):
        return 0

    limite_tempo = datetime.now() - timedelta(hours=24)
    total_24h = 0

    with open(ENVIADOS_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            status = row.get("status", "").strip()
            if status.startswith("ERRO"):
                continue

            data_str = row.get("data_hora", "").strip()
            if not data_str:
                continue

            try:
                dt = datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue

            if dt >= limite_tempo:
                rem_row = row.get("remetente", "").strip().lower()
                if email_remetente and rem_row:
                    if rem_row == email_remetente.lower():
                        total_24h += 1
                else:
                    total_24h += 1

    return total_24h

def registrar_envio(nome, email, empresa, status="ENVIADO", remetente=""):
    existe = os.path.exists(ENVIADOS_FILE)
    with open(ENVIADOS_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not existe:
            writer.writerow(["data_hora", "nome", "email", "empresa", "status", "remetente"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            nome,
            email,
            empresa,
            status,
            remetente
        ])

def formatar_saudacao(nome_completo):
    nome = nome_completo.strip()
    if not nome or nome.lower() in ["contato", "comercial", "sac", "n/a", "-"]:
        return "Olá, tudo bem?"
    # Pega o primeiro nome capitalizado
    primeiro_nome = nome.split()[0].title()
    return f"Olá, {primeiro_nome}, tudo bem?"

def gerar_mensagem(nome_contato, nome_remetente="João Calsavara"):
    saudacao = formatar_saudacao(nome_contato)
    return CORPO_TEMPLATE.format(saudacao=saudacao, nome_remetente=nome_remetente)

def ler_contatos():
    if not os.path.exists(CONTATOS_FILE):
        print(f"[-] Arquivo de contatos não encontrado: {CONTATOS_FILE}")
        sys.exit(1)
    
    contatos = []
    with open(CONTATOS_FILE, "r", encoding="utf-8") as f:
        # Detecta delimitador (, ou ;)
        sample = f.read(2048)
        f.seek(0)
        delimiter = ";" if ";" in sample and sample.count(";") > sample.count(",") else ","
        reader = csv.DictReader(f, delimiter=delimiter)
        for i, row in enumerate(reader, start=2):
            # Procura chaves mesmo com variações de maiúsculas/espaços
            row_clean = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            nome = row_clean.get("nome", row_clean.get("contato", ""))
            email = row_clean.get("email", row_clean.get("e-mail", ""))
            empresa = row_clean.get("empresa", row_clean.get("razao_social", row_clean.get("razão social", "")))
            
            if not email:
                continue
            contatos.append({
                "linha": i,
                "nome": nome,
                "email": email,
                "empresa": empresa
            })
    return contatos

def simular_envios(contatos, nome_remetente="João Calsavara", email_remetente=None, limite_diario=300):
    print("\n" + "="*60)
    print(" 🔍 MODO SIMULAÇÃO (DRY RUN) - NENHUM E-MAIL SERÁ ENVIADO")
    print("="*60)
    
    enviados = carregar_enviados()
    pendentes = [c for c in contatos if c["email"].lower() not in enviados]
    envios_24h = contar_envios_24h(email_remetente)
    
    print(f"Remetente: {nome_remetente} ({email_remetente or 'Não configurado'})")
    print(f"Cota nas últimas 24h: {envios_24h}/{limite_diario} e-mails")
    if envios_24h >= limite_diario:
        print("⛔ ATENÇÃO: Cota diária máxima de 24h atingida para este remetente!")
    print(f"Total de contatos na planilha: {len(contatos)}")
    print(f"Já enviados anteriormente: {len(contatos) - len(pendentes)}")
    print(f"Pendentes de envio: {len(pendentes)}\n")
    
    if not pendentes:
        print("[✓] Todos os contatos da lista já receberam e-mail!")
        return

    for idx, c in enumerate(pendentes[:3], start=1):
        corpo = gerar_mensagem(c["nome"], nome_remetente)
        print(f"--- [Exemplo {idx} de {len(pendentes)}] ---")
        print(f"De: {nome_remetente}")
        print(f"Para: {c['nome']} <{c['email']}>")
        print(f"Empresa: {c['empresa']}")
        print(f"Assunto: {ASSUNTO_PADRAO}")
        print("Corpo da mensagem:")
        print(corpo)
        print("-" * 60 + "\n")
    
    if len(pendentes) > 3:
        print(f"... e mais {len(pendentes) - 3} contatos serão enviados com o mesmo padrão.")

def conectar_smtp(config):
    server = smtplib.SMTP(config["smtp_server"], config["smtp_port"], timeout=20)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(config["email_remetente"], config["senha"])
    return server

def enviar_todos(limite=None, auto_confirm=False):
    config = carregar_config()
    contatos = ler_contatos()
    
    if not contatos:
        print("[!] Nenhum contato encontrado em contatos.csv.")
        return

    enviados = carregar_enviados()
    pendentes = [c for c in contatos if c["email"].lower() not in enviados]

    if not pendentes:
        print("[✓] Todos os contatos da lista já constam como enviados em enviados.csv!")
        return

    if limite and limite > 0:
        pendentes = pendentes[:limite]

    print(f"\n[+] Total de contatos selecionados para envio: {len(pendentes)}")
    
    if not config:
        print("\nPara testar a formatação das mensagens sem enviar, execute:")
        print("  python3 enviar_emails.py --dry-run\n")
        return

    remetente_email = config["email_remetente"]
    nome_remetente = config.get("nome_remetente", "João Calsavara")
    limite_diario = config.get("limite_diario", 300)
    delay = config.get("delay_segundos", 2)

    # Verificação de segurança da cota diária nas últimas 24 horas
    envios_24h = contar_envios_24h(remetente_email)

    print(f"[+] Remetente configurado: {remetente_email} ({nome_remetente})")
    print(f"[+] Cota utilizada nas últimas 24h: {envios_24h}/{limite_diario} e-mails")
    print(f"[+] Intervalo entre envios: {delay} segundos")

    # ⛔ TRAVA DE SEGURANÇA: Se já atingiu a cota diária, aborta antes de abrir conexão
    if envios_24h >= limite_diario:
        print("\n" + "="*72)
        print(" ⛔ TRAVA DE SEGURANÇA ATIVADA: COTA DIÁRIA ATINGIDA")
        print("="*72)
        print(f"O remetente '{remetente_email}' já realizou {envios_24h} envios nas últimas 24 horas.")
        print(f"O limite máximo seguro diário é de {limite_diario} e-mails por conta.")
        print("O envio foi BLOQUEADO para proteger sua conta do Gmail contra bloqueio/suspensão.")
        print("\nComo prosseguir:")
        print("  1. Outro colega do grupo pode rodar este script configurando o próprio e-mail no .env")
        print("  2. Ou aguarde até que a janela de 24 horas libere novos envios.")
        print("="*72 + "\n")
        return

    cota_restante = limite_diario - envios_24h
    if len(pendentes) > cota_restante:
        print(f"\n[!] Atenção: Sua cota diária restante é de {cota_restante} e-mails.")
        print(f"[!] Ajustando o lote atual de {len(pendentes)} para {cota_restante} contatos para respeitar a cota.")
        pendentes = pendentes[:cota_restante]

    print(f"\n[+] Total de contatos selecionados para envio nesta rodada: {len(pendentes)}")

    if not auto_confirm:
        confirma = input("\nDeseja iniciar os disparos reais agora? (digite 'sim' para confirmar): ").strip().lower()
        if confirma != "sim":
            print("Operação cancelada pelo usuário.")
            return

    print("\n[+] Conectando ao servidor SMTP...")
    try:
        server = conectar_smtp(config)
        print("[✓] Conexão autenticada com sucesso!\n")
    except Exception as e:
        print(f"[-] Falha ao autenticar no servidor SMTP: {e}")
        return

    total = len(pendentes)

    try:
        for idx, c in enumerate(pendentes, start=1):
            # Trava em tempo real caso alcance a cota durante o loop
            if envios_24h + idx > limite_diario:
                print(f"\n[!] Cota diária atingida ({limite_diario} e-mails nas últimas 24h).")
                print("[!] Encerrando envio com segurança para proteger a conta.")
                break

            nome = c["nome"]
            destinatario = c["email"]
            empresa = c["empresa"]

            print(f"[{idx}/{total}] Enviando e-mail para: {destinatario} ({nome or 'Sem nome'})...", end=" ", flush=True)

            msg = MIMEMultipart("alternative")
            msg["Subject"] = Header(ASSUNTO_PADRAO, "utf-8").encode()
            
            msg["From"] = formataddr((str(Header(nome_remetente, "utf-8")), remetente_email))
            msg["To"] = formataddr((str(Header(nome, "utf-8")), destinatario))

            corpo = gerar_mensagem(nome, nome_remetente)
            msg.attach(MIMEText(corpo, "plain", "utf-8"))

            try:
                server.sendmail(remetente_email, [destinatario], msg.as_string())
                registrar_envio(nome, destinatario, empresa, "ENVIADO", remetente_email)
                print("✓ Enviado com sucesso!")
            except Exception as env_err:
                err_str = str(env_err)
                print(f"✗ Erro: {err_str}")
                registrar_envio(nome, destinatario, empresa, f"ERRO: {err_str}", remetente_email)

                # Limite diário do Gmail atingido (500 e-mails/dia via SMTP)
                if "Daily user sending limit exceeded" in err_str or "5.4.5" in err_str:
                    print("\n" + "="*70)
                    print("[!] ATENÇÃO: LIMITE DIÁRIO DO GMAIL ATINGIDO (Erro 550 / 5.4.5).")
                    print("[!] O Google limita contas a 500 envios por dia via SMTP.")
                    print("[!] O envio foi travado imediatamente para proteger a sua conta.")
                    print("[!] Peça para outro colega continuar os envios no .env.")
                    print("="*70 + "\n")
                    break

                # Conexão encerrada pelo servidor
                if "please run connect() first" in err_str or "Connection unexpectedly closed" in err_str:
                    print("\n[!] Conexão com o servidor SMTP foi encerrada. Interrompendo envio.")
                    break

            if idx < total:
                time.sleep(delay)

    except KeyboardInterrupt:
        print("\n\n[!] Envio interrompido pelo usuário. O progresso foi salvo em enviados.csv.")
    finally:
        try:
            server.quit()
        except:
            pass

    print(f"\n[✓] Processo finalizado! {total} e-mails processados. Consulte o histórico em 'enviados.csv'.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Automação de Envio de E-mails Unicamp")
    parser.add_argument("--dry-run", "--simular", action="store_true", help="Simular envios sem disparar e-mails reais")
    parser.add_argument("--limite", type=int, default=None, help="Limite de e-mails a enviar")
    parser.add_argument("--yes", "-y", action="store_true", help="Confirmar automaticamente sem perguntar")
    args = parser.parse_args()

    if args.dry_run:
        config = carregar_config()
        nome_rem = config.get("nome_remetente", "Remetente") if config else "Remetente"
        email_rem = config.get("email_remetente") if config else None
        lim_diario = config.get("limite_diario", 300) if config else 300
        contatos = ler_contatos()
        if args.limite:
            contatos = contatos[:args.limite]
        simular_envios(contatos, nome_rem, email_rem, lim_diario)
    else:
        enviar_todos(limite=args.limite, auto_confirm=args.yes)
