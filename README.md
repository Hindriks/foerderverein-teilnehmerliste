# Teilnehmerliste per QR (Streamlit, Deutsch)

**Titel:** 🧯 Teilnehmerliste Feuerwehr Nordhorn Förderverein  
**Admin-Passwort (ENV):** `ADMIN_KEY=112`  
**Logo-Datei:** `Logo Förderverein.jpg` (separate Datei, links neben dem Titel)

## Felder
- Veranstaltung* (Brandschutzhelfer-Seminar / Feuerlöschtraining)
- Name*
- Unternehmen / Betrieb*
- Einverständnis Fotos* (Ja / Nein)
- Datum (automatisch, am Tag des Eintrags)

## Start
```bash
pip install -r requirements.txt
# optional: eigenen Admin-Key setzen
#   Linux/macOS: export ADMIN_KEY=112
#   Windows (PowerShell): setx ADMIN_KEY "112"
streamlit run app.py
```

## Nutzung
- Termin anlegen → QR-Code wird angezeigt → scannen lassen
- Teilnehmer tragen sich ein unter `?event=<ID>&mode=form`
- Admin-Ansicht: `?event=<ID>&mode=admin&key=<ADMIN_KEY>`
- Export CSV/XLSX, Zurücksetzen pro Event

## Hinweis
- Daten werden lokal in `./data/` gespeichert:
  - `<EVENT_ID>.csv`, `<EVENT_ID>_meta.json`, `<EVENT_ID>_qr.png`