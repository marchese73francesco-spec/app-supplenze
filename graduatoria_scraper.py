"""
Adapter di scraping per le Graduatorie Provinciali per le Supplenze (GPS).

COME FUNZIONA
-------------
1. discover_links(page_url)
   Scarica la pagina HTML di un Ambito Territoriale (es. la pagina "Graduatorie GPS
   provincia di Palermo") ed estrae tutti i link ai file scaricabili (.xls/.xlsx/.pdf),
   provando a dedurre la classe di concorso / fascia dal nome del file
   (es. "graduatoria_provinciale_aa-2__24072026.xls" -> classe "AA", fascia "2").

2. download_file(url, dest_folder)
   Scarica il singolo file su disco.

3. parse_graduatoria_file(path)
   Legge il file (Excel) in un pandas DataFrame e prova a riconoscere le colonne
   chiave (nominativo, punteggio, posizione) cercando tra le intestazioni più comuni
   usate dagli USR. Le intestazioni NON sono standardizzate a livello nazionale,
   quindi questa funzione è "best effort" e va raffinata provincia per provincia.

4. scrape_provincia(page_url, out_folder)
   Mette insieme i tre passaggi sopra per una singola provincia.

NOTA IMPORTANTE
---------------
Questo script estrae la GRADUATORIA (la classifica per punteggio), che è il dato
di base necessario. Il punteggio dell'"ultimo chiamato" per una supplenza è
un'informazione ulteriore che nella maggior parte delle province viene pubblicata
a parte, come esito delle convocazioni (elenco di chi ha accettato/rifiutato un
incarico), spesso con un decreto/allegato separato pubblicato durante l'anno
scolastico. Il prossimo passo, una volta validato questo primo livello, è
individuare e agganciare anche quella fonte.

DIPENDENZE
----------
pip install requests beautifulsoup4 pandas xlrd openpyxl --break-system-packages

USO DA RIGA DI COMANDO
-----------------------
python graduatoria_scraper.py "https://pa.usr.sicilia.it/graduatorie-provinciali-...-palermo/" ./output_palermo
"""

import os
import re
import sys
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import pandas as pd


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GraduatorieScraper/0.1; +per uso personale)"
}

# Codici di classe di concorso/ordine osservati nei nomi file reali (Palermo):
# AA (infanzia), EE (primaria), MM (secondaria I grado), SS (secondaria II grado),
# PPPP (personale educativo, con tabelle TAB9/TAB10). La fascia (1 o 2) segue il codice.
# Esempi reali: "graduatoria_provinciale_aa-1__24072026.xls",
#               "graduatoria_provinciale_pppp_tab9__24072026.xls"
CLASSE_PATTERN = re.compile(
    r"(?P<codice>AA|EE|MM|SS|PPPP)[_\-]?(?:TAB)?[_\-]?(?P<fascia>\d+)",
    re.IGNORECASE,
)

# Parole nel nome file che indicano che il documento NON è una graduatoria
# (decreto di pubblicazione, informativa privacy, modulo di reclamo) o che
# riguarda personale ATA, escluso su richiesta. A differenza di prima, questa
# lista è l'UNICO criterio di esclusione: non escludiamo più "ogni PDF senza
# codice riconosciuto", perché alcune province (es. Agrigento) chiamano le
# graduatorie con nomi descrittivi invece che coi codici AA/EE/MM/SS.
FILE_SKIP_KEYWORDS = (
    "registro ufficiale",
    "ata",
    "informativa",
    "istanza di rettifica",
    "istanza-di-rettifica",
    "incrociat",  # copre "incrociata"/"incrociate": tabelle derivate che altrimenti
                  # sovrascriverebbero la graduatoria vera con la stessa chiave (es. SS-2)
)

FILE_EXTENSIONS = (".xls", ".xlsx", ".pdf", ".zip")


