import os
import uuid
import io
import json
from datetime import datetime
import pandas as pd
import streamlit as st
from PIL import Image
import qrcode
from dotenv import load_dotenv

# ---------- Konfiguration ----------
load_dotenv()
st.set_page_config(page_title="Teilnehmerliste Feuerwehr Nordhorn Förderverein", page_icon="🧯", layout="centered")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

ADMIN_KEY = os.getenv("ADMIN_KEY", "112")
LOGO_FILENAME = os.getenv("LOGO_FILE", "Logo Förderverein.jpg")
BASE_URL = (os.getenv("BASE_URL", "https://teilnehmerliste.streamlit.app").rstrip("/") + "/")

APP_TITLE = "🧯 Teilnehmerliste Feuerwehr Nordhorn Förderverein"

# ---------- Hilfsfunktionen ----------
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
    return pd.DataFrame(columns=["event_type", "timestamp", "date", "name", "company", "photo_consent"])

def save_event_df(event_id: str, df: pd.DataFrame):
    df.to_csv(event_path(event_id), index=False)

def export_xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Teilnehmer")
    buf.seek(0)
    return buf.read()

def make_qr_png_bytes(text: str) -> bytes:
    # Robuster QR für Handy-Scanner: hohe Fehlerkorrektur, größere Module, klarer Rand
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # höher = robuster
        box_size=8,   # größer = leichter scannbar (8–10 ist gut für Displays)
        border=3      # weißer Rand (2–4)
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()


def regenerate_qr_for_event(eid: str, base_url: str):
    """Erzeugt den QR-Code eines bestehenden Events neu – mit korrekter absoluter URL"""
    full_form = f"{base_url.rstrip('/')}/?event={eid}&mode=form&v={eid}"
    png = make_qr_png_bytes(full_form)
    with open(qr_path(eid), "wb") as f:
        f.write(png)
    return full_form

