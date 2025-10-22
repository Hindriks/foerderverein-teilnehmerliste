import os
import io
import json
import re
import uuid
from datetime import datetime

import pandas as pd
import streamlit as st
from PIL import Image
import qrcode
from dotenv import load_dotenv

# =========================
#   GRUNDEINSTELLUNGEN
# =========================
load_dotenv()
st.set_page_config(
    page_title="Teilnehmerliste Feuerwehr Nordhorn Förderverein",
    page_icon="🧯",
    layout="centered"
)

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

ADMIN_KEY = os.getenv("ADMIN_KEY", "112")
LOGO_FILENAME = os.getenv("LOGO_FILE", "Logo Förderverein.jpg") or ""  # leer = Logo aus
BASE_URL = os.getenv("BASE_URL", "https://teilnehmerliste.streamlit.app").rstrip("/")

APP_TITLE = "🧯 Teilnehmerliste Feuerwehr Nordhorn Förderverein"

# =========================
#   ULTRA-ROBUSTER REDIRECT (/index.html)
# =========================
# Wenn URL ?event=... enthält, aber Pfad nicht /index.html, sofort clientseitig weiterleiten.
st.markdown("""
<script>
(function () {
  try {
    var url = new URL(window.location.href);
    var hasEvent = url.searchParams.has('event');
    var onIndex = url.pathname.toLowerCase().includes('index.html');
    if (hasEvent && !onIndex) {
      var basePath = url.pathname;
      if (!basePath.endsWith('/')) basePath += '/';
      var target = url.origin + basePath + 'index.html' + url.search;
      window.location.replace(target);
    }
  } catch (e) { /* noop */ }
})();
</script>
""", unsafe_allow_html=True)

# =========================
#   DATEI-HILFSFUNKTIONEN
# =========================
def event_path(event_id: str) -> str:
    return os.path.join(DATA_DIR, f"{event_id}.csv")

def qr_path(event_id: str) -> str:
    return os.path.join(DATA_DIR, f"{event_id}_qr.png")

def meta_path(event_id: str) -> str:
    return os.path.join(DATA_DIR, f"{event_id}_meta.json")

def load_event_df(event_id: str) -> pd.DataFrame:
    p = event_path(event_id)
    if os.path.exists(p):
        try:
            return pd.read_csv(p)
        except Exception:
            pass
    return pd.DataFrame(columns=["event_type", "timestamp", "date", "name", "company", "photo_consent"])

def save_event_df(event_id: str, df: pd.DataFrame):
    df.to_csv(event_path(event_id), index=False)

def export_xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        df.to_excel(xw, index=False, sheet_name="Teilnehmer")
    buf.seek(0)
    return buf.read()

def load_logo():
    if not LOGO_FILENAME:
        return None
    p = os.path.join(BASE_DIR, LOGO_FILENAME)
    if os.path.exists(p):
        try:
            return Image.open(p)
        except Exception:
            return None
    return None

# =========================
#   QR-CODE & LINKS
# =========================
def make_qr_png_bytes(text: str) -> bytes:
    # robust für Handy-Scanner (iPhone/Safari): hohe Fehlerkorrektur, größere Module, Rand
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

def form_link_for(eid: str) -> str:
    # iPhone-sicher: Query UND Hash doppelt setzen, plus Cache-Buster.
    # Wenn Safari die Query abschneidet, holt das JS sie aus dem Hash zurück.
    query = f"event={eid}&mode=form&v={eid}"
    return f"{BASE_URL}/index.html?{query}#{query}"


def admin_link_for(eid: str) -> str:
    return f"{BASE_URL}/index.html?event={eid}&mode=admin&key={ADMIN_KEY}"

def regenerate_qr_for_event(eid: str) -> str:
    link = form_link_for(eid)
    with open(qr_path(eid), "wb") as f:
        f.write(make_qr_png_bytes(link))
    return link

# =========================
#   EVENT-METADATEN
# =========================
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
    # QR generieren (iPhone-sicherer Link)
    link = form_link_for(event_id)
    with open(qr_path(event_id), "wb") as f:
        f.write(make_qr_png_bytes(link))
    # Meta speichern
    with open(meta_path(event_id), "w", encoding="utf-8") as f:
        f.write(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta, link

def read_meta(event_id: str) -> dict:
    p = meta_path(event_id)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"id": event_id, "title": "", "date": "", "location": "", "event_type": ""}

