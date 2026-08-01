"""
App Supplenze - trova le province con più possibilità di chiamata
in base a classe di concorso e punteggio.

Per ora legge i dati da data/ultimo_chiamato.json (dati di esempio).
Il prossimo passo è collegare qui l'output dello scraper reale.
"""

import json
import os

from flask import Flask, render_template, request

app = Flask(__name__)

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "ultimo_chiamato.json")


def carica_dati():
    with open(DATA_PATH, encoding="utf-8") as f:
        dati = json.load(f)
    dati.pop("_nota", None)
    return dati


def calcola_possibilita(classe_concorso: str, punteggio: float):
    dati = carica_dati()
    risultati = []

    for provincia, classi in dati.items():
        punteggio_ultimo = classi.get(classe_concorso)
        if punteggio_ultimo is None:
            continue

        margine = punteggio - punteggio_ultimo
        risultati.append(
            {
                "provincia": provincia,
                "punteggio_ultimo_chiamato": punteggio_ultimo,
                "margine": round(margine, 2),
                "possibilita": "alta" if margine >= 0 else "bassa",
            }
        )

    # Ordina dal margine migliore al peggiore
    risultati.sort(key=lambda r: r["margine"], reverse=True)
    return risultati


@app.route("/", methods=["GET", "POST"])
def index():
    risultati = None
    classe_concorso = ""
    punteggio = ""
    errore = None

    if request.method == "POST":
        classe_concorso = request.form.get("classe_concorso", "").strip().upper()
        punteggio_raw = request.form.get("punteggio", "").strip().replace(",", ".")

        try:
            punteggio_val = float(punteggio_raw)
            risultati = calcola_possibilita(classe_concorso, punteggio_val)
            if not risultati:
                errore = "Nessun dato trovato per questa classe di concorso."
        except ValueError:
            errore = "Inserisci un punteggio valido (es. 45.5)."

    return render_template(
        "index.html",
        risultati=risultati,
        classe_concorso=classe_concorso,
        punteggio=punteggio,
        errore=errore,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
