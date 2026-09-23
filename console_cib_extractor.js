// Cole este código no Console do Navegador (F12 -> Console) enquanto estiver na página do CIB DPR.
// Sempre que você abrir o modal de uma empresa, você pode rodar 'copiarContato()' ou ele copia automaticamente!

function extrairContatoModal() {
    const modal = document.querySelector('.modal-detalhe-empresa');
    if (!modal) {
        console.warn("Nenhum modal aberto.");
        return;
    }

    const razaoEl = modal.querySelector('.campo-detalhe.full strong');
    const razao = razaoEl ? razaoEl.innerText.trim() : '';

    let email = '';
    let contato = '';
    let executivo = '';

    modal.querySelectorAll('.campo-detalhe').forEach(div => {
        const label = div.querySelector('label')?.innerText.trim().toLowerCase() || '';
        const valor = div.querySelector('.valor')?.innerText.trim() || '';

        if (label === 'e-mail') email = valor;
        if (label === 'contato') contato = valor;
        if (label === 'principal executivo') executivo = valor;
    });

    const nomeFinal = (contato && contato !== '-') ? contato : ((executivo && executivo !== '-') ? executivo : '');
    const linhaCSV = `"${nomeFinal}","${email}","${razao}"`;

    navigator.clipboard.writeText(linhaCSV).then(() => {
        console.log(`%c[✓] Copiado para a área de transferência!`, 'color: green; font-weight: bold;');
        console.log(linhaCSV);
    });

    return { nome: nomeFinal, email, empresa: razao, csv: linhaCSV };
}

console.log("%cExtractor CIB carregado! Quando abrir o modal de uma empresa, digite extrairContatoModal() para copiar a linha CSV.", "color: blue; font-size: 14px;");
