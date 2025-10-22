// --- 1. Função auxiliar para obter o CSRF Token (do cookie) ---
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            let cookie = cookies[i].trimStart();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// --- helper: normaliza tipo de manutenção para o que o Django espera ---
function normalizaTipoManutencao(texto) {
    if (!texto) return null;
    const t = texto.trim().toLowerCase();
    if (t.startsWith('prevent')) return 'preventiva';
    if (t.startsWith('corret')) return 'corretiva';
    if (t.startsWith('check'))  return 'checklist'; // "Check-List" -> "checklist"
    return t;
}

// --- Funções de Limpeza Específicas para cada bloco de entrada ---
function limparBlocosDeEntradaTransmissor() {
    const blocoTransmissor = document.querySelector('#transmissores-container .transmissor-bloco');
    if (!blocoTransmissor) return;

    const campoCircuito = blocoTransmissor.querySelector('[name="num_circuito_tx[]"]');
    if (campoCircuito) {
        if (campoCircuito.tagName === "SELECT") campoCircuito.selectedIndex = 0;
        else campoCircuito.value = '';
        campoCircuito.focus(); // Foco automático no campo Circuito
    }

    blocoTransmissor.querySelector('[name="num_transmissor[]"]').value = '';
    blocoTransmissor.querySelector('[name="vout[]"]').value = '';
    blocoTransmissor.querySelector('[name="pout[]"]').value = '';
    blocoTransmissor.querySelector('[name="tap[]"]').value = '';
    blocoTransmissor.querySelector('[name="tipo_transmissor[]"]').selectedIndex = 0;
    blocoTransmissor.querySelector('[name="tipo_manutencao_tx_1[]"]').selectedIndex = 0;
}

function limparBlocosDeEntradaReceptor() {
    const blocoReceptor = document.querySelector('#receptores-container .receptor-bloco');
    if (!blocoReceptor) return;

    const campoCircuito = blocoReceptor.querySelector('[name="num_circuito_rx[]"]');
    if (campoCircuito) {
        if (campoCircuito.tagName === "SELECT") campoCircuito.selectedIndex = 0;
        else campoCircuito.value = '';
        campoCircuito.focus(); // Foco automático no campo Circuito
    }

    blocoReceptor.querySelector('[name="num_receptor[]"]').value = '';
    blocoReceptor.querySelector('[name="iav[]"]').value = '';
    blocoReceptor.querySelector('[name="ith[]"]').value = '';
    blocoReceptor.querySelector('[name="relacao_dinamica[]"]').value = '';
    blocoReceptor.querySelector('[name="tipo_manutencao_rx_1[]"]').selectedIndex = 0;
}

// **Função principal de limpeza de TODOS os blocos de entrada**
function limparTodosOsBlocosDeEntrada() {
    console.log("DEBUG JS: Executando limparTodosOsBlocosDeEntrada()");
    limparBlocosDeEntradaTransmissor();
    limparBlocosDeEntradaReceptor();
    console.log("DEBUG JS: limparTodosOsBlocosDeEntrada() concluída.");
}

