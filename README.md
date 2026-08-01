# App Supplenze

App web che, dati classe di concorso e punteggio, indica in quali province
ci sono più possibilità di ottenere una supplenza.

## Stato attuale

- Form + calcolo funzionanti (`app.py`, `templates/index.html`)
- Dati attualmente di **esempio** (`data/ultimo_chiamato.json`) — vanno sostituiti
  con i dati reali raccolti dallo scraper (`scraper/graduatoria_scraper.py`)
- Lo scraper trova ed estrae le graduatorie in Excel dai siti USR, ma va ancora
  esteso per estrarre nello specifico il punteggio dell'"ultimo chiamato"

## Come provarla sul tuo computer

```bash
pip install -r requirements.txt --break-system-packages
python app.py
```

Poi apri http://localhost:5000

## Come pubblicarla online GRATIS (Render.com)

1. **Crea un account** su https://render.com (puoi accedere con GitHub)

2. **Carica questo progetto su GitHub**
   - Crea un nuovo repository (es. `app-supplenze`)
   - Carica dentro tutti i file di questa cartella

3. **Su Render**:
   - Clicca "New +" → "Web Service"
   - Collega il repository GitHub appena creato
   - Imposta:
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `gunicorn app:app`
   - Piano: **Free**
   - Clicca "Create Web Service"

4. Dopo qualche minuto Render ti darà un indirizzo tipo
   `https://app-supplenze.onrender.com` — è la tua app online.

5. **Dominio personalizzato (facoltativo)**: se in futuro compri un dominio
   (es. su Namecheap o Register.it), in Render puoi collegarlo dalla sezione
   "Settings" → "Custom Domains" del tuo servizio.

## Prossimi passi

1. Validare lo scraper su dati reali (girandolo sul tuo computer)
2. Estendere lo scraper per trovare anche il dato "ultimo chiamato" (di solito
   pubblicato separatamente come esito convocazioni)
3. Automatizzare l'aggiornamento periodico dei dati (es. un "Cron Job" su
   Render che rilancia lo scraper una volta a settimana e aggiorna il JSON)
4. Estendere la copertura da Sicilia a tutte le regioni italiane
