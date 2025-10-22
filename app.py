import os
import uuid
import io
import json
import re
from datetime import datetime

import pandas as pd
import streamlit as st
from PIL import Image
import qrcode
from dotenv import load_dotenv

# ---------- Konfiguration ----------
load_dotenv()
st.set_page_config(page_title="Teilnehmerliste Feuerwehr Nordhorn Förderverein",
                   page_icon="🧯",
                   layout="centered")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

ADMIN_KEY = os.getenv("ADMIN_KEY", "112")
LOGO_FILENAME = os.getenv("LOGO_FILE", "Logo Förderverein.jpg")
BASE_URL = os.getenv("BASE_URL", "https://teilnehmerliste.streamlit.app").rstrip("/")

APP_TITLE = "🧯 Teilnehmerliste Feuerwehr Nordhorn Förderverein"

# ---------- Hilfsfunktionen ----------
def event_path(event_id: str) -> str:
    return os.path.join(DATA_DIR, f"{event_id}.csv")

def qr_path(event_id: str) -> str:
    return os.path.join(DATA_DIR, f"{event_id}_qr.png")

def meta_path(event_id: str) -> str:
    return os.path.join(DATA_DIR, f"{event_id}_meta.json")

def load_event_df(event_id: str) -> pd.DataFrame:
    p = event_path(event_id)
    if os.path.exists(p):
        return pd.read_csv(p)
    return pd.DataFrame(columns=["event_type","timestamp","date","name","company","photo_consent"])

def save_event_df(event_id: str, df: pd.DataFrame):
    df.to_csv(event_path(event_id), index=False)

def export_xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        df.to_excel(xw, index=False, sheet_name="Teilnehmer")
    buf.seek(0)
    return buf.read()

def make_qr_png_bytes(text: str) -> bytes:
    # robuster QR für Kamerascans (iPhone): hohe Fehlerkorrektur, größere Module, Rand
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=8,
        border=3
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()

def regenerate_qr_for_event(eid: str, base_url: str):
    # Option 2: immer über /index.html?… (Safari-kompatibel) + Cache-Buster
    full_form = f"{base_url.rstrip('/')}/index.html?event={eid}&mode=form&v={eid}"
    with open(qr_path(eid), "wb") as f:
        f.write(make_qr_png_bytes(full_form))
    return full_form

def new_event(title: str, date: str, location: str, event_type: str):
    event_id = uuid.uuid4().hex[:10]
    meta = {
        "id": event_id,
        "title": title.strip(),
        "date": date.strip(),
        "location": location.strip(),
        "event_type": event_type.strip(),
        "created_at": datetime.now().isoformat(timespec="seconds")
    }
    # CSV anlegen
    save_event_df(event_id, load_event_df(event_id))

    # Option 2: absolute URL via /index.html?  (+ Cache-Buster)
    full_form = f"{BASE_URL.rstrip('/')}/index.html?event={event_id}&mode=form&v={event_id}"

    # QR speichern
    with open(qr_path(event_id), "wb") as f:
        f.write(make_qr_png_bytes(full_form))

    # Meta speichern
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
            try:
                with open(os.path.join(DATA_DIR, fn), "r", encoding="utf-8") as f:
                    items.append(json.load(f))
            except Exception:
                pass
    items.sort(key=lambda m: m.get("created_at",""), reverse=True)
    return items

def load_logo():
    p = os.path.join(os.path.dirname(__file__), LOGO_FILENAME)
    if os.path.exists(p):
        try:
            return Image.open(p)
        except Exception:
            return None
    return None

# ---------- Query-Parameter (robust mit iPhone-Fix) ----------
# Neuer Weg
try:
    qp_new = dict(st.query_params)
except Exception:
    qp_new = {}
# Fallback
try:
    qp_old = st.experimental_get_query_params()
except Exception:
    qp_old = {}

def _pick_param(name, default=None):
    if name in qp_new and qp_new.get(name) not in (None, "", []):
        return qp_new.get(name)
    v = qp_old.get(name, [None])
    return (v[0] if isinstance(v, list) else v) or default

event_id = _pick_param("event", None)
mode = _pick_param("mode", "")
admin_key = _pick_param("key", "")
noredirect = _pick_param("noredirect", "")

# iPhone/Safari: Parameter aus Referer rekonstruieren, wenn leer
if not event_id:
    try:
        import streamlit.web.server.websocket_headers as ws_headers
        headers = ws_headers.get_websocket_headers()
        referer = headers.get("referer", "") if headers else ""
    except Exception:
        referer = ""
    m_e = re.search(r"[?&]event=([a-zA-Z0-9]+)", referer)
    m_m = re.search(r"[?&]mode=([a-zA-Z]+)", referer)
    if m_e:
        event_id = m_e.group(1)
        mode = m_m.group(1) if m_m else "form"
        st.query_params.update({"event": event_id, "mode": mode})
        st.toast("📱 Safari-Fix aktiv …")
        st.rerun()

# Debug (später entfernbar)
st.caption(f"🔍 DBG → event={event_id} | mode={mode} | key={admin_key}")