// --- 2. Função SALVAR DADOS ---
function salvarDados() {
    const csrftoken = getCookie('csrftoken');

    let estacao_nome_para_salvar = '';
    const nomeEstacaoSpan = document.getElementById('nome_estacao');
    if (nomeEstacaoSpan) {
        estacao_nome_para_salvar = nomeEstacaoSpan.textContent.trim();
    } else {
        console.error("Erro: Elemento com ID 'nome_estacao' não encontrado no HTML!");
        alert("Erro: Não foi possível determinar a estação. Por favor, recarregue a página.");
        return;
    }

    const tabelaTransmissor = document.getElementById('dados-transmissor').getElementsByTagName('tbody')[0];
    const linhasTransmissor = tabelaTransmissor.querySelectorAll('tr');
    const tabelaReceptor = document.getElementById('dados-receptor').getElementsByTagName('tbody')[0];
    const linhasReceptor = tabelaReceptor.querySelectorAll('tr');
    const transmissoresData = [];
    const receptoresData = [];

    console.log("DEBUG JS: Iniciando salvamento de dados.");
    console.log("DEBUG JS: Estação que será salva (do span):", estacao_nome_para_salvar);
    console.log("DEBUG JS: Número de linhas de transmissor na tabela:", linhasTransmissor.length);
    console.log("DEBUG JS: Número de linhas de receptor na tabela:", linhasReceptor.length);

    // Coleta dados dos transmissores (normalizando tipo_manutencao)
    linhasTransmissor.forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 7) {
            transmissoresData.push({
                num_circuito: cells[0].textContent,
                num_transmissor: cells[1].textContent,
                vout: parseFloat(cells[2].textContent) || null,
                pout: parseFloat(cells[3].textContent) || null,
                tap: cells[4].textContent,
                tipo_transmissor: cells[5].textContent,
                tipo_manutencao: normalizaTipoManutencao(cells[6].textContent)
            });
        }
    });

    // Coleta dados dos receptores (normalizando tipo_manutencao)
    linhasReceptor.forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 6) {
            receptoresData.push({
                num_circuito: cells[0].textContent,
                num_receptor: cells[1].textContent,
                iav: parseFloat(cells[2].textContent) || null,
                ith: parseFloat(cells[3].textContent) || null,
                relacao: cells[4].textContent,
                tipo_manutencao: normalizaTipoManutencao(cells[5].textContent)
            });
        }
    });

    const dados = {
        estacao: estacao_nome_para_salvar,
        transmissores: transmissoresData,
        receptores: receptoresData
    };

    console.log("DEBUG JS: Dados finais a serem enviados (JSON):", JSON.stringify(dados, null, 2));

    fetch('/salvar_dados_cdv/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify(dados)
    })
    .then(resp => resp.json().then(j => ({ ok: resp.ok, j })))
    .then(({ok, j}) => {
        if (!ok) throw new Error(j.message || 'Falha ao salvar');
        alert(j.message || 'Dados salvos com sucesso!');
  // limpar tabelas/inputs aqui...
})
    .catch(err => {
        alert('Erro ao salvar: ' + err.message);
    });
}

// --- 3. Funções ADICIONAR TRANSMISSOR/RECEPTOR ---
function adicionarTransmissor() {
    const blocoTransmissor = document.querySelector('#transmissores-container .transmissor-bloco');
    const tabelaTransmissor = document.getElementById('dados-transmissor').getElementsByTagName('tbody')[0];

    if (blocoTransmissor) {
        const numCircuito = blocoTransmissor.querySelector('[name="num_circuito_tx[]"]').value;
        const numTransmissor = blocoTransmissor.querySelector('[name="num_transmissor[]"]').value;
        const vout = blocoTransmissor.querySelector('[name="vout[]"]').value;
        const pout = blocoTransmissor.querySelector('[name="pout[]"]').value;
        const tap = blocoTransmissor.querySelector('[name="tap[]"]').value;
        const tipoTransmissor = blocoTransmissor.querySelector('[name="tipo_transmissor[]"]').value;
        const tipoManutencao = blocoTransmissor.querySelector('[name="tipo_manutencao_tx_1[]"]').value;

        // Validação básica
        if (numCircuito.trim() === '' || numTransmissor.trim() === '' || vout.trim() === '' || pout.trim() === '' || tap.trim() === '' || tipoTransmissor === '' || tipoManutencao === '') {
            alert('Por favor, preencha todos os campos obrigatórios do Transmissor antes de adicionar.');
            return;
        }

        const newRow = tabelaTransmissor.insertRow();
        newRow.insertCell().textContent = numCircuito;
        newRow.insertCell().textContent = numTransmissor;
        newRow.insertCell().textContent = vout;
        newRow.insertCell().textContent = pout;
        newRow.insertCell().textContent = tap;
        newRow.insertCell().textContent = tipoTransmissor;
        newRow.insertCell().textContent = tipoManutencao;

        const acoesCell = newRow.insertCell();
        acoesCell.innerHTML = `
            <button type="button" onclick="excluirLinha(this)" style="background-color: #dc3545; color: white; border: none; padding: 5px 8px; border-radius: 3px; cursor: pointer;">Excluir</button>
            <button type="button" onclick="editarLinhaTransmissor(this)" style="background-color: #007bff; color: white; border: none; padding: 5px 8px; border-radius: 3px; cursor: pointer; margin-left: 5px;">Editar</button>
    `;


        limparBlocosDeEntradaTransmissor();
    }
}