def list_events():
    items = []
    for fn in os.listdir(DATA_DIR):
        if fn.endswith("_meta.json"):
            try:
                with open(os.path.join(DATA_DIR, fn), "r", encoding="utf-8") as f:
                    items.append(json.load(f))
            except Exception:
                pass
    items.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return items

# =========================
#   QUERY-PARAMS (nur neue API) + SAFARI-Fallback
# =========================
# =========================
#   QUERY-PARAMS (nur neue API) + SAFARI-Fallback
# =========================
qp = dict(st.query_params)

event_id   = qp.get("event", None)
mode       = qp.get("mode", "")
admin_key  = qp.get("key", "")
noredirect = qp.get("noredirect", "")

# Safari-Fallback: wenn keine Params direkt übergeben wurden (z. B. iPhone-Kamera)
if not event_id:
    try:
        from streamlit.web.server.websocket_headers import get_websocket_headers
        referer = (get_websocket_headers() or {}).get("referer", "")
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

# 🔎 Sicht-Check: zeigt an, was wirklich ankommt
st.caption(f"🔎 Status: event={event_id} | mode={mode}")

# Zusätzlicher Fallback: wenn Event da, aber Mode fehlt oder anders ist → immer Formular
if event_id and mode != "form":
    st.query_params.update({"event": event_id, "mode": "form"})
    st.rerun()


# =========================
#   HEADER
# =========================
logo = load_logo()
col_logo, col_title = st.columns([1, 9])
with col_logo:
    if logo is not None:
        st.image(logo, use_column_width=True)
with col_title:
    st.title(APP_TITLE)
st.markdown("---")

# =========================
#   AUTO-REDIRECT HOME → letzter Termin (nur ohne Params)
# =========================
if not event_id and not mode and not noredirect:
    evts = list_events()
    if evts:
        latest = evts[0]["id"]
        st.query_params.update({"event": latest, "mode": "form"})
        st.toast("↪️ Weiterleitung zum aktuellen Formular …")
        st.rerun()

# =========================
#   STARTSEITE (nur ohne Params)
# =========================
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
            meta, link = new_event(title, date, location, event_type)
            st.success(f"✅ Termin erstellt: {meta['title']} ({meta['date']}, {meta['location']}) – {meta['event_type']}")
            st.markdown(f"**Formular-Link:** `{link}`")
            st.image(qr_path(meta['id']), caption="📱 QR-Code zum Formular")
            st.link_button("📱 Formular direkt öffnen", link)
            st.write("Direktlink:", link)
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
            form_url = form_link_for(eid)
            admin_url = admin_link_for(eid)
            c2.code(form_url)
            c3.code(admin_url)
            if os.path.exists(qr_path(eid)):
                c4.image(qr_path(eid), caption="QR (Formular)")
            st.link_button("📱 Formular direkt öffnen", form_url)
            st.write("Direktlink:", form_url)
    st.stop()

# =========================
#   FORMULAR
# =========================
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
                st.query_params.update({"event": event_id, "mode": "form"})
                st.balloons()
                st.stop()
    st.stop()

# =========================
#   ADMIN (ÜBERSICHT)
# =========================
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

        form_url = form_link_for(eid)
        if os.path.exists(qr_path(eid)):
            st.image(qr_path(eid), width=160, caption="QR-Code (Formular)")
        st.link_button("📱 Formular direkt öffnen", form_url)
        st.code(form_url)

        df = load_event_df(eid)
        st.metric("Anzahl Einträge", len(df))
        st.dataframe(df, use_container_width=True, hide_index=True)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "⬇️ CSV exportieren",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name=f"teilnehmer_{eid}.csv",
                mime="text/csv",
                key=f"csv_{eid}"
            )
        with c2:
            st.download_button(
                "⬇️ XLSX exportieren",
                data=export_xlsx_bytes(df),
                file_name=f"teilnehmer_{eid}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"xlsx_{eid}"
            )

        rc1, rc2 = st.columns([1, 3])
        with rc1:
            if st.button("🔄 QR neu erzeugen", key=f"regen_{eid}"):
                new_url = regenerate_qr_for_event(eid)
                st.success(f"QR aktualisiert: {new_url}")
        with rc2:
            st.code(form_url)

        st.warning("Zurücksetzen leert diese Teilnehmerliste unwiderruflich.")
        if st.button("🔁 Liste zurücksetzen", key=f"reset_{eid}"):
            save_event_df(eid, load_event_df(eid).iloc[0:0])
            st.success(f"Liste {meta.get('title','')} zurückgesetzt.")

        st.divider()

    st.stop()