# ---------- Kopfbereich ----------
logo = load_logo()
c_logo, c_title = st.columns([1,9])
with c_logo:
    if logo is not None:
        st.image(logo, use_column_width=True)
with c_title:
    st.title(APP_TITLE)
st.markdown("---")

# ---------- Auto-Redirect (Option 3) ----------
# Wenn ohne Parameter geöffnet wurde, leite auf den neuesten Termin (Formular) um,
# außer der Nutzer setzt ?noredirect=1 oder ruft explizit eine Admin-/Home-Ansicht auf.
if not event_id and not mode and not noredirect:
    evts = list_events()
    if evts:
        latest = evts[0]["id"]
        st.query_params.update({"event": latest, "mode": "form"})
        st.toast("↪️ Automatische Weiterleitung zum aktuellen Formular …")
        st.rerun()

# ---------- Startseite ----------
if not event_id and not mode:
    with st.expander("ℹ️ So funktioniert's", expanded=False):
        st.markdown("""
        **Ablauf:**  
        1️⃣ Termin anlegen (Titel, Datum, Ort, Typ).  
        2️⃣ QR-Code scannen oder Link nutzen – direkt zum Formular.  
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
            st.image(qr_path(meta['id']), caption="📱 QR-Code zum Formular")
            st.link_button("📱 Formular direkt öffnen", full_form)
            st.write("Direktlink:", full_form)
            st.stop()

    st.subheader("Vorhandene Termine")
    evts = list_events()
    if not evts:
        st.info("Noch keine Termine angelegt.")
    else:
        for meta in evts:
            eid = meta["id"]
            c1, c2, c3, c4 = st.columns([3,2,2,3])
            etype = meta.get("event_type", "")
            c1.markdown(f"**{meta.get('title','')}**  \n{meta.get('date','')} · {meta.get('location','')}")
            if etype:
                c1.markdown(f"*{etype}*")
            # absolute, iPhone-sichere Links via /index.html?
            form_link = f"{BASE_URL}/index.html?event={eid}&mode=form&v={eid}"
            admin_link = f"{BASE_URL}/index.html?event={eid}&mode=admin&key=112"
            c2.code(form_link)
            c3.code(admin_link)
            if os.path.exists(qr_path(eid)):
                c4.image(qr_path(eid), caption="QR (Formular)")
            st.link_button("📱 Formular direkt öffnen", form_link)
            st.write("Direktlink:", form_link)
    st.stop()

# ---------- Formular ----------
if event_id and mode == "form":
    st.header("📋 Anmeldung")
    df = load_event_df(event_id)
    meta = read_meta(event_id)
    pretype = (meta.get("event_type","") or "Feuerlöschtraining").strip()
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
                row = {
                    "event_type": pretype,
                    "timestamp": now.isoformat(timespec="seconds"),
                    "date": now.strftime("%d.%m.%Y"),
                    "name": name.strip(),
                    "company": company.strip(),
                    "photo_consent": photo_consent
                }
                df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
                save_event_df(event_id, df)
                st.success("✅ Danke! Deine Anmeldung wurde gespeichert.")
                # neue API: Query-Params beibehalten
                st.query_params.update({"event": event_id, "mode": "form"})
                st.balloons()
                st.stop()
    st.stop()

# ---------- Admin (Übersicht über alle Termine) ----------
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
        etype = meta.get("event_type","")
        label = f" · {etype}" if etype else ""
        st.markdown(f"### {meta.get('title','(ohne Titel)')}{label} – {meta.get('date','')} · {meta.get('location','')}")

        # QR + Direktlink anzeigen
        form_link = f"{BASE_URL}/index.html?event={eid}&mode=form&v={eid}"
        if os.path.exists(qr_path(eid)):
            st.image(qr_path(eid), width=160, caption="QR-Code (Formular)")
        st.link_button("📱 Formular direkt öffnen", form_link)
        st.code(form_link)

        # Tabelle + Exporte
        df = load_event_df(eid)
        st.metric("Anzahl Einträge", len(df))
        st.dataframe(df, use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("⬇️ CSV exportieren",
                               data=df.to_csv(index=False).encode("utf-8"),
                               file_name=f"teilnehmer_{eid}.csv",
                               mime="text/csv",
                               key=f"csv_{eid}")
        with c2:
            st.download_button("⬇️ XLSX exportieren",
                               data=export_xlsx_bytes(df),
                               file_name=f"teilnehmer_{eid}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key=f"xlsx_{eid}")

        # QR neu erzeugen (falls alte PNGs noch ohne /index.html?)
        r1, r2 = st.columns([1,3])
        with r1:
            if st.button("🔄 QR neu erzeugen", key=f"regen_{eid}"):
                new_url = regenerate_qr_for_event(eid, BASE_URL)
                st.success(f"QR aktualisiert: {new_url}")
        with r2:
            st.code(form_link)

        st.warning("Zurücksetzen leert diese Teilnehmerliste unwiderruflich.")
        if st.button("🔁 Liste zurücksetzen", key=f"reset_{eid}"):
            save_event_df(eid, load_event_df(eid).iloc[0:0])
            st.success(f"Liste {meta.get('title','')} zurückgesetzt.")
        st.divider()

    st.stop()

