"""
Recomendação em linguagem simples, voltada para agricultores.

Retorna dict com:
  acao:        "irrigar" | "aguardar" | "ok" | "sem_dados"
  titulo:      título curto com emoji
  mensagem:    instrução principal (linguagem leiga)
  explicacao:  por que (linguagem leiga)
  cor:         "success" | "warning" | "error" | "info"
"""
from datetime import date, timedelta

from . import config


def recomendar(balanco: list, previsao: dict, vazao_mm_h: float) -> dict:
    if not balanco:
        return {
            "acao": "sem_dados",
            "titulo": "⏳ Precisamos de mais informações",
            "mensagem": "Ainda não temos dados de clima para este talhão.",
            "explicacao": "Clique em 'Carregar clima' para o sistema calcular a recomendação.",
            "cor": "info",
        }

    hoje = balanco[-1]
    chuva_48h = sum(
        previsao.get((date.today() + timedelta(days=i)).isoformat(), {}).get("chuva", 0)
        for i in (1, 2)
    )

    if chuva_48h >= config.RAIN_WAIT_MM:
        return {
            "acao": "aguardar",
            "titulo": "🌧️ Espere a chuva",
            "mensagem": (
                f"Não regue hoje. A previsão indica cerca de {chuva_48h:.0f} mm "
                f"de chuva em até 48 horas."
            ),
            "explicacao": (
                "A chuva prevista é suficiente para as plantas neste período. "
                "Regar agora seria desperdiçar água e energia elétrica."
            ),
            "cor": "info",
        }

    if hoje["deficit"]:
        lamina = hoje["dr"]
        horas = lamina / vazao_mm_h if vazao_mm_h > 0 else 0
        if horas >= 1:
            tempo = f"cerca de {horas:.1f} hora(s)"
        else:
            tempo = f"cerca de {int(horas * 60)} minuto(s)"

        return {
            "acao": "irrigar",
            "titulo": "💧 Regue hoje",
            "mensagem": (
                f"Coloque aproximadamente {lamina:.0f} mm de água neste talhão hoje. "
                f"No seu sistema, isso equivale a {tempo} de irrigação."
            ),
            "explicacao": (
                "As plantas já consumiram quase toda a água disponível no solo. "
                "Se não regar hoje, elas podem sofrer com a falta de água e ter "
                "perda de produtividade."
            ),
            "cor": "error",
        }

    return {
        "acao": "ok",
        "titulo": "✅ Solo em boa umidade",
        "mensagem": "Não precisa regar hoje. O solo ainda tem água suficiente para as plantas.",
        "explicacao": (
            "As plantas estão em boa condição. Continue acompanhando — "
            "o sistema vai avisar quando chegar o momento de regar."
        ),
        "cor": "success",
    }
