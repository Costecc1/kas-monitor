"""
KAS Licytacje Monitor
Monitoruje ogłoszenia o sprzedaży z wolnej ręki na stronach KAS dla 16 województw.
Wysyła powiadomienia przez Telegram Bot.
"""

import os
import json
import time
import logging
import hashlib
import re
import requests
import schedule
import pdfplumber
import io
from datetime import datetime
from bs4 import BeautifulSoup

# ─── Konfiguracja Telegram ────────────────────────────────────────────────────

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "8876309250:AAE70jaq_V3gWzaN0JZlAdT-7NMYTmDw_pk")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8860913860")

CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL", "1"))
SEEN_FILE = "seen_listings.json"

# ─── Słowa kluczowe wolnej ręki (filtr ogłoszeń) ──────────────────────────────

WOLNA_REKA_KEYWORDS = [
    "wolnej ręki", "wolna ręka", "wolnej reki", "wolna reka",
    "sprzedaż z wolnej", "sprzedazy z wolnej",
    "zawiadomienie o sprzedaży z wolnej",
]

# ─── Słowa kluczowe PDF z dopiskami do powiadomienia ─────────────────────────
#
# Format każdego wpisu:
#   {
#     "keywords": ["słowo1", "słowo2", ...],   # szukane w treści PDF (OR)
#     "label":    "Krótki opis",               # wyświetlany w nagłówku
#     "note":     "Dopisek w powiadomieniu",   # dodatkowa informacja dla użytkownika
#     "emoji":    "💳",                        # emoji przed etykietą
#   }
#
# Żeby dodać nowe słowo kluczowe — dopisz kolejny słownik do listy poniżej.

PDF_KEYWORD_RULES = [
    {
        "keywords": ["przelew", "przelewem", "wpłata przelewem", "płatność przelewem",
                     "wplata przelewem", "platnosc przelewem"],
        "label":    "PRZELEW",
        "note":     "Ogłoszenie wymaga płatności przelewem — przygotuj dane do przelewu przed kontaktem.",
        "emoji":    "💳",
    } #,
    # {
        # "keywords": ["kolejność zgłoszeń", "kolejnosc zgloszen",
                     # "kolejności zgłoszeń", "kolejnosci zgloszen",
                     # "kolejność ofert", "pierwszeństwo", "pierwszenstwo"],
        # "label":    "KOLEJNOŚĆ ZGŁOSZEŃ",
        # "note":     "Sprzedaż wg kolejności zgłoszeń — działaj szybko i zgłoś się jako pierwszy!",
        # "emoji":    "📋",
    # },
    # ── Tutaj możesz dodawać kolejne reguły, np.: ────────────────────────────
    # {
    #     "keywords": ["negocjacje", "do negocjacji"],
    #     "label":    "NEGOCJACJE",
    #     "note":     "Cena do negocjacji.",
    #     "emoji":    "🤝",
    # },
    # {
    #     "keywords": ["nieruchomość", "nieruchomosc", "lokal", "grunt", "działka"],
    #     "label":    "NIERUCHOMOŚĆ",
    #     "note":     "Dotyczy nieruchomości — sprawdź KW i stan prawny.",
    #     "emoji":    "🏠",
    # },
]

# ─── Strony 16 województw ─────────────────────────────────────────────────────

