# Übergabeprotokoll — Neo Fabel Live-Trading-Test

**Erstellt von:** Claude (Cowork-Modus, ohne Terminal-/Computer-Use-Zugriff auf die reale Windows-Maschine)
**Datum:** 2026-07-22
**Zweck:** Nahtlose Übergabe an den Hermes-Agenten zur Fortsetzung der Arbeit — insbesondere für Schritte, die echten Terminalzugriff auf `D:\Neo_Fabel` / die native Windows-Umgebung erfordern.

---

## 0. Wichtigste Einschränkung dieser Session (bitte zuerst lesen)

Ich (Claude, Cowork) hatte in dieser Session **nur Datei-Lese-/Schreibzugriff** auf den Ordner `D:\Neo_Fabel` — **keinen** Zugriff auf:
- ein reales Terminal/PowerShell auf der Windows-Maschine des Users
- die native `kraken.exe` CLI
- das Kraken-Konto oder dessen Auth-Store
- Computer-Use / Browser-Steuerung (wurde in dieser Session nicht aktiviert)

Jeder Befehl, der unten als "auszuführen" markiert ist, musste vom User selbst in seinem eigenen PowerShell-Fenster ausgeführt werden. **Falls Hermes echten Terminalzugriff hat, ist das der entscheidende Unterschied** — Hermes kann ab hier direkt weiterarbeiten, wo ich nur beraten konnte.

---

## 1. Projektüberblick

**Neo Fabel** (`D:\Neo_Fabel`) ist ein bereits weitgehend fertiggestelltes AI-gestütztes Trading-Ökosystem:

- **Frontend:** React/Vite (`src/`), Firebase Auth
- **Backend:** Python/FastAPI (`backend/app/`), PostgreSQL, optional Qdrant
- **Signal-Pipeline:** `backend/app/signals/` — vollständig implementiert: enum-basierte State Machine (`domain.py`), deterministische Policy-Gates (`policy.py`), durable Postgres-Lease-Worker (`worker.py`), pluggable AI-Evaluator (`evaluator.py`), Paper-Execution-Port (`executor.py`)
- **Fable Engine:** internes Grid/DCA-Signalgenerator unter `backend/app/signals/engine/`
- **ONNX Neural Core, Chronos (Backtesting), Academy (Trainingsloop):** alle bereits implementiert, inkl. Dashboard-Seiten (`src/features/{onnx,chronos,academy}/`)
- **Testabdeckung:** 50 Dateien unter `backend/tests/`, inkl. `test_signal_routes_functional_smoke.py`, `test_signal_routes_gates.py`, `test_signal_routes_hardening.py`, `test_signals_safety.py`, `test_capital_policy.py`, `test_guardrails.py`

**Wichtige Erkenntnis aus dieser Session:** Eine frühere Planungsrunde von mir hatte fälschlich angenommen, das System sei "Greenfield" und ein Architekturkonzept von Grund auf nötig. Das war falsch — das System existiert bereits in ausgereifter Form. Zwei Dokumente aus dieser Fehleinschätzung liegen noch im Projekt und sollten **nicht als Bauplan verwendet werden**, da sie nicht der Realität entsprechen:
- `AI_TRADING_ECOSYSTEM_PLAN.md`
- `IMPLEMENTATION_BOOTSTRAP.md`

Empfehlung: Diese zwei Dateien löschen oder klar als "veraltet/falsch" markieren, sobald der User zustimmt (`allow_cowork_file_delete` erforderlich, da sie in `D:\Neo_Fabel` liegen).

---

## 2. Sicherheitsbefunde dieser Session

### 2.1 BEHOBEN: `.env` — `KRAKEN_MAX_NOTIONAL=2,5` (Komma statt Punkt)

**Problem:** `backend/app/settings.py` Zeile 30 definiert `kraken_max_notional: Decimal = Field(default=Decimal("2"), validation_alias="KRAKEN_MAX_NOTIONAL")`. Pydantic instanziiert `Settings()` beim Modul-Import (in `main.py` wird `settings.cors_origins` etc. direkt auf Modulebene verwendet). `Decimal("2,5")` wirft eine `InvalidOperation`-Exception → die gesamte App crashte beim Start, **noch bevor Uvicorn überhaupt den Port bindet**. Das war mit sehr hoher Wahrscheinlichkeit der Hauptgrund für "der Server startet nicht".

**Fix:** In `D:\Neo_Fabel\.env` geändert zu `KRAKEN_MAX_NOTIONAL=2.5`. ✅ Bereits erledigt.

