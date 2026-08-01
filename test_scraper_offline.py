"""
Test offline per graduatoria_scraper.extract_links_from_html.

Il frammento HTML qui sotto ricostruisce la struttura reale osservata sulla
pagina GPS di Palermo (stessi nomi file e stesso pattern di link), così da
poter validare la logica di parsing senza bisogno di connessione di rete.

Esegui con: python test_scraper_offline.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from graduatoria_scraper import extract_links_from_html  # noqa: E402


HTML_ESEMPIO_PALERMO = """
<table>
<tr><td><a href="/download/1013/9316/9320/m_pi-aoousppa-registro-ufficialeu-0018768-24-07-2026.pdf">Registro Ufficiale</a></td></tr>
<tr><td><a href="/download/1013/9316/9333/graduatoria_provinciale_aa-1__24072026.xls">AA-1</a></td></tr>
<tr><td><a href="/download/1013/9316/9330/graduatoria_provinciale_aa-2__24072026.xls">AA-2</a></td></tr>
<tr><td><a href="/download/1013/9316/9335/graduatoria_provinciale_ee-1__24072026.xls">EE-1</a></td></tr>
<tr><td><a href="/download/1013/9316/9331/graduatoria_provinciale_ee-2__24072026.xls">EE-2</a></td></tr>
<tr><td><a href="/download/1013/9316/9329/graduatoria_provinciale_pppp_tab9__24072026.xls">PPPP TAB9</a></td></tr>
<tr><td><a href="/download/1013/9316/9332/graduatoria_provinciale_pppp_tab10__24072026.xls">PPPP TAB10</a></td></tr>
<tr><td><a href="/download/1013/9316/9334/graduatoria_provinciale_mm-1__24072026.xls">MM-1</a></td></tr>
<tr><td><a href="/download/1013/9316/9336/graduatoria_provinciale_mm-2__24072026.xls">MM-2</a></td></tr>
<tr><td><a href="/download/1013/9316/9337/graduatoria_provinciale_ss-1__24072026.xls">SS-1</a></td></tr>
<tr><td><a href="/download/1013/9316/9338/graduatoria_provinciale_ss-2__24072026.xls">SS-2</a></td></tr>
<tr><td><a href="/download/1013/9316/9999/graduatoria_provinciale_ata-1__24072026.xls">ATA-1 (da escludere)</a></td></tr>
</table>
"""

BASE_URL = "https://pa.usr.sicilia.it/graduatorie-provinciali-palermo/"


def run():
    links = extract_links_from_html(HTML_ESEMPIO_PALERMO, BASE_URL)

    print(f"Trovati {len(links)} file (esclusi decreto e ATA)\n")
    for link in links:
        print(f"  {link['filename']:55s} -> codice={link['codice_dedotto']!s:6} fascia={link['fascia_dedotta']}")

    # Verifiche automatiche
    filenames = {l["filename"] for l in links}
    assert "m_pi-aoousppa-registro-ufficialeu-0018768-24-07-2026.pdf" not in filenames, \
        "Il decreto non doveva essere incluso"
    assert not any("ata" in f.lower() for f in filenames), \
        "I file ATA non dovevano essere inclusi"
    assert len(links) == 10, f"Attesi 10 file (le 10 graduatorie reali, esclusi decreto e ATA), trovati {len(links)}"

    codici_fasce = {(l["codice_dedotto"], l["fascia_dedotta"]) for l in links}
    attesi = {
        ("AA", "1"), ("AA", "2"), ("EE", "1"), ("EE", "2"),
        ("MM", "1"), ("MM", "2"), ("SS", "1"), ("SS", "2"),
        ("PPPP", "9"), ("PPPP", "10"),
    }
    # PPPP-10 e PPPP-9 sono 2 dei 9 file, gli altri 8 sono le classi AA/EE/MM/SS
    mancanti = attesi - codici_fasce
    extra = codici_fasce - attesi
    assert not mancanti, f"Classificazioni mancanti: {mancanti}"
    assert not extra, f"Classificazioni impreviste: {extra}"

    print("\n✅ Tutti i controlli passati: link trovati, ATA escluso, decreto escluso, classificazione corretta.")


def test_classificazione_stile_agrigento():
    """Verifica il classificatore di riserva per province come Agrigento, che usano
    nomi descrittivi in italiano invece dei codici AA/EE/MM/SS."""
    from graduatoria_scraper import _classifica_filename, _da_escludere

    casi = {
        "m_pi-aoouspag-registro-ufficialeu-0012567-14-07-2026.pdf": None,  # escluso
        "ss-scuola-secondaria-ii-grado_2-fascia.pdf": ("SS", "2"),
        "ss-scuola-secondaria-ii-grado_1-fascia.pdf": ("SS", "1"),
        "mm-scuola-secondaria-i-grado_2-fascia.pdf": ("MM", "2"),
        "mm-scuola-secondaria-i-grado_1-fascia.pdf": ("MM", "1"),
        "gps-2-fascia-primaria-comune_sostegno-biennio-2026_28.pdf": ("EE", "2"),
        "gps-2-fascia-personale-educativo-biennio-2026_28.pdf": ("PPPP", "2"),
        "gps-2-fascia-infanzia-comune_sostegno-biennio-2026_28.pdf": ("AA", "2"),
        "gps-1-fascia-primaria-comune_sostegno-biennio-2026_28.pdf": ("EE", "1"),
        "gps-1-fascia-personale-educativo-biennio-2026_28.pdf": ("PPPP", "1"),
        "gps-1-fascia-infanzia-comune_sostegno-biennio-2026_28.pdf": ("AA", "1"),
    }
    # I file "incrociate" vanno esclusi (altrimenti sovrascriverebbero le graduatorie vere)
    esclusi_extra = ["graduatorie-incrociate-2-fascia-secondaria-di-ii-grado.pdf"]

    for nome, atteso in casi.items():
        escluso = _da_escludere(nome)
        if atteso is None:
            assert escluso, f"{nome} doveva essere escluso (decreto)"
        else:
            assert not escluso, f"{nome} non doveva essere escluso"
            codice, fascia = _classifica_filename(nome)
            assert (codice, fascia) == atteso, f"{nome}: atteso {atteso}, trovato ({codice}, {fascia})"

    for nome in esclusi_extra:
        assert _da_escludere(nome), f"{nome} doveva essere escluso (tabella incrociata)"

    print("✅ Classificazione stile Agrigento (nomi descrittivi) corretta.")


def test_riconoscimento_colonne_reale():
    """Verifica che il riconoscimento colonne non ripeta lo scambio scoperto sui
    dati reali di Palermo: 'CODICE GRADUATORIA DI INCLUSIONE E DESCRIZIONE' (che
    contiene la classe di concorso, es. A002) NON deve finire scambiato per
    'posizione', e 'PUNTEGGIO TITOLO ACCESSO' (parziale) NON deve finire
    scambiato per 'punteggio' al posto di 'PUNTEGGIO TOTALE'."""
    import pandas as pd
    from graduatoria_scraper import parse_graduatoria_file

    df_input = pd.DataFrame({
        "UFFICIO PROVINCIALE": ["PA", "PA"],
        "CODICE GRADUATORIA DI INCLUSIONE E DESCRIZIONE": ["A002", "A002"],
        "FASCIA": [1, 1],
        "ORDINE SCUOLA GRADUATORIA": ["SS", "SS"],
        "COGNOME": ["ROSSI", "BIANCHI"],
        "NOME": ["MARIO", "LUCA"],
        "POSIZIONE GRADUATORIA": [1, 2],
        "PUNTEGGIO TITOLO ACCESSO": [54.0, 33.0],
        "PUNTEGGIO TOTALE": [208.5, 155.0],
    })
    percorso = "/tmp/_test_riconoscimento_colonne.xlsx"
    df_input.to_excel(percorso, index=False)

    df = parse_graduatoria_file(percorso)

    assert df.loc[0, "nominativo"] == "ROSSI MARIO", "cognome+nome non combinati correttamente"
    assert df.loc[0, "posizione"] == 1, "posizione scambiata con un'altra colonna"
    assert df.loc[0, "punteggio"] == 208.5, "punteggio totale scambiato con un punteggio parziale"
    assert df.loc[0, "classe_concorso"] == "A002", "classe di concorso non riconosciuta"

    print("✅ Riconoscimento colonne corretto (nessuno scambio posizione/classe o punteggio parziale/totale).")


if __name__ == "__main__":
    run()
    test_classificazione_stile_agrigento()
    test_riconoscimento_colonne_reale()
