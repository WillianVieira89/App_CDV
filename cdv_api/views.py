import json
import logging
import datetime
from collections import defaultdict

import openpyxl
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template import TemplateDoesNotExist
from django.utils import timezone
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import PatternFill, Font
from openpyxl.utils import get_column_letter

from .models import Estacao, Transmissor, Receptor

logger = logging.getLogger(__name__)


# =========================
# Utilidades
# =========================

def safe_float(value):
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def safe_int(value):
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def _norm_manutencao(valor):
    if not valor:
        return "preventiva"
    v = str(valor).strip().lower()
    mapa = {
        "preventiva": "preventiva",
        "corretiva": "corretiva",
        "check-list": "checklist",
        "checklist": "checklist",
    }
    return mapa.get(v, "preventiva")


def _pick_temp(d):
    return safe_float(d.get("temp_celsius", d.get("temperatura_local")))


def relacao_para_float(relacao_str):
    if not relacao_str:
        return None
    try:
        return float(str(relacao_str).replace("%", "").replace(",", ".").strip())
    except (ValueError, TypeError):
        return None


def detectar_degradacao_faixa(receptores_queryset, qtd_leituras=3):
    """
    Detecta degradação quando a tendência sai da faixa normal (60% a 80%).

    Regras:
    - usa as últimas 3 leituras por circuito
    - se estiver em queda contínua e a última < 60 -> degradação negativa
    - se estiver em subida contínua e a última > 80 -> degradação positiva
    """
    historico_por_circuito = defaultdict(list)

    receptores_ordenados = receptores_queryset.order_by("num_circuito", "-data_manutencao", "-id")

    for r in receptores_ordenados:
        valor = relacao_para_float(r.relacao)
        if valor is None:
            continue

        circuito = (r.num_circuito or "").strip().upper()

        if len(historico_por_circuito[circuito]) < qtd_leituras:
            historico_por_circuito[circuito].append({
                "data": r.data_manutencao,
                "relacao": valor,
            })

    circuitos_degradados = []

    for circuito, leituras in historico_por_circuito.items():
        if len(leituras) < qtd_leituras:
            continue

        leituras = list(reversed(leituras))  # mais antiga -> mais recente
        valores = [item["relacao"] for item in leituras]

        em_queda = all(valores[i] > valores[i + 1] for i in range(len(valores) - 1))
        em_subida = all(valores[i] < valores[i + 1] for i in range(len(valores) - 1))

        ultima = valores[-1]
        primeira = valores[0]

        if em_queda and ultima < 60:
            circuitos_degradados.append({
                "circuito": circuito,
                "leituras": valores,
                "variacao_total": round(ultima - primeira, 2),
                "ultima_relacao": round(ultima, 2),
                "tipo_degradacao": "Negativa",
                "status": "Abaixo de 60%",
            })

        elif em_subida and ultima > 80:
            circuitos_degradados.append({
                "circuito": circuito,
                "leituras": valores,
                "variacao_total": round(ultima - primeira, 2),
                "ultima_relacao": round(ultima, 2),
                "tipo_degradacao": "Positiva",
                "status": "Acima de 80%",
            })

    circuitos_degradados.sort(
        key=lambda x: (
            x["tipo_degradacao"] != "Negativa",
            x["ultima_relacao"],
        )
    )

    return circuitos_degradados


# =========================
# Páginas principais
# =========================

@login_required
def registrar_cdv(request):
    """
    Renderiza a tela de registro de dados do CDV já com a lista de circuitos
    correspondente à estação selecionada.

    Aceita ?estacao=<ID> ou ?estacao=<NOME>.
    """
    estacao_param = request.GET.get("estacao")
    if not estacao_param:
        return redirect("index")

    try:
        try:
            estacao = Estacao.objects.get(id=int(estacao_param))
        except (ValueError, Estacao.DoesNotExist):
            estacao = Estacao.objects.get(nome=estacao_param)
    except Estacao.DoesNotExist:
        return redirect("index")

    tx_codes = Transmissor.objects.filter(estacao=estacao).values_list("num_circuito", flat=True)
    rx_codes = Receptor.objects.filter(estacao=estacao).values_list("num_circuito", flat=True)
    circuitos = sorted({(c or "").strip() for c in list(tx_codes) + list(rx_codes) if c})

    context = {
        "estacao_nome": estacao.nome,
        "estacao_id_current": estacao.id,
        "circuitos": circuitos,
    }
    return render(request, "cdv_api/registrar_cdv.html", context)