VOIVODESHIP_URLS = {
    "Dolnośląskie":        "https://www.dolnoslaskie.kas.gov.pl/izba-administracji-skarbowej-we-wroclawiu/ogloszenia/obwieszczenia-o-licytacjach",
    "Kujawsko-Pomorskie":  "https://www.kujawsko-pomorskie.kas.gov.pl/izba-administracji-skarbowej-w-bydgoszczy/ogloszenia/obwieszczenia-o-licytacjach",
    "Lubelskie":           "https://www.lubelskie.kas.gov.pl/izba-administracji-skarbowej-w-lublinie/ogloszenia/obwieszczenia-o-licytacjach",
    "Lubuskie":            "https://www.lubuskie.kas.gov.pl/izba-administracji-skarbowej-w-zielonej-gorze/ogloszenia/obwieszczenia-o-licytacjach",
    "Łódzkie":             "https://www.lodzkie.kas.gov.pl/izba-administracji-skarbowej-w-lodzi/ogloszenia/obwieszczenia-o-licytacjach",
    "Małopolskie":         "https://www.malopolskie.kas.gov.pl/izba-administracji-skarbowej-w-krakowie/ogloszenia/obwieszczenia-o-licytacjach",
    "Mazowieckie":         "https://www.mazowieckie.kas.gov.pl/izba-administracji-skarbowej-w-warszawie/ogloszenia/obwieszczenia-o-licytacjach",
    "Opolskie":            "https://www.opolskie.kas.gov.pl/izba-administracji-skarbowej-w-opolu/ogloszenia/obwieszczenia-o-licytacjach",
    "Podkarpackie":        "https://www.podkarpackie.kas.gov.pl/izba-administracji-skarbowej-w-rzeszowie/ogloszenia/obwieszczenia-o-licytacjach",
    "Podlaskie":           "https://www.podlaskie.kas.gov.pl/izba-administracji-skarbowej-w-bialymstoku/ogloszenia/obwieszczenia-o-licytacjach",
    "Pomorskie":           "https://www.pomorskie.kas.gov.pl/izba-administracji-skarbowej-w-gdansku/ogloszenia/obwieszczenia-o-licytacjach",
    "Śląskie":             "https://www.slaskie.kas.gov.pl/izba-administracji-skarbowej-w-katowicach/ogloszenia/obwieszczenia-o-licytacjach",
    "Świętokrzyskie":      "https://www.swietokrzyskie.kas.gov.pl/izba-administracji-skarbowej-w-kielcach/ogloszenia/obwieszczenia-o-licytacjach",
    "Warmińsko-Mazurskie": "https://www.warminsko-mazurskie.kas.gov.pl/izba-administracji-skarbowej-w-olsztynie/ogloszenia/obwieszczenia-o-licytacjach",
    "Wielkopolskie":       "https://www.wielkopolskie.kas.gov.pl/izba-administracji-skarbowej-w-poznaniu/ogloszenia/obwieszczenia-o-licytacjach",
    "Zachodniopomorskie":  "https://www.zachodniopomorskie.kas.gov.pl/izba-administracji-skarbowej-w-szczecinie/ogloszenia/obwieszczenia-o-licytacjach",
}

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("monitor.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ─── Persistencja ─────────────────────────────────────────────────────────────

def load_seen() -> dict:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_seen(seen: dict):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)

# ─── Pomocnicze ───────────────────────────────────────────────────────────────

def make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def text_contains(text: str, keywords: list) -> bool:
    t = text.lower()
    return any(kw.lower() in t for kw in keywords)

def is_wolna_reka(title: str) -> bool:
    return text_contains(title, WOLNA_REKA_KEYWORDS)

# ─── PDF analiza ──────────────────────────────────────────────────────────────

def analyze_pdf(pdf_url: str) -> dict:
    """
    Pobiera PDF i sprawdza go pod kątem wszystkich reguł z PDF_KEYWORD_RULES.
    Zwraca listę dopasowanych reguł oraz snippet tekstu.
    """
    result = {"matched_rules": [], "snippet": "", "error": None}
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://www.kas.gov.pl/",
        }
        r = requests.get(pdf_url, headers=headers, timeout=30)
        r.raise_for_status()
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"

        for rule in PDF_KEYWORD_RULES:
            if text_contains(full_text, rule["keywords"]):
                result["matched_rules"].append(rule)

        result["snippet"] = full_text[:500].replace("\n", " ").strip()
    except Exception as e:
        result["error"] = str(e)
        log.warning(f"PDF error ({pdf_url}): {e}")
    return result

# ─── HTTP Session ─────────────────────────────────────────────────────────────

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    })
    return s

# ─── Scraping ─────────────────────────────────────────────────────────────────