def new_event(title: str, date: str, location: str, event_type: str):
    """Legt ein neues Event an und erzeugt QR-Code mit absoluter URL"""
    event_id = uuid.uuid4().hex[:10]
    meta = {
        "id": event_id,
        "title": title.strip(),
        "date": date.strip(),
        "location": location.strip(),
        "event_type": event_type.strip(),
        "created_at": datetime.now().isoformat(timespec="seconds")
    }

    save_event_df(event_id, load_event_df(event_id))
    full_form = f"{BASE_URL.rstrip('/')}/?event={event_id}&mode=form&v={event_id}"
    qr_png = make_qr_png_bytes(full_form)
    with open(qr_path(event_id), "wb") as f:
        f.write(qr_png)
    with open(meta_path(event_id), "w", encoding="utf-8") as f:
        f.write(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta, full_form

def read_meta(event_id: str) -> dict:
    try:
        with open(meta_path(event_id), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"id": event_id, "title": "", "date": "", "location": ""}

def list_events():
    items = []
    for fn in os.listdir(DATA_DIR):
        if fn.endswith("_meta.json"):
            with open(os.path.join(DATA_DIR, fn), "r", encoding="utf-8") as f:
                try:
                    meta = json.load(f)
                    items.append(meta)
                except Exception:
                    pass
    items.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return items

def load_logo():
    path = os.path.join(os.path.dirname(__file__), LOGO_FILENAME)
    if os.path.exists(path):
        try:
            return Image.open(path)
        except Exception:
            return None
    return None

# ---------- Query-Parameter ----------
qp = st.experimental_get_query_params()
event_id = qp.get("event", [None])[0]
mode = qp.get("mode", [""])[0]
admin_key = qp.get("key", [""])[0]

# ---------- Kopfbereich ----------
logo = load_logo()
header_col_logo, header_col_title = st.columns([1, 9])
with header_col_logo:
    if logo is not None:
        st.image(logo, caption=None, use_column_width=True)
with header_col_title:
    st.title(APP_TITLE)

st.markdown("---")

# ---------- Startseite ----------
if not event_id and not mode:
    with st.expander("ℹ️ So funktioniert's", expanded=False):
        st.markdown("""
        **Ablauf:**  
        1️⃣ Termin anlegen (Titel, Datum, Ort, Typ).  
        2️⃣ QR-Code scannen oder drucken – führt direkt zum Formular.  
        3️⃣ Teilnehmende tragen sich ein (Pflichtfelder).  
        4️⃣ Admin sieht alles live und kann exportieren.
        """)

st.subheader("Neuen Termin anlegen")
with st.form("create_event"):
    c1, c2, c3 = st.columns(3)
    title = c1.text_input("Titel", value="Teilnehmerliste Feuerwehr Nordhorn Förderverein")
    date = c2.text_input("Datum", value=datetime.now().strftime("%d.%m.%Y"))
    location = c3.text_input("Ort", value="Wache Nord")
    event_type = st.selectbox("Veranstaltung*", ["Brandschutzhelfer-Seminar", "Feuerlöschtraining"])
    submitted = st.form_submit_button("Termin erstellen")
    if submitted:
        meta, full_form = new_event(title, date, location, event_type)
        st.success(f"✅ Termin erstellt: {meta['title']} ({meta['date']}, {meta['location']}) – {meta['event_type']}")
        st.markdown(f"**Formular-Link:** `{full_form}`")

        # QR-Code anzeigen
        st.image(qr_path(meta['id']), caption="📱 QR-Code zum Formular (einfach scannen oder ausdrucken)")

        # 👇 Neu: klickbarer Button + Direktlink für Handy
        st.link_button("📱 Formular direkt öffnen", full_form)
        st.write("Direktlink:", full_form)

        # Nach dem Anlegen hier stoppen, damit der Bereich unten nicht sofort rendert
        st.stop()

st.subheader("Vorhandene Termine")
evts = list_events()
if not evts:
    st.info("Noch keine Termine angelegt.")
else:
    for meta in evts:
        eid = meta["id"]
        c1, c2, c3, c4 = st.columns([3, 2, 2, 3])

        etype = meta.get("event_type", "")
        c1.markdown(f"**{meta.get('title','')}**  \n{meta.get('date','')} · {meta.get('location','')}")
        if etype:
            c1.markdown(f"*{etype}*")

        # Codes mit absoluter URL
        c2.code(f"{BASE_URL.rstrip('/')}/?event={eid}&mode=form")
        c3.code(f"{BASE_URL.rstrip('/')}/?event={eid}&mode=admin&key=112")

        # QR + Button + Direktlink (alles innerhalb der Schleife!)
        if os.path.exists(qr_path(eid)):
            c4.image(qr_path(eid), caption="QR (Formular)")
        direct = f"{BASE_URL.rstrip('/')}/?event={eid}&mode=form&v={eid}"
        st.link_button("📱 Formular direkt öffnen", direct, key=f"open_{eid}")
        st.write("Direktlink:", direct)

st.stop()

# ---------- Formular ----------
if event_id and mode == "form":
    st.header("📋 Anmeldung")
    df = load_event_df(event_id)
    meta = read_meta(event_id)
    pretype = (meta.get("event_type", "") or "Feuerlöschtraining").strip()
    st.info(f"Veranstaltung: **{pretype}**")

    with st.form("signup"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name*", placeholder="Max Muster")
        company = c2.text_input("Unternehmen / Betrieb*", placeholder="Firma / Einrichtung")
        photo_consent = st.selectbox("Einverständnis für eventuelle Fotos*", ["Ja", "Nein"])
        submit = st.form_submit_button("Eintragen")

        if submit:
            if not name.strip() or not company.strip():
                st.error("Bitte alle Pflichtfelder ausfüllen.")
            else:
                now = datetime.now()
                new_row = {
                    "event_type": pretype,
                    "timestamp": now.isoformat(timespec="seconds"),
                    "date": now.strftime("%d.%m.%Y"),
                    "name": name.strip(),
                    "company": company.strip(),
                    "photo_consent": photo_consent
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_event_df(event_id, df)
                st.success("✅ Danke! Deine Anmeldung wurde gespeichert.")
                st.balloons()
                st.stop()
    st.stop()

# ---------- Admin ----------
if mode == "admin":
    if admin_key != ADMIN_KEY:
        st.error("Kein Zugriff: falsches oder fehlendes Admin-Passwort.")
        st.stop()

    st.header("🧯 Admin-Übersicht – Alle Termine")
    events = list_events()
    if not events:
        st.info("Noch keine Termine angelegt.")
        st.stop()

    for meta in events:
        eid = meta["id"]
        etype = meta.get("event_type", "")
        label = f" · {etype}" if etype else ""
        st.markdown(f"### {meta.get('title','(ohne Titel)')}{label} – {meta.get('date','')} · {meta.get('location','')}")

        qr_file = qr_path(eid)
        if os.path.exists(qr_file):
            st.image(qr_file, width=160, caption="QR-Code (Formular)")
        st.code(f"{BASE_URL}?event={eid}&mode=form")

        df = load_event_df(eid)
        st.metric("Anzahl Einträge", len(df))
        st.dataframe(df, use_container_width=True, hide_index=True)

        exp_c1, exp_c2 = st.columns(2)
        with exp_c1:
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ CSV exportieren",
                               data=csv_bytes,
                               file_name=f"teilnehmer_{eid}.csv",
                               mime="text/csv",
                               key=f"csv_{eid}")
        with exp_c2:
            xlsx_bytes = export_xlsx_bytes(df)
            st.download_button("⬇️ XLSX exportieren",
                               data=xlsx_bytes,
                               file_name=f"teilnehmer_{eid}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key=f"xlsx_{eid}")

        regen_c1, regen_c2 = st.columns([1, 3])
        with regen_c1:
            if st.button("🔄 QR neu erzeugen", key=f"regen_{eid}"):
                new_url = regenerate_qr_for_event(eid, BASE_URL)
                st.success(f"QR aktualisiert: {new_url}")
        with regen_c2:
            st.code(f"{BASE_URL}?event={eid}&mode=form")

        st.warning("Zurücksetzen leert diese Teilnehmerliste unwiderruflich.")
        if st.button("🔁 Liste zurücksetzen", key=f"reset_{eid}"):
            save_event_df(eid, load_event_df(eid).iloc[0:0])
            st.success(f"Liste {meta.get('title','')} zurückgesetzt.")
        st.divider()

    st.stop()
