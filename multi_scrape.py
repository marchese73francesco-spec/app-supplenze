"""
Esegue lo scraping su tutte le province presenti in province_sicilia.json
che hanno una "pagina_gps" impostata (non null).

USO
---
python multi_scrape.py ./output
"""

import json
import os
import sys

from graduatoria_scraper import scrape_provincia

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "province_sicilia.json")


def carica_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    config.pop("_nota", None)
    return config


def run(out_folder_base: str):
    config = carica_config()
    riepilogo_generale = {}

    for provincia, info in config.items():
        pagina = info.get("pagina_gps")
        if not pagina:
            print(f"\n=== {provincia}: SALTATA (nessuna pagina_gps configurata) ===")
            continue

        print(f"\n=== {provincia} ({info.get('formato', '?')}) ===")
        out_folder = os.path.join(out_folder_base, provincia.lower().replace(" ", "_"))

        try:
            tabelle = scrape_provincia(pagina, out_folder)
            riepilogo_generale[provincia] = {
                chiave: len(tabella) for chiave, tabella in tabelle.items()
            }
        except Exception as exc:  # noqa: BLE001
            print(f"  ERRORE per {provincia}: {exc}")
            riepilogo_generale[provincia] = {"errore": str(exc)}

    print("\n\n===== RIEPILOGO GENERALE =====")
    for provincia, dati in riepilogo_generale.items():
        print(f"{provincia}: {dati}")


if __name__ == "__main__":
    out_base = sys.argv[1] if len(sys.argv) > 1 else "./output"
    run(out_base)
