import json
import logging
import datetime  # para validações de data
import openpyxl

from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction, IntegrityError
from django.db.models import Count, Avg
from django.db.models.functions import TruncDate
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import PatternFill, Font, Border, Side
from openpyxl.utils import get_column_letter
from .models import Estacao, Transmissor, Receptor
from .forms import ReceptorForm, TransmissorForm
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

# Configurar logging
logger = logging.getLogger(__name__)

# normaliza 'Preventiva' -> 'preventiva', etc., para bater com TIPO_MANUTENCAO_CHOICES
def _norm_manutencao(valor):
    if not valor:
        return 'preventiva'
    v = str(valor).strip().lower()
    mapa = {'preventiva':'preventiva', 'corretiva':'corretiva', 'check-list':'checklist', 'checklist':'checklist'}
    return mapa.get(v, 'preventiva')

def _model_has_field(model_cls, field_name: str) -> bool:
    return any(getattr(f, 'name', None) == field_name for f in model_cls._meta.get_fields())

def _pick_temp(d):
    # aceita temp_celsius OU temperatura_local vindos do front
    return safe_float(d.get("temp_celsius", d.get("temperatura_local")))

# =========================
# Utilidades
# =========================
def safe_float(value):
    """Converte para float, se possível; caso contrário, None."""
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def safe_int(value):
    """Converte para int, se possível; caso contrário, None."""
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None


# =========================
# Páginas principais
# =========================
@login_required
def index(request):
    lista_de_estacoes = Estacao.objects.all().order_by("nome")
    selected_estacao_id = request.GET.get("estacao_id")
    context = {
        "lista_de_estacoes": lista_de_estacoes,
        "selected_estacao_id": selected_estacao_id,
    }
    return render(request, "cdv_api/index.html", context)


@login_required
def registrar_cdv(request):
    """
    Renderiza a tela 2 (Registrar Dados do CDV) já com a lista de 'circuitos'
    correspondente à estação selecionada na tela 1.

    Aceita ?estacao=<ID> ou ?estacao=<NOME>.
    Envia ao template:
        - estacao_nome
        - estacao_id_current
        - circuitos (lista de strings) -> use em dois dropdowns (TX e RX)
    """
    estacao_param = request.GET.get("estacao")  # pode ser ID ou nome
    if not estacao_param:
        return redirect("index")

    # Resolve a estação por ID (numérico) ou nome
    try:
        try:
            estacao = Estacao.objects.get(id=int(estacao_param))
        except (ValueError, Estacao.DoesNotExist):
            estacao = Estacao.objects.get(nome=estacao_param)
    except Estacao.DoesNotExist:
        return redirect("index")

    # Monta a lista de circuitos já existentes para a estação (TX + RX)
    tx_codes = Transmissor.objects.filter(estacao=estacao).values_list("num_circuito", flat=True)
    rx_codes = Receptor.objects.filter(estacao=estacao).values_list("num_circuito", flat=True)
    circuitos = sorted({(c or "").strip() for c in list(tx_codes) + list(rx_codes) if c})

    context = {
        "estacao_nome": estacao.nome,
        "estacao_id_current": estacao.id,
        "circuitos": circuitos,  # use no template para os dois dropdowns
    }
    return render(request, "cdv_api/registrar_cdv.html", context)

@login_required
def gerar_relatorio_excel_page(request):
    lista_de_estacoes = Estacao.objects.all().order_by("nome")
    last_estacao_nome_param = request.GET.get("last_estacao_nome")
    tipo_manutencao = request.GET.get("tipo_manutencao")  # NOVO

    return render(
        request,
        "cdv_api/gerar_relatorio_excel.html",
        {
            "lista_de_estacoes": lista_de_estacoes,
            "last_estacao_nome": last_estacao_nome_param,
            "tipo_manutencao": tipo_manutencao,  # NOVO
        },
    )