function adicionarReceptor() {
    const blocoReceptor = document.querySelector('#receptores-container .receptor-bloco');
    const tabelaReceptor = document.getElementById('dados-receptor').getElementsByTagName('tbody')[0];

    if (blocoReceptor) {
        const numCircuito = blocoReceptor.querySelector('[name="num_circuito_rx[]"]').value;
        const numReceptor = blocoReceptor.querySelector('[name="num_receptor[]"]').value;
        const iav = blocoReceptor.querySelector('[name="iav[]"]').value;
        const ith = blocoReceptor.querySelector('[name="ith[]"]').value;
        const relacaoInput = blocoReceptor.querySelector('[name="relacao_dinamica[]"]');
        let relacaoValor = relacaoInput ? relacaoInput.value : '';
        const tipoManutencao = blocoReceptor.querySelector('[name="tipo_manutencao_rx_1[]"]').value;

        if (numCircuito === '' || numReceptor.trim() === '' || iav.trim() === '' || ith.trim() === '' || tipoManutencao === '') {
            alert('Por favor, preencha todos os campos obrigatórios do Receptor antes de adicionar.');
            return;
        }

        const newRow = tabelaReceptor.insertRow();
        newRow.insertCell().textContent = numCircuito;
        newRow.insertCell().textContent = numReceptor;
        newRow.insertCell().textContent = iav;
        newRow.insertCell().textContent = ith;
        newRow.insertCell().textContent = relacaoValor;
        newRow.insertCell().textContent = tipoManutencao;

        const acoesCell = newRow.insertCell();
        acoesCell.innerHTML = `
            <button type="button" onclick="excluirLinha(this)" style="background-color: #dc3545; color: white; border: none; padding: 5px 8px; border-radius: 3px; cursor: pointer;">Excluir</button>
            <button type="button" onclick="editarLinhaReceptor(this)" style="background-color: #007bff; color: white; border: none; padding: 5px 8px; border-radius: 3px; cursor: pointer; margin-left: 5px;">Editar</button>
`;

        limparBlocosDeEntradaReceptor();
    }
}

// --- Funções EDITAR ---
function editarLinhaTransmissor(botaoEditar) {
    const row = botaoEditar.parentNode.parentNode;
    const cells = row.querySelectorAll('td');

    const blocoTransmissor = document.querySelector('#transmissores-container .transmissor-bloco');
    if (blocoTransmissor) {
        blocoTransmissor.querySelector('[name="num_circuito_tx[]"]').value = cells[0].textContent;
        blocoTransmissor.querySelector('[name="num_transmissor[]"]').value = cells[1].textContent;
        blocoTransmissor.querySelector('[name="vout[]"]').value = cells[2].textContent;
        blocoTransmissor.querySelector('[name="pout[]"]').value = cells[3].textContent;
        blocoTransmissor.querySelector('[name="tap[]"]').value = cells[4].textContent;
        blocoTransmissor.querySelector('[name="tipo_transmissor[]"]').value = cells[5].textContent;
        blocoTransmissor.querySelector('[name="tipo_manutencao_tx_1[]"]').value = cells[6].textContent;
    }
    row.parentNode.removeChild(row);
}

function editarLinhaReceptor(botaoEditar) {
    const row = botaoEditar.parentNode.parentNode;
    const cells = row.querySelectorAll('td');

    const blocoReceptor = document.querySelector('#receptores-container .receptor-bloco');
    if (blocoReceptor) {
        blocoReceptor.querySelector('[name="num_circuito_rx[]"]').value = cells[0].textContent;
        blocoReceptor.querySelector('[name="num_receptor[]"]').value = cells[1].textContent;
        blocoReceptor.querySelector('[name="iav[]"]').value = cells[2].textContent;
        blocoReceptor.querySelector('[name="ith[]"]').value = cells[3].textContent;
        blocoReceptor.querySelector('[name="relacao_dinamica[]"]').value = cells[4].textContent;
        blocoReceptor.querySelector('[name="tipo_manutencao_rx_1[]"]').value = cells[5].textContent;
    }
    row.parentNode.removeChild(row);
}

// --- Auxiliares ---
function excluirLinha(botaoExcluir) {
    const row = botaoExcluir.parentNode.parentNode;
    row.parentNode.removeChild(row);
}

function calcularRelacaoDinamica(input) {
  const receptorBloco = input.closest('.receptor-bloco');
  const iavInput = receptorBloco.querySelector('[name="iav[]"]');
  const ithInput = receptorBloco.querySelector('[name="ith[]"]');
  const relacaoInput = receptorBloco.querySelector('[name="relacao_dinamica[]"]');

  if (iavInput && ithInput && relacaoInput) {
    const iav = parseFloat(iavInput.value);
    const ith = parseFloat(ithInput.value);

    if (!isNaN(iav) && !isNaN(ith) && iav !== 0) {
      const relacao = (ith / iav) * 100;
      relacaoInput.value = `${relacao.toFixed(2)}%`;
    } else {
      relacaoInput.value = '';
    }
  }
}