def fetch_listings(voivo: str, base_url: str) -> list:
    results = []
    session = make_session()
    try:
        r = session.get(base_url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("h2 a, h3 a")
        for a in items:
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not href:
                continue
            if not href.startswith("http"):
                from urllib.parse import urljoin
                href = urljoin(base_url, href)

            parent = a.find_parent("li") or a.find_parent("div")
            source = ""
            if parent:
                source_tag = parent.find(string=re.compile(r"Źródło:"))
                if source_tag:
                    source = source_tag.strip().replace("Źródło:", "").strip()

            if is_wolna_reka(title):
                results.append({
                    "title": title,
                    "url": href,
                    "clean_id": make_id(href),
                    "voivodeship": voivo,
                    "source": source,
                    "pdf_info": None,
                })
    except Exception as e:
        log.error(f"Błąd pobierania {voivo}: {e}")
    return results

def fetch_pdf_links(listing_url: str) -> list:
    pdfs = []
    session = make_session()
    try:
        r = session.get(listing_url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().endswith(".pdf"):
                if not href.startswith("http"):
                    from urllib.parse import urljoin
                    href = urljoin(listing_url, href)
                pdfs.append(href)
    except Exception as e:
        log.warning(f"Błąd PDF linków z {listing_url}: {e}")
    return pdfs

# ─── Telegram ─────────────────────────────────────────────────────────────────

def send_telegram(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram nie skonfigurowany — pomijam.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        log.info("Telegram wysłany.")
    except Exception as e:
        log.error(f"Błąd Telegram: {e}")

def build_message(listing: dict) -> str:
    pdf = listing.get("pdf_info") or {}
    matched = pdf.get("matched_rules", [])

    source_line = f" · {listing['source']}" if listing.get("source") else ""
    header = (
        f"🏷 <b>WOLNA RĘKA</b> — {listing['voivodeship']}{source_line}\n"
        f"📄 {listing['title']}\n"
        f"🔗 <a href=\"{listing['url']}\">Otwórz ogłoszenie</a>"
    )

    if not matched:
        return header

    # Sekcja dopasowanych słów kluczowych
    details = "\n\n━━━━━━━━━━━━━━━━━━━━"
    for rule in matched:
        details += (
            f"\n{rule['emoji']} <b>{rule['label']}</b>\n"
            f"<i>{rule['note']}</i>"
        )

    return header + details

# ─── Główna pętla ─────────────────────────────────────────────────────────────

def check_all():
    log.info(f"▶ Sprawdzam {len(VOIVODESHIP_URLS)} województw...")
    seen = load_seen()
    new_count = 0

    for voivo, url in VOIVODESHIP_URLS.items():
        listings = fetch_listings(voivo, url)
        log.info(f"  {voivo}: {len(listings)} ogłoszeń z wolnej ręki")

        for item in listings:
            cid = item["clean_id"]
            if cid in seen:
                continue

            # Analiza PDF
            pdf_links = fetch_pdf_links(item["url"])
            if pdf_links:
                item["pdf_info"] = analyze_pdf(pdf_links[0])
                item["pdf_url"]  = pdf_links[0]
            else:
                item["pdf_info"] = {"matched_rules": [], "snippet": ""}
                item["pdf_url"]  = None

            # Powiadomienie Telegram
            msg = build_message(item)
            send_telegram(msg)

            # Zapamiętaj
            matched_labels = [r["label"] for r in item["pdf_info"].get("matched_rules", [])]
            seen[cid] = {
                "title":        item["title"],
                "voivodeship":  item["voivodeship"],
                "url":          item["url"],
                "seen_at":      datetime.now().isoformat(),
                "pdf_matches":  matched_labels,
            }
            new_count += 1
            log.info(f"  ✅ NOWE: {item['title'][:70]}")
            time.sleep(1)

    save_seen(seen)
    log.info(f"▶ Gotowe. Nowych: {new_count}")

# ─── Start ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info(f"🚀 KAS Monitor start — interwał co {CHECK_INTERVAL_MINUTES} min")
    check_all()
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(check_all)
    while True:
        schedule.run_pending()
        time.sleep(30)