# =========================
# Ações / APIs
# =========================
@login_required
def salvar_dados_cdv(request):
        # barreira simples contra duplo clique: 1 request a cada 1.5s
    key = "cdv_last_post"
    now = timezone.now()
    last = request.session.get(key)
    if last and (now - datetime.datetime.fromisoformat(last)).total_seconds() < 1.5:
        return JsonResponse({"status":"error","message":"Requisição ignorada (duplicada)."}, status=429)
    request.session[key] = now.isoformat()
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método não permitido."}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        estacao_nome = data.get("estacao")
        transmissores_data = data.get("transmissores", [])
        receptores_data    = data.get("receptores", [])

        if not estacao_nome:
            return JsonResponse({"status": "error", "message": "Nome da estação não fornecido."}, status=400)

        try:
            estacao = Estacao.objects.get(nome=estacao_nome)
        except Estacao.DoesNotExist:
            return JsonResponse({"status": "error", "message": f"Estação \"{estacao_nome}\" não encontrada."}, status=404)

        hoje = timezone.localdate()

        with transaction.atomic():
            # ---------- TX ----------
            for tx in transmissores_data:
                num_circ = tx.get("num_circuito")
                num_tx   = tx.get("num_transmissor")
                hora     = tx.get("horario_coleta")  # 'HH:MM'
                temp     = _pick_temp(tx)

                # Procura registro "igual" no mesmo dia
                qs = (Transmissor.objects
                      .filter(estacao=estacao,
                              num_circuito=num_circ,
                              num_transmissor=num_tx,
                              horario_coleta=hora)
                      .annotate(dia=TruncDate("data_manutencao"))
                      .filter(dia=hoje))

                if qs.exists():
                    obj = qs.latest("id")
                    # Atualiza temperatura se chegou agora
                    if temp is not None:
                        obj.temp_celsius = temp
                    # Atualiza demais campos (sem criar duplicata)
                    obj.vout = safe_float(tx.get("vout"))
                    obj.pout = safe_float(tx.get("pout"))
                    obj.tap  = tx.get("tap")
                    obj.tipo_transmissor = tx.get("tipo_transmissor")
                    obj.tipo_manutencao  = _norm_manutencao(tx.get("tipo_manutencao"))
                    obj.save()
                else:
                    # Cria primeiro registro (se vier sem temp, fica None; a próxima chamada completará)
                    Transmissor.objects.create(
                        estacao=estacao,
                        num_circuito=num_circ,
                        num_transmissor=num_tx,
                        vout=safe_float(tx.get("vout")),
                        pout=safe_float(tx.get("pout")),
                        tap=tx.get("tap"),
                        tipo_transmissor=tx.get("tipo_transmissor"),
                        tipo_manutencao=_norm_manutencao(tx.get("tipo_manutencao")),
                        horario_coleta=hora,
                        temp_celsius=temp,
                    )

            # ---------- RX ----------
            for rx in receptores_data:
                num_circ = rx.get("num_circuito")
                num_rx   = rx.get("num_receptor")
                hora     = rx.get("horario_coleta")
                temp     = _pick_temp(rx)

                iav = safe_float(rx.get("iav"))
                ith = safe_float(rx.get("ith"))
                if iav and ith and iav != 0:
                    rel_str = f"{(ith/iav)*100:.2f}%"
                else:
                    rel = safe_float(rx.get("relacao"))
                    rel_str = f"{rel:.2f}%" if rel is not None else None

                qs = (Receptor.objects
                      .filter(estacao=estacao,
                              num_circuito=num_circ,
                              num_receptor=num_rx,
                              horario_coleta=hora)
                      .annotate(dia=TruncDate("data_manutencao"))
                      .filter(dia=hoje))

                if qs.exists():
                    obj = qs.latest("id")
                    if temp is not None:
                        obj.temp_celsius = temp
                    obj.iav = iav
                    obj.ith = ith
                    obj.relacao = rel_str
                    obj.tipo_manutencao = _norm_manutencao(rx.get("tipo_manutencao"))
                    obj.save()
                else:
                    Receptor.objects.create(
                        estacao=estacao,
                        num_circuito=num_circ,
                        num_receptor=num_rx,
                        iav=iav,
                        ith=ith,
                        relacao=rel_str,
                        tipo_manutencao=_norm_manutencao(rx.get("tipo_manutencao")),
                        horario_coleta=hora,
                        temp_celsius=temp,
                    )

        return JsonResponse({"status": "success", "message": "Dados salvos com sucesso!"})

    except Exception as e:
        logger.exception("Erro inesperado na view salvar_dados_cdv")
        return JsonResponse({"status": "error", "message": f"Ocorreu um erro inesperado no servidor: {str(e)}"}, status=500)

# =========================
# Autenticação
# =========================
def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect("index")
            else:
                form.add_error(None, "Nome de usuário ou senha incorretos.")
        return render(request, "cdv_api/login.html", {"form": form})
    else:
        form = AuthenticationForm()
        return render(request, "cdv_api/login.html", {"form": form})
    