@login_required
def gerar_relatorio_excel_page(request):
    lista_de_estacoes = Estacao.objects.all().order_by("nome")
    last_estacao_nome_param = request.GET.get("last_estacao_nome")
    tipo_manutencao = request.GET.get("tipo_manutencao")

    return render(
        request,
        "cdv_api/gerar_relatorio_excel.html",
        {
            "lista_de_estacoes": lista_de_estacoes,
            "last_estacao_nome": last_estacao_nome_param,
            "tipo_manutencao": tipo_manutencao,
        },
    )


@login_required
def index(request):
    lista_de_estacoes = Estacao.objects.all().order_by("nome")
    context = {
        "lista_de_estacoes": lista_de_estacoes,
        "selected_estacao_id": request.GET.get("estacao_id"),
    }
    try:
        return render(request, "cdv_api/index.html", context)
    except TemplateDoesNotExist:
        logger.exception("Template cdv_api/index.html ausente")
        return HttpResponse("<h1>Home OK</h1>")


@login_required
def home(request):
    try:
        return render(request, "cdv_api/home.html", {})
    except TemplateDoesNotExist:
        logger.exception("Falha ao renderizar home()")
        return render(request, "cdv_api/erro_generico.html", status=500)


# =========================
# Autenticação
# =========================

def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = authenticate(
                username=form.cleaned_data.get("username"),
                password=form.cleaned_data.get("password"),
            )
            if user is not None:
                login(request, user)
                return redirect("index")
            form.add_error(None, "Nome de usuário ou senha incorretos.")
        return render(request, "cdv_api/login.html", {"form": form})

    form = AuthenticationForm()
    return render(request, "cdv_api/login.html", {"form": form})


# =========================
# APIs / Ações
# =========================