def _classifica_filename(filename: str) -> tuple[str | None, str | None]:
    """Deduce codice classe/ordine e fascia dal nome del file.
    Prova prima i codici standard (AA/EE/MM/SS/PPPP), poi un fallback basato
    su parole italiane per le province che non usano quei codici (es. Agrigento:
    'SS Scuola Secondaria II Grado_2 Fascia' invece di 'ss-2')."""
    match = CLASSE_PATTERN.search(filename)
    if match:
        return match.group("codice").upper(), match.group("fascia")

    normalizzato = re.sub(r"[-_]", " ", filename.lower())

    if "secondaria" in normalizzato and ("ii grado" in normalizzato or "2 grado" in normalizzato):
        ordine = "SS"
    elif "secondaria" in normalizzato and ("i grado" in normalizzato or "1 grado" in normalizzato):
        ordine = "MM"
    elif "primaria" in normalizzato:
        ordine = "EE"
    elif "infanzia" in normalizzato:
        ordine = "AA"
    elif "personale educativo" in normalizzato or "educativo" in normalizzato:
        ordine = "PPPP"
    else:
        ordine = None

    fascia_match = re.search(r"\bfascia\s*(\d)\b|\b(\d)\s*fascia\b", normalizzato)
    if fascia_match:
        fascia = fascia_match.group(1) or fascia_match.group(2)
    elif re.search(r"\bii\s*fascia\b", normalizzato):
        fascia = "2"
    elif re.search(r"\bi\s*fascia\b", normalizzato):
        fascia = "1"
    else:
        fascia = None

    if ordine is None and fascia is None:
        return None, None
    return ordine, fascia


def _da_escludere(filename: str) -> bool:
    # Normalizza -, _, ( ) e . in spazi: "registro-ufficialeu" e "registro_ufficiale"
    # diventano entrambi confrontabili con "registro ufficiale".
    normalizzato = re.sub(r"[-_().]", " ", filename.lower())
    return any(keyword in normalizzato for keyword in FILE_SKIP_KEYWORDS)


def extract_links_from_html(html: str, base_url: str) -> list[dict]:
    """Estrae i link ai file scaricabili da un HTML già scaricato.
    Separata da discover_links per poter essere testata offline con un HTML
    di esempio, senza bisogno di connessione di rete."""
    soup = BeautifulSoup(html, "html.parser")

    results = []
    seen_urls = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.lower().endswith(FILE_EXTENSIONS):
            continue

        full_url = urljoin(base_url, href)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        filename = os.path.basename(full_url)

        if _da_escludere(filename):
            continue

        codice, fascia = _classifica_filename(filename)

        results.append(
            {
                "url": full_url,
                "filename": filename,
                "codice_dedotto": codice,
                "fascia_dedotta": fascia,
                "estensione": os.path.splitext(filename)[1].lower(),
            }
        )

    return results