@login_required
def gerar_excel_estacao(request):
    """
    Gera um Excel com duas abas (Transmissores/Receptores), incluindo Temp. (Celsius).
    Filtros: estação (obrigatório), circuito (opcional), intervalo de datas e tipo de manutenção.
    """
    estacao_id = request.GET.get("estacao_id")
    circuito_filtro = request.GET.get("circuito_filtro")
    data_inicio_str = request.GET.get("data_inicio")
    data_fim_str = request.GET.get("data_fim")
    tipo_manutencao_raw = request.GET.get("tipo_manutencao")

    def norm_tipo(val: str | None):
        if not val:
            return None
        v = val.strip().lower()
        if v.startswith("prevent"):  return "preventiva"
        if v.startswith("corret"):   return "corretiva"
        if v.startswith("check"):    return "checklist"
        return None

    tipo_manutencao = norm_tipo(tipo_manutencao_raw)

    if not estacao_id:
        return HttpResponse("Por favor, selecione uma estação.", status=400)

    estacao = get_object_or_404(Estacao, id=estacao_id)

    transmissores = Transmissor.objects.filter(estacao=estacao)
    receptores    = Receptor.objects.filter(estacao=estacao)

    logger.info(
        "Excel filtro -> estacao_id=%s, circuito=%s, data_ini=%s, data_fim=%s, tipo_raw=%s -> tipo_norm=%s",
        estacao_id, circuito_filtro, data_inicio_str, data_fim_str, tipo_manutencao_raw, tipo_manutencao
    )

    if circuito_filtro:
        transmissores = transmissores.filter(num_circuito__icontains=circuito_filtro)
        receptores    = receptores.filter(num_circuito__icontains=circuito_filtro)

    if tipo_manutencao in {"preventiva", "corretiva", "checklist"}:
        transmissores = transmissores.filter(tipo_manutencao=tipo_manutencao)
        receptores    = receptores.filter(tipo_manutencao=tipo_manutencao)

    def _parse_date(s):
        try:
            return timezone.datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    data_inicio = _parse_date(data_inicio_str) if data_inicio_str else None
    data_fim    = _parse_date(data_fim_str) if data_fim_str else None

    if data_inicio and data_fim:
        data_fim_ajustada = data_fim + timezone.timedelta(days=1)
        transmissores = transmissores.filter(
            data_manutencao__date__gte=data_inicio,
            data_manutencao__date__lt=data_fim_ajustada,
        )
        receptores = receptores.filter(
            data_manutencao__date__gte=data_inicio,
            data_manutencao__date__lt=data_fim_ajustada,
        )
    elif data_inicio:
        transmissores = transmissores.filter(data_manutencao__date__gte=data_inicio)
        receptores    = receptores.filter(data_manutencao__date__gte=data_inicio)
    elif data_fim:
        data_fim_ajustada = data_fim + timezone.timedelta(days=1)
        transmissores = transmissores.filter(data_manutencao__date__lt=data_fim_ajustada)
        receptores    = receptores.filter(data_manutencao__date__lt=data_fim_ajustada)

    logger.info("Excel pós-filtro -> TX=%d, RX=%d (tipo=%s)",
                transmissores.count(), receptores.count(), tipo_manutencao)

    # remove linhas sem temperatura
    transmissores = transmissores.exclude(temp_celsius__isnull=True)
    receptores    = receptores.exclude(temp_celsius__isnull=True)

    transmissores = transmissores.order_by("data_manutencao", "horario_coleta", "id")
    receptores    = receptores.order_by("data_manutencao", "horario_coleta", "id")

    wb = openpyxl.Workbook()

    # ------- TX -------
    ws_tx = wb.active
    ws_tx.title = "Transmissores"
    ws_tx.append([
        "Estação", "Circuito", "TX", "VOUT", "POUT", "TAP", "Tipo TX", "Tipo Manutenção",
        "Data", "Horário Coleta", "Temp. (Celsius)"
    ])

    for t in transmissores:
        dt = timezone.localtime(t.data_manutencao) if t.data_manutencao else None
        data_fmt = dt.strftime("%d/%m/%Y") if dt else "-"
        hora_fmt = t.horario_coleta.strftime("%H:%M") if t.horario_coleta else "-"
        ws_tx.append([
            estacao.nome, t.num_circuito, safe_int(t.num_transmissor), t.vout, t.pout,
            safe_int(t.tap), t.tipo_transmissor, t.tipo_manutencao, data_fmt, hora_fmt, t.temp_celsius
        ])

    # ------- RX -------
    ws_rx = wb.create_sheet("Receptores")
    ws_rx.append([
        "Estação", "Circuito", "RX", "IAV", "ITH", "Relação", "Tipo Manutenção",
        "Data", "Horário Coleta", "Temp. (Celsius)"
    ])

    from openpyxl.utils import get_column_letter
    linha_inicio_rx = ws_rx.max_row + 1

    for r in receptores:
        dt = timezone.localtime(r.data_manutencao) if r.data_manutencao else None
        data_fmt = dt.strftime("%d/%m/%Y") if dt else "-"
        hora_fmt = r.horario_coleta.strftime("%H:%M") if r.horario_coleta else "-"

        # Relação como fração (para formatar % no Excel)
        rel_excel = None
        if r.relacao and r.relacao.replace("%", "").strip():
            try:
                rel_excel = float(r.relacao.replace("%", "")) / 100.0
            except ValueError:
                rel_excel = None

        ws_rx.append([
            estacao.nome, r.num_circuito, safe_int(r.num_receptor), r.iav, r.ith,
            rel_excel, r.tipo_manutencao, data_fmt, hora_fmt, r.temp_celsius
        ])

    # Formata % na coluna Relação (F)
    col_rel = get_column_letter(6)
    linha_fim_rx = ws_rx.max_row
    for row in range(linha_inicio_rx, linha_fim_rx + 1):
        ws_rx[f"{col_rel}{row}"].number_format = "0.00%"

    # Temperatura com 1 casa decimal (última coluna) em ambas as abas
    for ws in (ws_tx, ws_rx):
        last_col = ws.max_column
        for col_cells in ws.iter_cols(min_col=last_col, max_col=last_col, min_row=2, max_row=ws.max_row):
            for c in col_cells:
                c.number_format = "0.0"

    # Auto-largura simples
    for ws in (ws_tx, ws_rx):
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                v = cell.value
                l = len(str(v)) if v is not None else 0
                max_len = max(max_len, l)
            ws.column_dimensions[col_letter].width = min(max_len + 2, 30)

    # ---- Semáforo na coluna Relação (sheet RX) ----
    from openpyxl.formatting.rule import CellIsRule, FormulaRule
    from openpyxl.styles import PatternFill, Font

    intervalo = f"{col_rel}{linha_inicio_rx}:{col_rel}{linha_fim_rx}"
    fill_red   = PatternFill(start_color="FFFFC7CE", end_color="FFFFC7CE", fill_type="solid")
    font_red   = Font(color="FF9C0006")
    fill_green = PatternFill(start_color="FFC6EFCE", end_color="FFC6EFCE", fill_type="solid")
    font_green = Font(color="FF006100")

    # < 60%  -> vermelho
    ws_rx.conditional_formatting.add(
        intervalo,
        CellIsRule(operator="lessThan", formula=["0.6"], fill=fill_red, font=font_red)
    )
    # > 80%  -> vermelho
    ws_rx.conditional_formatting.add(
        intervalo,
        CellIsRule(operator="greaterThan", formula=["0.8"], fill=fill_red, font=font_red)
    )
    # 61%..79% (exclusivo) -> verde (AND(Fx>0.6, Fx<0.8))
    primeira_celula = f"{col_rel}{linha_inicio_rx}"
    ws_rx.conditional_formatting.add(
        intervalo,
        FormulaRule(formula=[f"AND({primeira_celula}>=0.6,{primeira_celula}<=0.8)"], fill=fill_green, font=font_green)
    )

    # ========= RESUMO ESTATÍSTICO =========
    from openpyxl.styles import Font, Alignment
    from collections import defaultdict
    import math

    def _rel_to_frac(obj):
        """Converte '72.35%' -> 0.7235. Retorna None se inválido/ausente."""
        s = (obj.relacao or "").strip()
        if not s:
            return None
        try:
            return float(s.replace("%", "").replace(",", ".")) / 100.0
        except Exception:
            return None

    # Coleta valores numéricos
    rx_rel = []
    rx_rel_por_tipo = defaultdict(list)
    for r in receptores:
        v = _rel_to_frac(r)
        if v is not None:
            rx_rel.append(v)
            rx_rel_por_tipo[r.tipo_manutencao or ""] .append(v)

    tx_temps = [t.temp_celsius for t in transmissores if t.temp_celsius is not None]
    rx_temps = [r.temp_celsius for r in receptores    if r.temp_celsius is not None]
    all_temps = tx_temps + rx_temps

    def _avg(lst):
        return (sum(lst) / len(lst)) if lst else None
    def _min(lst):
        return min(lst) if lst else None
    def _max(lst):
        return max(lst) if lst else None

    # Métricas principais
    rx_count   = len(rx_rel)
    rx_avg     = _avg(rx_rel)
    rx_below60 = sum(1 for v in rx_rel if v < 0.60)
    rx_between = sum(1 for v in rx_rel if 0.60 < v < 0.80)  # EXCLUSIVO
    rx_above80 = sum(1 for v in rx_rel if v > 0.80)

    tx_avg_temp = _avg(tx_temps)
    rx_avg_temp = _avg(rx_temps)
    all_avg_temp= _avg(all_temps)
    tx_min_temp = _min(tx_temps)
    tx_max_temp = _max(tx_temps)
    rx_min_temp = _min(rx_temps)
    rx_max_temp = _max(rx_temps)
    all_min_temp= _min(all_temps)
    all_max_temp= _max(all_temps)

    # Aba Resumo
    ws_sum = wb.create_sheet("Resumo")

    # Título
    ws_sum["A1"] = f"Resumo Estatístico — {estacao.nome}"
    ws_sum["A1"].font = Font(size=14, bold=True)
    ws_sum.merge_cells("A1:D1")

    row = 3

    # Bloco 1 — Relação (RX) geral
    ws_sum[f"A{row}"] = "Relação (RX) — Geral"
    ws_sum[f"A{row}"].font = Font(bold=True)
    row += 1
    ws_sum.append(["Métrica", "Valor"])
    ws_sum[f"A{row}"].font = Font(bold=True)
    ws_sum[f"B{row}"].font = Font(bold=True)
    row += 1

    ws_sum.append(["Quantidade (linhas RX com relação)", rx_count]); row += 1
    ws_sum.append(["Média de Relação", rx_avg]); row += 1
    ws_sum.append(["Abaixo de 60%", rx_below60]); row += 1
    ws_sum.append(["Entre 61% e 79%", rx_between]); row += 1
    ws_sum.append(["Acima de 80%", rx_above80]); row += 2

    # Formato de porcentagem para a média
    ws_sum[f"B{row-6}"].number_format = "0.00%"

    # Bloco 2 — Relação por Tipo de Manutenção
    ws_sum[f"A{row}"] = "Relação (RX) — por Tipo de Manutenção"
    ws_sum[f"A{row}"].font = Font(bold=True)
    row += 1
    ws_sum.append(["Tipo", "Qtd", "Média Relação"])
    ws_sum[f"A{row}"].font = Font(bold=True)
    ws_sum[f"B{row}"].font = Font(bold=True)
    ws_sum[f"C{row}"].font = Font(bold=True)
    row += 1

    for tipo, vals in rx_rel_por_tipo.items():
        avg_tipo = _avg(vals)
        ws_sum.append([tipo or "-", len(vals), avg_tipo])
        # formatar como % a última célula recém inserida
        ws_sum[f"C{row}"].number_format = "0.00%"
        row += 1
    row += 1

    # Bloco 3 — Temperaturas
    ws_sum[f"A{row}"] = "Temperatura (°C)"
    ws_sum[f"A{row}"].font = Font(bold=True)
    row += 1
    ws_sum.append(["Grupo", "Média", "Mín", "Máx"])
    ws_sum[f"A{row}"].font = Font(bold=True)
    ws_sum[f"B{row}"].font = Font(bold=True)
    ws_sum[f"C{row}"].font = Font(bold=True)
    ws_sum[f"D{row}"].font = Font(bold=True)
    row += 1

    def _append_temp_row(label, avg_, min_, max_):
        ws_sum.append([label, avg_, min_, max_])

    _append_temp_row("TX",   tx_avg_temp, tx_min_temp, tx_max_temp); row += 1
    _append_temp_row("RX",   rx_avg_temp, rx_min_temp, rx_max_temp); row += 1
    _append_temp_row("Geral",all_avg_temp,all_min_temp,all_max_temp);row += 1

    # Formatação numérica das temperaturas (1 casa)
    for r in range(row-3, row):
        for c in ("B","C","D"):
            ws_sum[f"{c}{r}"].number_format = "0.0"

    # Ajuste de largura
    for col in ("A","B","C","D"):
        ws_sum.column_dimensions[col].width = 26


    # Resposta
    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="dados_{estacao.nome}.xlsx"'
    wb.save(resp)
    return resp

@login_required
def home(request):
    try:
        # ajuste o nome do template conforme seu projeto
        return render(request, "home.html", {})
    except Exception:
        logger.exception("Falha ao renderizar home()")
        return render(request, "erro_generico.html", status=500)