@login_required
def salvar_dados_cdv(request):
    key = "cdv_last_post"
    now = timezone.now()
    last = request.session.get(key)

    if last and (now - datetime.datetime.fromisoformat(last)).total_seconds() < 1.5:
        return JsonResponse(
            {"status": "error", "message": "Requisição ignorada (duplicada)."},
            status=429,
        )

    request.session[key] = now.isoformat()

    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Método não permitido."},
            status=405,
        )

    try:
        data = json.loads(request.body.decode("utf-8"))
        estacao_nome = data.get("estacao")
        transmissores_data = data.get("transmissores", [])
        receptores_data = data.get("receptores", [])

        if not estacao_nome:
            return JsonResponse(
                {"status": "error", "message": "Nome da estação não fornecido."},
                status=400,
            )

        try:
            estacao = Estacao.objects.get(nome=estacao_nome)
        except Estacao.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": f'Estação "{estacao_nome}" não encontrada.'},
                status=404,
            )

        hoje = timezone.localdate()

        with transaction.atomic():
            # ---------- TX ----------
            for tx in transmissores_data:
                num_circ = tx.get("num_circuito")
                num_tx = tx.get("num_transmissor")
                hora = tx.get("horario_coleta")
                temp = _pick_temp(tx)

                qs = (
                    Transmissor.objects.filter(
                        estacao=estacao,
                        num_circuito=num_circ,
                        num_transmissor=num_tx,
                        horario_coleta=hora,
                    )
                    .annotate(dia=TruncDate("data_manutencao"))
                    .filter(dia=hoje)
                )

                if qs.exists():
                    obj = qs.latest("id")
                    if temp is not None:
                        obj.temp_celsius = temp
                    obj.vout = safe_float(tx.get("vout"))
                    obj.pout = safe_float(tx.get("pout"))
                    obj.tap = tx.get("tap")
                    obj.tipo_transmissor = tx.get("tipo_transmissor")
                    obj.tipo_manutencao = _norm_manutencao(tx.get("tipo_manutencao"))
                    obj.save()
                else:
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
                num_rx = rx.get("num_receptor")
                hora = rx.get("horario_coleta")
                temp = _pick_temp(rx)

                iav = safe_float(rx.get("iav"))
                ith = safe_float(rx.get("ith"))

                if iav and ith and iav != 0:
                    rel_str = f"{(ith / iav) * 100:.2f}%"
                else:
                    rel = safe_float(rx.get("relacao"))
                    rel_str = f"{rel:.2f}%" if rel is not None else None

                qs = (
                    Receptor.objects.filter(
                        estacao=estacao,
                        num_circuito=num_circ,
                        num_receptor=num_rx,
                        horario_coleta=hora,
                    )
                    .annotate(dia=TruncDate("data_manutencao"))
                    .filter(dia=hoje)
                )

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
        return JsonResponse(
            {"status": "error", "message": f"Ocorreu um erro inesperado no servidor: {str(e)}"},
            status=500,
        )


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

    def norm_tipo(val):
        if not val:
            return None
        v = val.strip().lower()
        if v.startswith("prevent"):
            return "preventiva"
        if v.startswith("corret"):
            return "corretiva"
        if v.startswith("check"):
            return "checklist"
        return None

    def _parse_date(s):
        try:
            return timezone.datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    tipo_manutencao = norm_tipo(tipo_manutencao_raw)

    if not estacao_id:
        return HttpResponse("Por favor, selecione uma estação.", status=400)

    estacao = get_object_or_404(Estacao, id=estacao_id)

    transmissores = Transmissor.objects.filter(estacao=estacao)
    receptores = Receptor.objects.filter(estacao=estacao)

    logger.info(
        "Excel filtro -> estacao_id=%s, circuito=%s, data_ini=%s, data_fim=%s, tipo_raw=%s -> tipo_norm=%s",
        estacao_id, circuito_filtro, data_inicio_str, data_fim_str, tipo_manutencao_raw, tipo_manutencao,
    )

    if circuito_filtro:
        transmissores = transmissores.filter(num_circuito__icontains=circuito_filtro)
        receptores = receptores.filter(num_circuito__icontains=circuito_filtro)

    if tipo_manutencao in {"preventiva", "corretiva", "checklist"}:
        transmissores = transmissores.filter(tipo_manutencao=tipo_manutencao)
        receptores = receptores.filter(tipo_manutencao=tipo_manutencao)

    data_inicio = _parse_date(data_inicio_str) if data_inicio_str else None
    data_fim = _parse_date(data_fim_str) if data_fim_str else None

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
        receptores = receptores.filter(data_manutencao__date__gte=data_inicio)
    elif data_fim:
        data_fim_ajustada = data_fim + timezone.timedelta(days=1)
        transmissores = transmissores.filter(data_manutencao__date__lt=data_fim_ajustada)
        receptores = receptores.filter(data_manutencao__date__lt=data_fim_ajustada)

    logger.info(
        "Excel pós-filtro -> TX=%d, RX=%d (tipo=%s)",
        transmissores.count(),
        receptores.count(),
        tipo_manutencao,
    )

    transmissores = transmissores.exclude(temp_celsius__isnull=True)
    receptores = receptores.exclude(temp_celsius__isnull=True)

    transmissores = transmissores.order_by("data_manutencao", "horario_coleta", "id")
    receptores = receptores.order_by("data_manutencao", "horario_coleta", "id")

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
            estacao.nome,
            t.num_circuito,
            safe_int(t.num_transmissor),
            t.vout,
            t.pout,
            safe_int(t.tap),
            t.tipo_transmissor,
            t.tipo_manutencao,
            data_fmt,
            hora_fmt,
            t.temp_celsius,
        ])

    # ------- RX -------
    ws_rx = wb.create_sheet("Receptores")
    ws_rx.append([
        "Estação", "Circuito", "RX", "IAV", "ITH", "Relação", "Tipo Manutenção",
        "Data", "Horário Coleta", "Temp. (Celsius)"
    ])

    linha_inicio_rx = ws_rx.max_row + 1

    for r in receptores:
        dt = timezone.localtime(r.data_manutencao) if r.data_manutencao else None
        data_fmt = dt.strftime("%d/%m/%Y") if dt else "-"
        hora_fmt = r.horario_coleta.strftime("%H:%M") if r.horario_coleta else "-"

        rel_excel = None
        if r.relacao and r.relacao.replace("%", "").strip():
            try:
                rel_excel = float(r.relacao.replace("%", "")) / 100.0
            except ValueError:
                rel_excel = None

        ws_rx.append([
            estacao.nome,
            r.num_circuito,
            safe_int(r.num_receptor),
            r.iav,
            r.ith,
            rel_excel,
            r.tipo_manutencao,
            data_fmt,
            hora_fmt,
            r.temp_celsius,
        ])

    col_rel = get_column_letter(6)
    linha_fim_rx = ws_rx.max_row

    for row in range(linha_inicio_rx, linha_fim_rx + 1):
        ws_rx[f"{col_rel}{row}"].number_format = "0.00%"

    for ws in (ws_tx, ws_rx):
        last_col = ws.max_column
        for col_cells in ws.iter_cols(min_col=last_col, max_col=last_col, min_row=2, max_row=ws.max_row):
            for c in col_cells:
                c.number_format = "0.0"

    for ws in (ws_tx, ws_rx):
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                v = cell.value
                l = len(str(v)) if v is not None else 0
                max_len = max(max_len, l)
            ws.column_dimensions[col_letter].width = min(max_len + 2, 30)

    intervalo = f"{col_rel}{linha_inicio_rx}:{col_rel}{linha_fim_rx}"
    fill_red = PatternFill(start_color="FFFFC7CE", end_color="FFFFC7CE", fill_type="solid")
    font_red = Font(color="FF9C0006")
    fill_green = PatternFill(start_color="FFC6EFCE", end_color="FFC6EFCE", fill_type="solid")
    font_green = Font(color="FF006100")

    ws_rx.conditional_formatting.add(
        intervalo,
        CellIsRule(operator="lessThan", formula=["0.6"], fill=fill_red, font=font_red)
    )
    ws_rx.conditional_formatting.add(
        intervalo,
        CellIsRule(operator="greaterThan", formula=["0.8"], fill=fill_red, font=font_red)
    )

    primeira_celula = f"{col_rel}{linha_inicio_rx}"
    ws_rx.conditional_formatting.add(
        intervalo,
        FormulaRule(
            formula=[f"AND({primeira_celula}>=0.6,{primeira_celula}<=0.8)"],
            fill=fill_green,
            font=font_green,
        )
    )

    # ========= RESUMO =========
    def _rel_to_frac(obj):
        s = (obj.relacao or "").strip()
        if not s:
            return None
        try:
            return float(s.replace("%", "").replace(",", ".")) / 100.0
        except Exception:
            return None

    rx_rel = []
    rx_rel_por_tipo = defaultdict(list)

    for r in receptores:
        v = _rel_to_frac(r)
        if v is not None:
            rx_rel.append(v)
            rx_rel_por_tipo[r.tipo_manutencao or ""].append(v)

    tx_temps = [t.temp_celsius for t in transmissores if t.temp_celsius is not None]
    rx_temps = [r.temp_celsius for r in receptores if r.temp_celsius is not None]
    all_temps = tx_temps + rx_temps

    def _avg(lst):
        return (sum(lst) / len(lst)) if lst else None

    def _min(lst):
        return min(lst) if lst else None

    def _max(lst):
        return max(lst) if lst else None

    rx_count = len(rx_rel)
    rx_avg = _avg(rx_rel)
    rx_below60 = sum(1 for v in rx_rel if v < 0.60)
    rx_between = sum(1 for v in rx_rel if 0.60 < v < 0.80)
    rx_above80 = sum(1 for v in rx_rel if v > 0.80)

    tx_avg_temp = _avg(tx_temps)
    rx_avg_temp = _avg(rx_temps)
    all_avg_temp = _avg(all_temps)
    tx_min_temp = _min(tx_temps)
    tx_max_temp = _max(tx_temps)
    rx_min_temp = _min(rx_temps)
    rx_max_temp = _max(rx_temps)
    all_min_temp = _min(all_temps)
    all_max_temp = _max(all_temps)

    ws_sum = wb.create_sheet("Resumo")
    ws_sum["A1"] = f"Resumo Estatístico — {estacao.nome}"
    ws_sum["A1"].font = Font(size=14, bold=True)
    ws_sum.merge_cells("A1:D1")

    row = 3

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

    ws_sum[f"B{row-6}"].number_format = "0.00%"

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
        ws_sum[f"C{row}"].number_format = "0.00%"
        row += 1

    row += 1

    ws_sum[f"A{row}"] = "Temperatura (°C)"
    ws_sum[f"A{row}"].font = Font(bold=True)
    row += 1

    ws_sum.append(["Grupo", "Média", "Mín", "Máx"])
    ws_sum[f"A{row}"].font = Font(bold=True)
    ws_sum[f"B{row}"].font = Font(bold=True)
    ws_sum[f"C{row}"].font = Font(bold=True)
    ws_sum[f"D{row}"].font = Font(bold=True)
    row += 1

    ws_sum.append(["TX", tx_avg_temp, tx_min_temp, tx_max_temp]); row += 1
    ws_sum.append(["RX", rx_avg_temp, rx_min_temp, rx_max_temp]); row += 1
    ws_sum.append(["Geral", all_avg_temp, all_min_temp, all_max_temp]); row += 1

    for r in range(row - 3, row):
        for c in ("B", "C", "D"):
            ws_sum[f"{c}{r}"].number_format = "0.0"

    for col in ("A", "B", "C", "D"):
        ws_sum.column_dimensions[col].width = 26

    resp = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp["Content-Disposition"] = f'attachment; filename="dados_{estacao.nome}.xlsx"'
    wb.save(resp)
    return resp


