
import os
import uuid
import io
import base64
from datetime import datetime
from urllib.parse import urlencode

import pandas as pd
import streamlit as st
from PIL import Image
import qrcode
from dotenv import load_dotenv

# ---------- Config ----------
load_dotenv()
st.set_page_config(page_title="Teilnehmerliste Feuerwehr Nordhorn Förderverein", page_icon="🧯", layout="wide")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)
ADMIN_KEY = os.getenv("ADMIN_KEY", "112")
LOGO_FILENAME = os.getenv("LOGO_FILE", "Logo Förderverein.jpg")

APP_TITLE = "🧯 Teilnehmerliste Feuerwehr Nordhorn Förderverein"

# ---------- Helpers ----------
def event_path(event_id: str) -> str:
    return os.path.join(DATA_DIR, f"{event_id}.csv")

def qr_path(event_id: str) -> str:
    return os.path.join(DATA_DIR, f"{event_id}_qr.png")

def meta_path(event_id: str) -> str:
    return os.path.join(DATA_DIR, f"{event_id}_meta.json")

def load_event_df(event_id: str) -> pd.DataFrame:
    path = event_path(event_id)
    if os.path.exists(path):
        return pd.read_csv(path)
    # Columns: event_type, timestamp, date, name, company, photo_consent
    return pd.DataFrame(columns=["event_type","timestamp","date","name","company","photo_consent"])

def save_event_df(event_id: str, df: pd.DataFrame):
    df.to_csv(event_path(event_id), index=False)

def export_xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Teilnehmer")
    buf.seek(0)
    return buf.read()

def make_qr_png_bytes(text: str) -> bytes:
    img = qrcode.make(text)
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()

def new_event(title: str, date: str, location: str):
    event_id = uuid.uuid4().hex[:10]
    meta = {
        "id": event_id,
        "title": title.strip(),
        "date": date.strip(),
        "location": location.strip(),
        "created_at": datetime.now().isoformat(timespec="seconds")
    }
    # Save empty CSV to initialize
    save_event_df(event_id, load_event_df(event_id))
    # Save QR (relative link so es funktioniert im gleichen Host)
    form_url = f"?event={event_id}&mode=form"
    qr_png = make_qr_png_bytes(form_url)
    with open(qr_path(event_id), "wb") as f:
        f.write(qr_png)
    # Save metadata JSON
    with open(meta_path(event_id), "w", encoding="utf-8") as f:
        f.write(pd.Series(meta).to_json(force_ascii=False, indent=2))
    return meta, form_url

def read_meta(event_id: str) -> dict:
    mpath = meta_path(event_id)
    if os.path.exists(mpath):
        try:
            import json
            with open(mpath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"id": event_id, "title": "", "date": "", "location": ""}

def list_events():
    items = []
    for fn in os.listdir(DATA_DIR):
        if fn.endswith("_meta.json"):
            try:
                import json
                with open(os.path.join(DATA_DIR, fn), "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    items.append(meta)
            except Exception:
                pass
    # sort by created_at desc
    items.sort(key=lambda m: m.get("created_at",""), reverse=True)
    return items

def load_logo():
    path = os.path.join(os.path.dirname(__file__), LOGO_FILENAME)
    if os.path.exists(path):
        try:
            img = Image.open(path)
            return img
        except Exception:
            return None
    return None

# ---------- Query Params ----------
qp = st.experimental_get_query_params()
event_id = qp.get("event", [None])[0]
mode = qp.get("mode", [""])[0]
admin_key = qp.get("key", [""])[0]

# ---------- Header with Logo ----------
logo = load_logo()
header_col_logo, header_col_title = st.columns([1, 9])
with header_col_logo:
    if logo is not None:
        st.image(logo, caption=None, use_column_width=True)
with header_col_title:
    st.title(APP_TITLE)

st.markdown("---")

# ---------- Home / Create Event ----------
if not event_id and not mode:
    with st.expander("ℹ️ So funktioniert's", expanded=False):
        st.markdown("""
        **Ablauf**  
        1) Unten neuen Termin anlegen (Titel, Datum, Ort).  
        2) QR-Code scannen/ausdrucken – führt direkt zum Formular.  
        3) Teilnehmende tragen sich ein (Pflichtfelder: Veranstaltung, Name, Unternehmen, Fotoeinverständnis).  
        4) In der Admin-Ansicht siehst du alles live, exportierst CSV/XLSX und setzt bei Bedarf für den nächsten Termin zurück.
        """)

    st.subheader("Neuen Termin anlegen")
    with st.form("create_event"):
        c1, c2, c3 = st.columns(3)
        title = c1.text_input("Titel", value="Teilnehmerliste Feuerwehr Nordhorn Förderverein")
        date = c2.text_input("Datum", value=datetime.now().strftime("%d.%m.%Y"))
        location = c3.text_input("Ort", value="Wache Nord")
        submitted = st.form_submit_button("Termin erstellen")
        if submitted:
            meta, form_url = new_event(title, date, location)
            st.success(f"Termin erstellt: {meta['title']} ({meta['date']}, {meta['location']})")
            st.markdown(f"**Formular-Link (relativ):** `{form_url}`")
            st.image(qr_path(meta["id"]), caption="QR-Code zum Formular (einfach ausdrucken)")
            st.stop()

    st.subheader("Vorhandene Termine")
    evts = list_events()
    if not evts:
        st.info("Noch keine Termine angelegt.")
    else:
        for meta in evts:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3,2,2,3])
                c1.markdown(f"**{meta.get('title','')}**  \n{meta.get('date','')} · {meta.get('location','')}")
                eid = meta["id"]
                c2.code(f"?event={eid}&mode=form", language="text")
                c3.code(f"?event={eid}&mode=admin&key=DEIN_ADMIN_KEY", language="text")
                qr_file = qr_path(eid)
                if os.path.exists(qr_file):
                    c4.image(qr_file, caption="QR (Formular)")
    st.stop()