### 2.2 OFFEN: `.env.example` enthält echte Secrets und ist NICHT von Git ignoriert

**Problem:** `.gitignore` Zeile 8-9:
```
.env*
!.env.example
```
Das negiert `.env.example` explizit aus der Ignore-Regel — die Datei wird also von Git getrackt. Gleichzeitig ist `.env.example` vollständig mit echten, funktionsfähigen Secrets befüllt (Gemini, OpenAI, OpenRouter, XAI, Moonshot, BytePlus, Alpha Vantage, Finnhub, Telegram-Bot-Token, GitHub PAT, Qdrant API Key, TVremix Key, AIPrimeTech Key — sowie ursprünglich auch ein Kraken-Schlüsselpaar, das der User zwischenzeitlich rotiert hat).

**Impact:** Falls dieses Repo jemals gepusht/geteilt wurde (GitHub, privates Remote, Backup-Sync), sind diese Credentials in der Git-Historie kompromittiert.

**Noch nicht behoben** — der User wurde gefragt, ob das Repo je gepusht wurde, hat dazu aber noch nicht geantwortet; die eigentliche Bereinigung (echte Werte in `.env.local` verschieben, `.env.example` auf Platzhalter zurücksetzen) wurde noch nicht durchgeführt, weil der Fokus stattdessen auf "Server zum Laufen bringen" verschoben wurde.

**Empfehlung für Hermes:** Fragen, ob das Repo je zu einem Remote gepusht wurde. Falls ja: alle in `.env.example` sichtbaren Keys als kompromittiert behandeln und rotieren (Gemini, OpenAI, OpenRouter, XAI, Moonshot, BytePlus, Alpha Vantage, Finnhub, Telegram, GitHub PAT, Qdrant, TVremix, AIPrimeTech). Danach `.env.example` auf reine Platzhalterwerte zurücksetzen.

### 2.3 KRITISCH, TEILWEISE ADRESSIERT: `docker-compose.yml` erzwingt Paper-Mode unabhängig von `.env`

**Befund:** `docker-compose.yml` Zeilen 42-43 und 113-114 setzen `KRAKEN_AUTONOMY_LEVEL: "2"` und `KRAKEN_LIVE_TRADING_ENABLED: "false"` als **literale** Werte (nicht `${VAR}`-Substitution) für die Services `api` und `signal-worker`. Literale Compose-`environment`-Werte überschreiben *immer* `.env`. Das bedeutet: **jeder dokumentierte Docker-Weg im README erzwingt Paper-Modus**, egal was in `.env` steht. Das wirkt wie ein bewusstes, zusätzliches Sicherheits-Gate (unabhängig von den `.env`-Flags).

**Konsequenz:** Live-Trading (Level 4) läuft **nicht** über Docker Compose, sondern ausschließlich über den nativen Windows-Pfad:
```
scripts/kraken-level4-preflight.ps1 → scripts/kraken-deadman-refresh.ps1 -Loop → scripts/kraken-level1-monitor.ps1
```
Diese Skripte rufen die native `kraken`-CLI direkt auf (nicht über Docker, nicht über die FastAPI-App).

### 2.4 Firebase-Zugangsdaten fehlerhaft (blockiert authentifizierte Endpunkte, nicht den Start selbst)

**Problem:** `.env` hat `GOOGLE_APPLICATION_CREDENTIALS=finnp17@gmail.com` (eine E-Mail-Adresse, kein Dateipfad). `.env.local` verweist stattdessen auf `D:\Neo_Fabel\firebase.json` — das ist aber **nur die Firebase-Hosting-Konfiguration** (Rewrites, Cache-Header), **kein** Service-Account-Schlüssel. Es existiert im gesamten Repo keine echte `serviceAccount*.json`/`firebase-adminsdk*.json`-Datei.

**Impact:** `backend/app/auth.py` Zeile 56 versucht `credentials.Certificate(settings.firebase_credentials_path)` zu laden — das schlägt fehl, sobald ein authentifizierter Endpunkt aufgerufen wird (lazy init, kein Crash beim Start). Da `AUTH_DEV_BYPASS=false` in `.env` gesetzt ist, gibt es aktuell keinen Fallback. Betroffen: `/api/v1/signal-routes`, `/api/v1/loops/live/start`, jeder `require_user`/`require_signal_admin`-geschützte Endpunkt.

