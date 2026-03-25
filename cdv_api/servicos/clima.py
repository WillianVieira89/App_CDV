import os
import logging
import unicodedata
import datetime

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

logger.info("WEATHERAPI_KEY carregada: %s", bool(os.getenv("WEATHERAPI_KEY")))

TIMEOUT_API = 5

# Coordenadas por estação
COORDENADAS_ESTACOES = {
    "Capão Redondo": {"lat": -23.6682, "lon": -46.7802},
    "Campo Limpo": {"lat": -23.6492, "lon": -46.7582},
    "Vila Das Belezas": {"lat": -23.6404, "lon": -46.7458},
    "Giovanni Gronchi": {"lat": -23.6439, "lon": -46.7332},
    "Santo Amaro": {"lat": -23.6546, "lon": -46.7100},
    "Largo Treze": {"lat": -23.6549, "lon": -46.7017},
    "Adolfo Pinheiro": {"lat": -23.6508, "lon": -46.6942},
    "Alto Da Boa Vista": {"lat": -23.6417, "lon": -46.6990},
    "Borba Gato": {"lat": -23.6335, "lon": -46.6896},
    "Brooklin": {"lat": -23.6261, "lon": -46.6885},
    "Campo Belo": {"lat": -23.6210, "lon": -46.6850},
    "Eucaliptos": {"lat": -23.6108, "lon": -46.6686},
    "Moema": {"lat": -23.6033, "lon": -46.6622},
    "Aacd Servidor": {"lat": -23.5981, "lon": -46.6524},
    "Hospital São Paulo": {"lat": -23.5987, "lon": -46.6456},
    "Santa Cruz": {"lat": -23.5991, "lon": -46.6367},
    "Chácara Klabin": {"lat": -23.5925, "lon": -46.6302},
}


def normalizar_nome_estacao(nome):
    if not nome:
        return ""

    nome = str(nome).strip().replace("-", " ")
    nome = unicodedata.normalize("NFD", nome)
    nome = "".join(c for c in nome if unicodedata.category(c) != "Mn")
    nome = " ".join(nome.split())
    return nome.title()


def obter_coordenadas(estacao_nome):
    nome = normalizar_nome_estacao(estacao_nome)
    return COORDENADAS_ESTACOES.get(nome)


def obter_clima_open_meteo(estacao_nome):
    coords = obter_coordenadas(estacao_nome)
    if not coords:
        raise ValueError(f"Coordenadas não encontradas para a estação: {estacao_nome}")

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "current": "temperature_2m,relative_humidity_2m",
        "timezone": "America/Sao_Paulo",
    }

    resp = requests.get(url, params=params, timeout=TIMEOUT_API)
    resp.raise_for_status()
    data = resp.json()

    current = data.get("current", {})
    temperatura = current.get("temperature_2m")
    umidade = current.get("relative_humidity_2m")

    if temperatura is None:
        raise ValueError("Open-Meteo não retornou temperatura.")

    return {
        "temperatura": float(temperatura),
        "umidade": umidade,
        "fonte": "open-meteo",
        "coletado_em": timezone.now(),
    }


def obter_clima_weatherapi(estacao_nome):
    key = os.getenv("WEATHERAPI_KEY")
    if not key:
        raise ValueError("WEATHERAPI_KEY não configurada.")

    coords = obter_coordenadas(estacao_nome)
    if not coords:
        raise ValueError(f"Coordenadas não encontradas para a estação: {estacao_nome}")

    query = f"{coords['lat']},{coords['lon']}"
    url = "http://api.weatherapi.com/v1/current.json"
    params = {
        "key": key,
        "q": query,
        "aqi": "no",
    }

    resp = requests.get(url, params=params, timeout=TIMEOUT_API)
    resp.raise_for_status()
    data = resp.json()

    current = data.get("current", {})
    temperatura = current.get("temp_c")
    umidade = current.get("humidity")

    if temperatura is None:
        raise ValueError("WeatherAPI não retornou temperatura.")

    return {
        "temperatura": float(temperatura),
        "umidade": umidade,
        "fonte": "weatherapi",
        "coletado_em": timezone.now(),
    }


