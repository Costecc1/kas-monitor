# KAS Licytacje Monitor 🏷️

Automatyczny monitor ogłoszeń **z wolnej ręki** ze stron KAS dla wszystkich 16 województw.  
Powiadomienia przez **Telegram Bot**.

---

## Szybki start

### 1. Zainstaluj zależności
```bash
pip install -r requirements.txt
```

### 2. Skonfiguruj Telegram (5 minut)

**Krok 1 — utwórz bota:**
- Napisz do [@BotFather](https://t.me/BotFather) na Telegramie
- Wyślij `/newbot`, podaj nazwę i username bota
- BotFather odda Ci **token** w formacie `1234567890:ABCxxx...`

**Krok 2 — znajdź swoje Chat ID:**
- Napisz cokolwiek do swojego nowego bota
- Otwórz w przeglądarce: `https://api.telegram.org/bot<TWÓJ_TOKEN>/getUpdates`
- Znajdź `"chat":{"id": 123456789}` — to jest Twoje **Chat ID**

**Krok 3 — ustaw zmienne środowiskowe:**
```bash
cp .env.example .env
# Edytuj .env i wpisz token i chat_id
```

### 3. Uruchom
```bash
# Lokalnie (załaduje .env automatycznie):
pip install python-dotenv
python start_local.py

# Lub z ręcznym ustawieniem zmiennych:
export TELEGRAM_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
python monitor.py
```

---

## Jak dodawać słowa kluczowe

Otwórz `monitor.py` i znajdź sekcję `PDF_KEYWORD_RULES`. Każda reguła to słownik:

```python
{
    "keywords": ["słowo1", "słowo2"],   # szukane w PDF (OR — wystarczy jedno)
    "label":    "MOJA ETYKIETA",        # wyświetlana w powiadomieniu
    "note":     "Dopisek dla Ciebie",   # dodatkowa informacja
    "emoji":    "🔔",                   # emoji przed etykietą
},
```

**Przykłady gotowe do wklejenia:**

```python
# Ogłoszenia dot. nieruchomości
{
    "keywords": ["nieruchomość", "nieruchomosc", "lokal", "grunt", "działka", "dzialka"],
    "label":    "NIERUCHOMOŚĆ",
    "note":     "Dotyczy nieruchomości — sprawdź KW i stan prawny przed kontaktem.",
    "emoji":    "🏠",
},

# Cena do negocjacji
{
    "keywords": ["negocjacje", "do negocjacji", "cena negocjowana"],
    "label":    "NEGOCJACJE",
    "note":     "Cena jest do negocjacji — warto zadzwonić.",
    "emoji":    "🤝",
},

# Gotówka
{
    "keywords": ["gotówka", "gotowka", "płatność gotówką", "platnosc gotowka"],
    "label":    "GOTÓWKA",
    "note":     "Wymagana płatność gotówką przy odbiorze.",
    "emoji":    "💵",
},
```

---

## Przykładowe powiadomienie Telegram

```
🏷 WOLNA RĘKA — Mazowieckie · Urząd Skarbowy w Płońsku
📄 Zawiadomienie o sprzedaży z wolnej ręki - Samochód osobowy BMW 520i
🔗 Otwórz ogłoszenie

━━━━━━━━━━━━━━━━━━━━
💳 PRZELEW
Ogłoszenie wymaga płatności przelewem — przygotuj dane do przelewu przed kontaktem.
📋 KOLEJNOŚĆ ZGŁOSZEŃ
Sprzedaż wg kolejności zgłoszeń — działaj szybko i zgłoś się jako pierwszy!
```

---

## Hosting za darmo

### Railway.app (zalecane)

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

W panelu Railway → **Variables** dodaj:
- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`
- `CHECK_INTERVAL` = `5`

### GitHub Actions (całkowicie darmowe)

Utwórz `.github/workflows/monitor.yml`:

```yaml
name: KAS Monitor
on:
  schedule:
    - cron: '*/5 * * * *'
  workflow_dispatch:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Restore seen listings
        uses: actions/cache@v4
        with:
          path: seen_listings.json
          key: seen-${{ github.run_id }}
          restore-keys: seen-
      - run: pip install -r requirements.txt
      - name: Run check
        env:
          TELEGRAM_TOKEN:   ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python -c "from monitor import check_all; check_all()"
      - name: Save seen listings
        uses: actions/cache@v4
        with:
          path: seen_listings.json
          key: seen-${{ github.run_id }}
```

Dodaj sekrety: GitHub repo → Settings → Secrets → `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`.

### Render.com

New → Background Worker → połącz GitHub  
- Build: `pip install -r requirements.txt`  
- Start: `python monitor.py`  
- Environment: dodaj `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`

---

## Pliki

```
kas-monitor/
├── monitor.py          # główny skrypt (edytuj PDF_KEYWORD_RULES)
├── requirements.txt
├── Procfile
├── runtime.txt
├── .env.example
├── start_local.py
└── seen_listings.json  # tworzony automatycznie
```