def discover_links(page_url: str) -> list[dict]:
    """Scarica la pagina e trova i link ai file di graduatoria."""
    resp = requests.get(page_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return extract_links_from_html(resp.text, page_url)


def download_file(url: str, dest_folder: str, force: bool = False, tentativi: int = 3) -> str:
    """Scarica un file e restituisce il percorso locale.
    Se il file esiste già (stesso nome) lo riusa, a meno di force=True:
    utile perché queste pagine vengono spesso ripubblicate/aggiornate e
    non ha senso riscaricare tutto ogni volta."""
    os.makedirs(dest_folder, exist_ok=True)
    filename = os.path.basename(url)
    dest_path = os.path.join(dest_folder, filename)

    if os.path.exists(dest_path) and not force:
        return dest_path

    ultimo_errore = None
    for tentativo in range(1, tentativi + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=60)
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(resp.content)
            return dest_path
        except requests.RequestException as exc:  # noqa: PERF203
            ultimo_errore = exc
            print(f"    [tentativo {tentativo}/{tentativi}] errore download {filename}: {exc}")

    raise RuntimeError(f"Impossibile scaricare {url} dopo {tentativi} tentativi") from ultimo_errore


# Per ogni campo, elenco di nomi di colonna ESATTI (case-insensitive) da cercare
# per primi, in ordine di priorità. Solo se nessuno di questi combacia si passa
# a una ricerca "contiene la parola" più permissiva (COLUMN_HINTS sotto).
# Questo evita scambi pericolosi scoperti sui dati reali di Palermo: la ricerca
# "contiene 'graduatoria'" prendeva "CODICE GRADUATORIA DI INCLUSIONE E
# DESCRIZIONE" (che è in realtà la classe di concorso, es. A002) invece di
# "POSIZIONE GRADUATORIA"; e "contiene 'punteggio'" prendeva "PUNTEGGIO TITOLO
# ACCESSO" (un punteggio parziale) invece di "PUNTEGGIO TOTALE".
COLUMN_EXACT = {
    "posizione": ["posizione graduatoria", "posizione"],
    "punteggio": ["punteggio totale", "totale punti", "punti totali"],
    "cognome": ["cognome"],
    "nome": ["nome"],
    "nominativo": ["nominativo", "candidato"],
    "classe_concorso": [
        "codice graduatoria di inclusione e descrizione",
        "classe di concorso",
        "codice classe di concorso",
        "cdc",
    ],
}

# Fallback permissivo ("contiene questa parola"), usato solo se non c'è stata
# nessuna corrispondenza esatta sopra. Tenuto più povero apposta, per non
# ripetere lo stesso tipo di scambio visto sopra.
COLUMN_HINTS = {
    "nominativo": ["cognome", "candidato"],
    "punteggio": ["punti tot", "totale punti"],
    "posizione": ["pos.", "n. ord", "numero ordine"],
}


def _match_esatto(columns: list[str], candidati: list[str]) -> str | None:
    lowered = {str(c).strip().lower(): c for c in columns}
    for candidato in candidati:
        if candidato in lowered:
            return lowered[candidato]
    return None


def _match_column(columns: list[str], hints: list[str]) -> str | None:
    lowered = {c: str(c).strip().lower() for c in columns}
    for col, low in lowered.items():
        for hint in hints:
            if hint in low:
                return col
    return None


def _trova_colonna(columns: list[str], campo: str) -> str | None:
    """Cerca prima una corrispondenza esatta, poi ripiega sul fallback permissivo."""
    esatta = _match_esatto(columns, COLUMN_EXACT.get(campo, []))
    if esatta is not None:
        return esatta
    return _match_column(columns, COLUMN_HINTS.get(campo, []))


def _parse_pdf_graduatoria(path: str) -> pd.DataFrame:
    """Estrae le tabelle da un PDF di graduatoria usando pdfplumber.
    I PDF non sono tabelle strutturate come gli Excel: l'estrazione è
    più fragile e va verificata caso per caso (intestazioni ripetute
    su ogni pagina, tabelle che si spezzano tra una pagina e l'altra, ecc.)."""
    import pdfplumber

    righe = []
    intestazione = None

    with pdfplumber.open(path) as pdf:
        for pagina in pdf.pages:
            for tabella in pagina.extract_tables():
                if not tabella:
                    continue
                if intestazione is None:
                    intestazione = tabella[0]

                # Scarta qualunque riga identica all'intestazione, ovunque si trovi
                # nel blocco: capita che si ripeta a ogni cambio pagina, anche
                # quando pdfplumber unisce più pagine in un unico blocco tabella.
                corpo = [riga for riga in tabella if riga != intestazione]
                righe.extend(corpo)

    if intestazione is None:
        raise ValueError("Nessuna tabella trovata nel PDF")

    df = pd.DataFrame(righe, columns=intestazione)
    return df


def parse_graduatoria_file(path: str) -> pd.DataFrame:
    """Legge un file di graduatoria (Excel o PDF) e prova a normalizzare le colonne chiave."""
    ext = os.path.splitext(path)[1].lower()

    if ext in (".xls", ".xlsx"):
        df = pd.read_excel(path)
    elif ext == ".pdf":
        df = _parse_pdf_graduatoria(path)
    else:
        raise ValueError(f"Formato non supportato: {ext}")

    colonne = list(df.columns)

    col_posizione = _trova_colonna(colonne, "posizione")
    col_punteggio = _trova_colonna(colonne, "punteggio")
    col_cognome = _match_esatto(colonne, COLUMN_EXACT["cognome"])
    col_nome = _match_esatto(colonne, COLUMN_EXACT["nome"])
    col_nominativo = _trova_colonna(colonne, "nominativo")
    col_classe_concorso = _match_esatto(colonne, COLUMN_EXACT["classe_concorso"])

    rename = {}
    if col_posizione:
        rename[col_posizione] = "posizione"
    if col_punteggio:
        rename[col_punteggio] = "punteggio"
    if col_classe_concorso:
        rename[col_classe_concorso] = "classe_concorso"

    df = df.rename(columns=rename)

    if col_cognome and col_nome:
        # Cognome e nome sono colonne separate (caso Palermo): le combino invece
        # di rinominare solo "cognome" in "nominativo" e perdere il nome.
        df["nominativo"] = df[col_cognome].astype(str) + " " + df[col_nome].astype(str)
    elif col_nominativo:
        df = df.rename(columns={col_nominativo: "nominativo"})

    missing = [
        campo
        for campo, presente in {
            "nominativo": "nominativo" in df.columns,
            "punteggio": "punteggio" in df.columns,
            "posizione": "posizione" in df.columns,
        }.items()
        if not presente
    ]
    if missing:
        print(
            f"[avviso] In {os.path.basename(path)} non ho riconosciuto le colonne: {missing}. "
            f"Colonne disponibili: {colonne}"
        )
    if not col_classe_concorso:
        print(f"[avviso] In {os.path.basename(path)} non ho trovato la colonna classe di concorso.")

    return df


import zipfile


def _estrai_zip(zip_path: str, dest_folder: str) -> list[dict]:
    """Estrae uno zip (es. 'graduatorie.zip' di Catania) e classifica i file
    al suo interno come se fossero link scoperti direttamente sulla pagina.
    Il nome dello zip stesso è generico: la classe di concorso si deduce dal
    nome dei singoli file contenuti."""
    estratti_folder = os.path.join(dest_folder, os.path.splitext(os.path.basename(zip_path))[0])
    os.makedirs(estratti_folder, exist_ok=True)

    risultati = []
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(estratti_folder)
        for nome_interno in z.namelist():
            filename = os.path.basename(nome_interno)
            if not filename.lower().endswith((".xls", ".xlsx", ".pdf")):
                continue
            if _da_escludere(filename):
                continue

            codice, fascia = _classifica_filename(filename)
            risultati.append(
                {
                    "url": None,
                    "filename": filename,
                    "percorso_locale": os.path.join(estratti_folder, nome_interno),
                    "codice_dedotto": codice,
                    "fascia_dedotta": fascia,
                    "estensione": os.path.splitext(filename)[1].lower(),
                }
            )

    return risultati


def scrape_provincia(page_url: str, out_folder: str) -> dict[str, pd.DataFrame]:
    """Scarica e analizza tutti i file di graduatoria trovati in una pagina provincia."""
    links = discover_links(page_url)
    print(f"Trovati {len(links)} file scaricabili su {page_url}")

    parsed = {}
    for link in links:
        print(f"  - scarico {link['filename']} ...")
        local_path = download_file(link["url"], out_folder)

        if link["estensione"] == ".zip":
            print(f"    -> estraggo {link['filename']} ...")
            contenuti = _estrai_zip(local_path, out_folder)
            print(f"    -> trovati {len(contenuti)} file dentro lo zip")
            file_da_leggere = [(c["percorso_locale"], c) for c in contenuti]
        else:
            file_da_leggere = [(local_path, link)]

        for percorso, info in file_da_leggere:
            try:
                df = parse_graduatoria_file(percorso)
                key = f"{info['codice_dedotto']}-{info['fascia_dedotta']}" if info["codice_dedotto"] else info["filename"]
                parsed[key] = df
                print(f"    -> {info['filename']}: {len(df)} righe lette")
            except Exception as exc:  # noqa: BLE001
                print(f"    -> errore nella lettura di {info['filename']}: {exc}")

    return parsed


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python graduatoria_scraper.py <url_pagina_provincia> <cartella_output>")
        sys.exit(1)

    url_arg = sys.argv[1]
    out_arg = sys.argv[2]

    tabelle = scrape_provincia(url_arg, out_arg)

    print("\nRiepilogo tabelle lette:")
    for nome, tabella in tabelle.items():
        print(f"  {nome}: {tabella.shape[0]} righe, colonne: {list(tabella.columns)}")