**Status:** User wollte einen neuen Service-Account-Schlüssel über die Firebase Console generieren (`https://console.firebase.google.com/project/tv-trading-f3be0/settings/serviceaccounts/adminsdk`, Projekt `tv-trading-f3be0`). **Der User hat mir den Dateipfad zum heruntergeladenen JSON noch nicht mitgeteilt** — das Gespräch ist zum Live-Trading-Test abgebogen, bevor das abgeschlossen wurde. **Das ist ein offener Blocker.**

---

## 3. Aktueller Blocker: Kraken-CLI-Authentifizierung schlägt fehl

Der User möchte **einen einzigen kleinen Live-Test-Trade** platzieren (Guthaben: ca. 3€, "Pissgroschen"), danach sofort zurück auf Paper-Modus. Guardrails sind entsprechend klein konfiguriert (`KRAKEN_MAX_NOTIONAL=2.5`, `KRAKEN_MAX_ORDER_SIZE=25`, Pair-Allowlist `ADAUSD,XRPUSD,ADAEUR,XRPEUR`).

**Preflight-Ergebnis** (`scripts/kraken-level4-preflight.ps1 -PairAllowlist "ADAUSD" -MaxOrderSize "0.01"`):
```
[FAIL] auth test: kraken auth test failed: {"error":"auth","message":"Authentication failed: EAPI:Invalid key"}
[FAIL] balance: ... Invalid key
[FAIL] open-orders: ... Invalid key
[OK] pair ADAUSD tradable
[WARN] sample validate failed: ... Invalid key
[SKIP] deadman switch
Preflight FAILED - do not start Level 4 session.
```

**Ursache (vermutet, nicht bestätigt):** Die native `kraken`-CLI liest Zugangsdaten **nicht** aus `.env`/`.env.local` — sondern entweder aus `$env:KRAKEN_API_KEY`/`$env:KRAKEN_API_SECRET` in der aktuellen Shell-Session, oder aus einem eigenen, persistenten Auth-Store (vermutlich via `kraken auth set`, das in den bisherigen Skript-Kommentaren erwähnt wird, dessen exakte Syntax aber nie verifiziert wurde). Der User hat im Verlauf **mehrere unterschiedliche Kraken-Schlüsselpaare** genannt:

1. `.env.local` (Spot): `KRAKEN_API_KEY=yyUJbZrOM/Obj2QjMcQou0bCnguwR9uzVSA9PN6Ty/xvVeh71P8ik9aZ` — laut User evtl. der **neue No-Withdraw-Schlüssel** (unbestätigt)
2. `.env` (Spot, abweichend): `KRAKEN_API_KEY=GfQofYatiHBivp7g4gSEX/hCnu8DsGef33XE1NQaZIMc1llAfCVIPaUR`
3. Zwei weitere im Chat genannte Paare, als "kraken public/personal" und "spot public/personal" bezeichnet, ohne klare Zuordnung, welches aktuell gültig ist

**Wichtig:** Diese Werte sind bereits im Chat-Verlauf offengelegt worden. Sicherheitsempfehlung: sobald der Live-Test abgeschlossen ist, sollte der User in Erwägung ziehen, den in diesem Chat geteilten Schlüssel erneut zu rotieren, da er nun außerhalb der lokalen `.env`-Dateien in einem Konversationsverlauf existiert.

**Nächster Schritt (noch nicht ausgeführt):**
1. Klären, welches der genannten Schlüsselpaare tatsächlich der neu erstellte No-Withdraw-Spot-Key ist.
2. In der PowerShell-Session direkt setzen:
```powershell
$env:KRAKEN_API_KEY = "<bestätigter neuer Key>"
$env:KRAKEN_API_SECRET = "<bestätigtes neues Secret>"
kraken auth test
```
3. Prüfen, ob eventuell ein älterer, gespeicherter `kraken auth set`-Eintrag Vorrang vor den Env-Vars hat (CLI-Dokumentation/Hilfe dazu wurde in dieser Session nicht eingesehen — `kraken --help` / `kraken auth --help` wäre der nächste Schritt, um die exakte Auth-Precedence zu verstehen, statt sie zu vermuten).
4. Erst wenn `kraken auth test` sauber durchläuft, das volle Preflight-Skript erneut ausführen.

---

## 4. Sicherheitsrahmen für den geplanten Live-Test (bitte beibehalten)

Der User ist sich des Risikos bewusst und möchte bewusst einen kleinen, einmaligen Test durchführen. Der vereinbarte Rahmen, den Hermes respektieren sollte:

- **Einsatz:** ca. 3€ Gesamtguthaben, Order-Größe deutlich unter `KRAKEN_MAX_NOTIONAL=2.5`
- **Schlüssel:** No-Withdraw/Trade-only (vom User bestätigt umgestellt)
- **Pair:** ADAUSD (vorgeschlagen, 5 ADA, Market-Order)
- **Ablauf:** Preflight (ohne `-LiveEnabled`) muss vollständig `[OK]` sein, bevor irgendetwas live geht → danach genau **eine** Order → danach sofort zurück auf Paper (`.env`: `KRAKEN_LIVE_TRADING_ENABLED=false`, `KRAKEN_AUTONOMY_LEVEL=2`)
- **Kein Level-3-Track-Record vorhanden** — User hat das selbst bestätigt und bewusst in Kauf genommen (README empfiehlt eigentlich ≥1 Woche stabiles Level-3-Supervised-Trading vor Level 4)
- **Ausführung der eigentlichen Order muss der User selbst im Terminal tätigen** — kein Agent sollte das automatisiert/unbeaufsichtigt tun

Der exakte Befehl für den eigentlichen Test-Trade (erst nach grünem Preflight ausführen):
```powershell
kraken order buy ADAUSD 5 --type market
```

Danach sofort:
```powershell
# In .env zurücksetzen:
# KRAKEN_LIVE_TRADING_ENABLED=false
# KRAKEN_AUTONOMY_LEVEL=2
```

---

## 5. Offene Aufgabenliste für Hermes (priorisiert)

1. **Kraken-Auth klären und fixen** (Abschnitt 3) — welcher Schlüssel ist aktiv, warum schlägt `auth test` fehl, `kraken auth --help` prüfen statt zu raten.
2. **Firebase Service-Account-JSON** — User wollte einen neuen generieren; Pfad noch nicht mitgeteilt. Sobald vorhanden: `.env` → `GOOGLE_APPLICATION_CREDENTIALS=<realer Pfad>` setzen (außerhalb des Repos speichern, siehe README-Abschnitt "Firebase Auth setup").
3. **Live-Test durchführen** gemäß Rahmen in Abschnitt 4, dann sofort zurück auf Paper.
4. **`.env.example`-Leck bereinigen** (Abschnitt 2.2) — sobald der User bestätigt, ob das Repo je gepusht wurde.
5. **Veraltete Planungsdokumente entfernen/korrigieren**: `AI_TRADING_ECOSYSTEM_PLAN.md`, `IMPLEMENTATION_BOOTSTRAP.md` — spiegeln nicht die reale, bereits fertige Architektur wider.
6. **Nach dem Live-Test:** vollständigen Docker-Paper-Stack einmal sauber hochfahren und verifizieren (`docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file .env.local up --build api postgres`, dann `npm run dev`), damit der User ein funktionierendes Gesamtsystem sieht, nicht nur den isolierten CLI-Test.

---

## 6. Referenzen

| Datei | Relevanz |
|---|---|
| `backend/app/settings.py` | Pydantic-Settings, u.a. `kraken_max_notional` (Zeile 30), `firebase_credentials_path` (Zeile 45-47) |
| `backend/app/auth.py` | Firebase-Admin-Init, lazy (Zeilen 43-66) |
| `backend/app/main.py` | FastAPI-Lifespan (Zeile 107), Settings-Nutzung auf Modulebene (Zeile 261) |
| `docker-compose.yml` | Hardcodierte Paper-Only-Werte (Zeilen 42-43, 113-114) |
| `docker-compose.local.yml` | Windows-Lokal-Overlay, erzwingt ebenfalls `AUTH_DEV_BYPASS=true`, Paper-Only |
| `docker-compose.firebase.yml` | Firebase-Credential-Overlay für Docker (separat von nativer Ausführung) |
| `scripts/kraken-level4-preflight.ps1` | Preflight-Check, nativ, nutzt `kraken`-CLI direkt |
| `scripts/kraken-deadman-refresh.ps1`, `scripts/kraken-level1-monitor.ps1` | Noch nicht gelesen/geprüft in dieser Session |
| `.env`, `.env.local`, `.env.example` | Siehe Abschnitt 2 — Widersprüche zwischen den Dateien beachten |
| `firebase.json` | NUR Hosting-Config, kein Service-Account-Schlüssel |

---

**Ende des Übergabeprotokolls.**