# ---------- Public Form ----------
if event_id and mode == "form":
    st.header("Anmeldung")

    df = load_event_df(event_id)

    with st.form("signup"):
        event_type = st.selectbox("Veranstaltung*", options=["Brandschutzhelfer-Seminar", "Feuerlöschtraining"])
        c1, c2 = st.columns(2)
        name = c1.text_input("Name*", placeholder="Max Muster")
        company = c2.text_input("Unternehmen / Betrieb*", placeholder="Firma / Einrichtung")
        photo_consent = st.selectbox("Einverständnis für eventuelle Fotos*", options=["Ja", "Nein"])
        submit = st.form_submit_button("Eintragen")

        if submit:
            errors = []
            if not event_type:
                errors.append("Bitte Veranstaltung wählen.")
            if not name.strip():
                errors.append("Bitte Namen angeben.")
            if not company.strip():
                errors.append("Bitte Unternehmen/Betrieb angeben.")
            if not photo_consent:
                errors.append("Bitte Foto-Einverständnis wählen.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                now = datetime.now()
                new_row = {
                    "event_type": event_type,
                    "timestamp": now.isoformat(timespec="seconds"),
                    "date": now.strftime("%d.%m.%Y"),
                    "name": name.strip(),
                    "company": company.strip(),
                    "photo_consent": photo_consent
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_event_df(event_id, df)
                st.success("Danke! Deine Anmeldung wurde gespeichert.")
                st.experimental_set_query_params(event=event_id, mode="form")
                st.stop()

    st.info("Du kannst dieses Fenster schließen oder weitere Personen eintragen.")
    st.stop()

# ---------- Admin View ----------
if event_id and mode == "admin":
    if admin_key != ADMIN_KEY:
        st.error("Kein Zugriff: Falsches oder fehlendes Admin-Passwort.")
        st.stop()

    meta = read_meta(event_id)
    st.header(f"Admin · {meta.get('title','')} – {meta.get('date','')} @ {meta.get('location','')}")

    # Show QR + link
    c1, c2 = st.columns([1,2])
    qr_file = qr_path(event_id)
    with c1:
        if os.path.exists(qr_file):
            st.image(qr_file, caption="QR-Code (Formular)")
        st.code(f"?event={event_id}&mode=form", language="text")

    df = load_event_df(event_id)
    st.metric("Anzahl Einträge", len(df))
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Export
    exp_c1, exp_c2 = st.columns(2)
    with exp_c1:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ CSV exportieren", data=csv_bytes, file_name=f"teilnehmer_{event_id}.csv", mime="text/csv")
    with exp_c2:
        xlsx_bytes = export_xlsx_bytes(df)
        st.download_button("⬇️ XLSX exportieren", data=xlsx_bytes, file_name=f"teilnehmer_{event_id}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Reset
    st.warning("Zurücksetzen leert diese Teilnehmerliste unwiderruflich.")
    if st.button("🔁 Liste zurücksetzen"):
        save_event_df(event_id, load_event_df(event_id).iloc[0:0])
        st.success("Liste zurückgesetzt.")

    st.stop()