# =========================
# Dashboard
# =========================

@login_required
def dashboard_manutencao(request):
    estacao_id = request.GET.get("estacao_id")
    circuito_filtro = request.GET.get("circuito_filtro")
    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")
    tipo_manutencao = request.GET.get("tipo_manutencao")

    lista_de_estacoes = Estacao.objects.all().order_by("nome")

    transmissores = Transmissor.objects.all()
    receptores = Receptor.objects.all()

    estacao_nome = None

    if estacao_id:
        estacao = get_object_or_404(Estacao, id=estacao_id)
        estacao_nome = estacao.nome
        transmissores = transmissores.filter(estacao=estacao)
        receptores = receptores.filter(estacao=estacao)

    if circuito_filtro:
        transmissores = transmissores.filter(num_circuito__icontains=circuito_filtro)
        receptores = receptores.filter(num_circuito__icontains=circuito_filtro)

    if tipo_manutencao:
        transmissores = transmissores.filter(tipo_manutencao=tipo_manutencao)
        receptores = receptores.filter(tipo_manutencao=tipo_manutencao)

    if data_inicio:
        transmissores = transmissores.filter(data_manutencao__date__gte=data_inicio)
        receptores = receptores.filter(data_manutencao__date__gte=data_inicio)

    if data_fim:
        transmissores = transmissores.filter(data_manutencao__date__lte=data_fim)
        receptores = receptores.filter(data_manutencao__date__lte=data_fim)

    total_tx = transmissores.count()
    total_rx = receptores.count()

    tx_por_circuito = (
        transmissores.values("num_circuito")
        .annotate(total=Count("id"))
        .order_by("num_circuito")
    )

    rx_por_circuito = (
        receptores.values("num_circuito")
        .annotate(total=Count("id"))
        .order_by("num_circuito")
    )

    tipo_manutencao_qs = (
        transmissores.values("tipo_manutencao")
        .annotate(total=Count("id"))
        .order_by("tipo_manutencao")
    )

    ultimos_tx = transmissores.order_by("-data_manutencao", "-id")[:10]

    ultimos_rx_qs = receptores.order_by("-data_manutencao", "-id")[:10]
    ultimos_rx = []

    for item in ultimos_rx_qs:
        valor_relacao = relacao_para_float(item.relacao)

        if valor_relacao is None:
            classe_relacao = ""
        elif valor_relacao < 60:
            classe_relacao = "relacao-baixa"
        elif valor_relacao > 80:
            classe_relacao = "relacao-alta"
        else:
            classe_relacao = "relacao-normal"

        ultimos_rx.append({
            "obj": item,
            "classe_relacao": classe_relacao,
        })

    relacoes_por_circuito = {}
    contagem_abaixo_60 = 0
    contagem_entre_60_80 = 0
    contagem_acima_80 = 0

    receptores_ordenados = receptores.order_by("num_circuito", "-data_manutencao", "-id")

    for r in receptores_ordenados:
        circuito = (r.num_circuito or "").strip().upper()

        if circuito not in relacoes_por_circuito:
            valor = relacao_para_float(r.relacao)
            if valor is None:
                continue

            if valor < 60:
                classificacao = "Abaixo de 60%"
                classe_relacao = "relacao-baixa"
                contagem_abaixo_60 += 1
            elif valor > 80:
                classificacao = "Acima de 80%"
                classe_relacao = "relacao-alta"
                contagem_acima_80 += 1
            else:
                classificacao = "Entre 60% e 80%"
                classe_relacao = "relacao-normal"
                contagem_entre_60_80 += 1

            relacoes_por_circuito[circuito] = {
                "circuito": circuito,
                "relacao": valor,
                "classificacao": classificacao,
                "classe_relacao": classe_relacao,
            }

    lista_relacoes = list(relacoes_por_circuito.values())

    circuitos_criticos = [
        item for item in lista_relacoes
        if item["classificacao"] in ["Abaixo de 60%", "Acima de 80%"]
    ]

    relacao_labels = [item["circuito"] for item in lista_relacoes]
    relacao_data = [item["relacao"] for item in lista_relacoes]

    relacao_cores = []
    for item in lista_relacoes:
        valor = item["relacao"]

        if valor < 60:
            relacao_cores.append("rgba(255, 193, 7, 0.9)")   # amarelo
        elif 60 <= valor <= 80:
            relacao_cores.append("rgba(13, 110, 253, 0.9)")  # azul
        else:
            relacao_cores.append("rgba(220, 53, 69, 0.9)")   # vermelho

    circuitos_em_degradacao = detectar_degradacao_faixa(receptores)

    total_degradacao_negativa = sum(
        1 for item in circuitos_em_degradacao if item["tipo_degradacao"] == "Negativa"
    )
    total_degradacao_positiva = sum(
        1 for item in circuitos_em_degradacao if item["tipo_degradacao"] == "Positiva"
    )

    context = {
        "lista_de_estacoes": lista_de_estacoes,
        "selected_estacao_id": str(estacao_id) if estacao_id else "",
        "estacao_nome": estacao_nome,

        "circuito_filtro": circuito_filtro or "",
        "tipo_manutencao": tipo_manutencao or "",
        "data_inicio": data_inicio or "",
        "data_fim": data_fim or "",

        "total_tx": total_tx,
        "total_rx": total_rx,

        "tx_labels": json.dumps([x["num_circuito"] for x in tx_por_circuito]),
        "tx_data": json.dumps([x["total"] for x in tx_por_circuito]),

        "rx_labels": json.dumps([x["num_circuito"] for x in rx_por_circuito]),
        "rx_data": json.dumps([x["total"] for x in rx_por_circuito]),

        "tipo_labels": json.dumps([x["tipo_manutencao"] for x in tipo_manutencao_qs]),
        "tipo_data": json.dumps([x["total"] for x in tipo_manutencao_qs]),

        "relacao_labels": json.dumps(relacao_labels),
        "relacao_data": json.dumps(relacao_data),
        "relacao_cores": json.dumps(relacao_cores),

        "contagem_abaixo_60": contagem_abaixo_60,
        "contagem_entre_60_80": contagem_entre_60_80,
        "contagem_acima_80": contagem_acima_80,

        "circuitos_criticos": circuitos_criticos,

        "circuitos_em_degradacao": circuitos_em_degradacao,
        "total_degradacao_gradual": len(circuitos_em_degradacao),
        "total_degradacao_negativa": total_degradacao_negativa,
        "total_degradacao_positiva": total_degradacao_positiva,

        "ultimos_tx": ultimos_tx,
        "ultimos_rx": ultimos_rx,
    }

    return render(request, "cdv_api/dashboard_manutencao.html", context)

@login_required
def historico_circuito(request):

    circuito = request.GET.get("circuito")
    estacao_id = request.GET.get("estacao_id")

    if not circuito:
        return JsonResponse({"erro": "Circuito não informado"})

    receptores = (
        Receptor.objects
        .filter(num_circuito=circuito)
        .order_by("-data_manutencao", "-id")[:10]
    )

    receptores = list(reversed(receptores))

    datas = []
    relacoes = []

    for r in receptores:

        valor = relacao_para_float(r.relacao)

        if valor is None:
            continue

        datas.append(r.data_manutencao.strftime("%d/%m"))
        relacoes.append(valor)

    return JsonResponse({
        "datas": datas,
        "relacoes": relacoes
    })