# Automação de E-mails - Pesquisa Acadêmica Unicamp (DUIMP)

Sistema completo para envio automatizado e personalizado de e-mails para contatos aduaneiros/importadores cadastrados no CIB DPR.

---

## 📁 Estrutura de Arquivos

- [enviar_emails.py](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/enviar_emails.py) — Script principal que personaliza a mensagem e realiza os disparos via SMTP.
- [processar_bounces.py](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/processar_bounces.py) — Lê notificações de erro de entrega via IMAP no Gmail e higieniza a base.
- [contatos_ativos.csv](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/contatos_ativos.csv) — Lista de contatos válidos e higienizados pronta para disparo.
- [contatos_inativos.csv](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/contatos_inativos.csv) — Histórico de contatos descartados (bounces / sem MX).
- [contatos.csv](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/contatos.csv) — Lista original de contatos (`nome,email,empresa`).
- [config.json](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/config.json) — Configuração do remetente e servidor SMTP.
- [enviados.csv](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/enviados.csv) — Histórico automático para garantir que ninguém receba e-mail repetido.
- [extrair_cib.py](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/extrair_cib.py) — Script que puxa automaticamente empresas do site CIB DPR para a planilha.
- [console_cib_extractor.js](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/console_cib_extractor.js) — Snippet para o Console do Chrome (F12) para copiar contatos com 1 clique se estiver navegando manualmente.

---

## 🚀 Passo a Passo de Uso

### 1. Configurar suas Credenciais de E-mail (Suporte a Múltiplos Remetentes)

Qualquer integrante do grupo pode disparar e-mails com a sua própria conta Gmail pessoal. O sistema detecta o nome do remetente e personaliza automaticamente a saudação e a assinatura de cada e-mail.

Você pode configurar suas credenciais de duas maneiras:

#### Opção A (Recomendada): Usando arquivo `.env`
1. Copie o arquivo de exemplo:
   ```bash
   cp .env.example .env
   ```
2. Abra o [.env](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/.env) e preencha com seus dados:
   ```env
   NOME_REMETENTE=Seu Nome Completo
   EMAIL_REMETENTE=seu_email@gmail.com
   EMAIL_SENHA=xxxx xxxx xxxx xxxx
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   DELAY_SEGUNDOS=2
   ```

#### Opção B: Usando `config.json`
Se preferir usar JSON, copie [config.example.json](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/config.example.json) para `config.json` e preencha:
```json
{
  "smtp_server": "smtp.gmail.com",
  "smtp_port": 587,
  "email_remetente": "seu_email@gmail.com",
  "senha": "xxxx xxxx xxxx xxxx",
  "nome_remetente": "Seu Nome Completo",
  "delay_segundos": 2
}
```

> **Como gerar a senha de aplicativo no Gmail:**
> 1. Acesse sua Conta Google > **Segurança** > **Verificação em duas etapas** (deve estar ativada).
> 2. Procure por **Senhas de aplicativo** (ou acesse `myaccount.google.com/apppasswords`).
> 3. Crie uma senha com o nome `Pesquisa DUIMP` e copie o código gerado de 16 caracteres.
> *(Obs: o arquivo `.env` e `config.json` estão protegidos pelo `.gitignore` e nunca serão enviados para o GitHub).*

---

### 2. Alimentar a Lista de Contatos ([contatos.csv](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/contatos.csv))

Você pode preencher de três formas:

1. **Manualmente:** Abrir [contatos.csv](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/contatos.csv) e colar nome, email e empresa.
2. **Automático via script:** Rodar `python3 extrair_cib.py <faixa> <paginas>`. Exemplo:
   ```bash
   # Extrai as 3 primeiras páginas da Faixa 2 (US$ 1 milhão a US$ 10 milhões)
   python3 extrair_cib.py 2 3
   ```
3. **No Console do Navegador:** Se estiver navegando manualmente no Chrome, cole o código de [console_cib_extractor.js](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/console_cib_extractor.js) no console (F12) e digite `extrairContatoModal()` com o modal aberto.

---

### 3. Simular o Envio (Sem disparar nenhum e-mail)

Antes de enviar de verdade, teste como ficará cada e-mail:

```bash
python3 enviar_emails.py --dry-run
```

O script mostrará a saudação personalizada (`Olá, Pedro, tudo bem?`, `Olá, Sueli, tudo bem?`, etc.) e o corpo completo.

---

### 4. Disparar os E-mails Reais (ou em Lotes de 200 em 200)

Para evitar bloqueios de provedores e respeitar os limites diários do Gmail, o ideal é enviar os e-mails em lotes controlados (por exemplo, de 200 em 200):

```bash
# Enviar um lote de 200 e-mails (pede confirmação interativa antes de começar)
python3 enviar_emails.py --limite 200

# Enviar um lote de 200 e-mails confirmando automaticamente
python3 enviar_emails.py --limite 200 --yes
```

> **Como funciona o controle de lotes:**
> O script consulta automaticamente o arquivo [enviados.csv](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/enviados.csv) e pula quem já recebeu.
> * Na 1ª execução com `--limite 200`: envia para os primeiros 200 contatos pendentes.
> * Na 2ª execução com `--limite 200`: envia para os próximos 200 contatos da fila.
> * Você pode repetir o comando até que todos os contatos da lista sejam atendidos.

Caso queira enviar para todos os contatos pendentes de uma só vez (sem limite):
```bash
python3 enviar_emails.py
```

O script aplica um intervalo de segurança configurável entre cada envio (padrão 2 segundos no `.env` / `config.json`) para proteção anti-spam.

> 🛡️ **Trava Automática de Cota Diária:**
> Para evitar bloqueios do Google (limite de 500/dia), o script possui uma **trava de segurança configurada em 300 e-mails por dia**.
> Se você atingir 300 envios nas últimas 24 horas, o script trava automaticamente antes de conectar no SMTP.
> Caso a cota seja atingida, basta que outro integrante do grupo configure seu próprio e-mail no `.env` para continuar os envios!

---

### 5. Higienizar a Base de Contatos (Bounces / E-mails Inexistentes)

Depois de cada rodada de envios, alguns e-mails podem retornar com erro de entrega ("User unknown", caixa cheia ou desativada). O script [processar_bounces.py](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/processar_bounces.py) conecta na sua caixa do Gmail via IMAP, identifica os e-mails que falharam e limpa a base automaticamente:

```bash
python3 processar_bounces.py
```

O comando:
1. Remove os e-mails inexistentes de [contatos_ativos.csv](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/contatos_ativos.csv).
2. Move os contatos inválidos para [contatos_inativos.csv](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/contatos_inativos.csv).
3. Atualiza o status em [enviados.csv](file:///home/jpcalsavara/Documentos/Disciplinas%20da%20Faculdade/2026.2/Empreendedorismo/enviados.csv) para `BOUNCE / EMAIL INEXISTENTE`.