def obter_ultima_temperatura_salva(estacao_nome):
    from cdv_api.models import Transmissor, Receptor, Estacao

    nome_original = (estacao_nome or "").strip()
    estacao = Estacao.objects.filter(nome=nome_original).first()

    if not estacao:
        nome_normalizado = normalizar_nome_estacao(estacao_nome)
        for est in Estacao.objects.all():
            if normalizar_nome_estacao(est.nome) == nome_normalizado:
                estacao = est
                break

    if not estacao:
        return None

    ultimo_tx = (
        Transmissor.objects.filter(estacao=estacao, temp_celsius__isnull=False)
        .order_by("-data_manutencao", "-horario_coleta", "-id")
        .first()
    )

    ultimo_rx = (
        Receptor.objects.filter(estacao=estacao, temp_celsius__isnull=False)
        .order_by("-data_manutencao", "-horario_coleta", "-id")
        .first()
    )

    candidatos = []

    if ultimo_tx:
        candidatos.append({
            "temperatura": float(ultimo_tx.temp_celsius),
            "coletado_em": ultimo_tx.data_manutencao,
        })

    if ultimo_rx:
        candidatos.append({
            "temperatura": float(ultimo_rx.temp_celsius),
            "coletado_em": ultimo_rx.data_manutencao,
        })

    if not candidatos:
        return None

    candidatos.sort(key=lambda x: x["coletado_em"], reverse=True)
    mais_recente = candidatos[0]

    return {
        "temperatura": mais_recente["temperatura"],
        "umidade": None,
        "fonte": "banco_local",
        "coletado_em": mais_recente["coletado_em"],
    }


def obter_temperatura_estacao(estacao_nome):    
    erros = []

    try:
        resultado = obter_clima_open_meteo(estacao_nome)
        resultado["tentativa"] = "principal"
        return resultado
    except Exception as e:
        erros.append(f"Open-Meteo: {e}")

    try:
        resultado = obter_clima_weatherapi(estacao_nome)
        resultado["tentativa"] = "fallback_api"
        return resultado
    except Exception as e:
        erros.append(f"WeatherAPI: {e}")

    fallback = obter_ultima_temperatura_salva(estacao_nome)
    if fallback:
        fallback["tentativa"] = "fallback_banco"
        fallback["erros"] = erros
        return fallback

    raise Exception("Não foi possível obter a temperatura. " + " | ".join(erros))

def obter_temperatura_open_meteo_horaria(estacao_nome, data_str, hora_str):
    coords = obter_coordenadas(estacao_nome)
    if not coords:
        raise ValueError(f"Coordenadas não encontradas para a estação: {estacao_nome}")

    try:
        data_ref = datetime.datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Data inválida. Use o formato YYYY-MM-DD.")

    try:
        hora_ref = datetime.datetime.strptime(hora_str[:5], "%H:%M").time()
    except ValueError:
        raise ValueError("Hora inválida. Use o formato HH:MM.")

    hoje = timezone.localdate()
    hora_alvo = f"{hora_ref.hour:02d}:00"

    if data_ref == hoje:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "hourly": "temperature_2m,relative_humidity_2m",
            "timezone": "America/Sao_Paulo",
            "forecast_days": 1,
        }
    else:
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "start_date": data_str,
            "end_date": data_str,
            "hourly": "temperature_2m,relative_humidity_2m",
            "timezone": "America/Sao_Paulo",
        }

    resp = requests.get(url, params=params, timeout=TIMEOUT_API)
    resp.raise_for_status()
    data = resp.json()

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    hums = hourly.get("relative_humidity_2m", [])

    alvo = f"{data_str}T{hora_alvo}"

    idx = times.index(alvo) if alvo in times else -1

    if idx == -1:
        # tenta hora anterior/posterior
        h = hora_ref.hour
        alternativas = []
        if h > 0:
            alternativas.append(f"{data_str}T{h-1:02d}:00")
        if h < 23:
            alternativas.append(f"{data_str}T{h+1:02d}:00")

        for alt in alternativas:
            if alt in times:
                idx = times.index(alt)
                break

    if idx == -1:
        raise ValueError("Open-Meteo não encontrou temperatura para o horário informado.")

    temperatura = temps[idx] if idx < len(temps) else None
    umidade = hums[idx] if idx < len(hums) else None

    if temperatura is None:
        raise ValueError("Open-Meteo não retornou temperatura horária.")

    return {
        "temperatura": float(temperatura),
        "umidade": umidade,
        "fonte": "open-meteo-horario",
        "coletado_em": timezone.now(),
    }


def obter_temperatura_por_horario(estacao_nome, data_str, hora_str):
    erros = []

    try:
        return obter_temperatura_open_meteo_horaria(estacao_nome, data_str, hora_str)
    except Exception as e:
        erros.append(f"Open-Meteo horário: {e}")

    # fallback: temperatura atual
    try:
        resultado = obter_clima_weatherapi(estacao_nome)
        resultado["tentativa"] = "fallback_api_atual"
        resultado["erros"] = erros
        return resultado
    except Exception as e:
        erros.append(f"WeatherAPI atual: {e}")

    fallback = obter_ultima_temperatura_salva(estacao_nome)
    if fallback:
        fallback["tentativa"] = "fallback_banco"
        fallback["erros"] = erros
        return fallback

    raise Exception("Não foi possível obter a temperatura por horário. " + " | ".join(erros))