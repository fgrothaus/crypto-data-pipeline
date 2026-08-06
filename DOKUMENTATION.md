# Crypto Data Pipeline

**Eine Echtzeit-Datenpipeline für Kryptowährungskurse — von der externen API bis in den Browser, betrieben als Microservices auf Kubernetes mit vollautomatischer GitOps-Deployment-Kette.**

---

> [!IMPORTANT]
> **Zweck des Projekts (Portfolio-Kontext)**
>
> Die Fachlichkeit (ein Krypto-Preis-Ticker) ist bewusst schlank gehalten. Sie ist der *Aufhänger*, um einen vollständigen, produktionsnahen Stack zu demonstrieren und mein Verständnis der einzelnen Bausteine und ihres Zusammenspiels zu zeigen:
>
> **Asynchrones Python (asyncio) · Message Broker (RabbitMQ) · In-Memory-Cache (Redis) · relationale Persistenz (PostgreSQL + SQLAlchemy 2.0 async) · WebSockets für Server-Push · REST für historische Abfragen · React/TypeScript-SPA · Docker & Multi-Stage-Builds · Kubernetes (k3d) mit Deployments, StatefulSets, Services, Ingress, ConfigMaps, Secrets, Probes & Resource Limits · Reverse Proxy (Traefik) · CI mit GitHub Actions · CD nach dem GitOps-Prinzip mit ArgoCD.**
>
> Der Lerneffekt liegt im *Drumherum*, nicht in der Domäne — die Domäne ist aber bewusst so gewählt, dass sie einen echten Datenstrom erzeugt und damit alle Bausteine sinnvoll unter Last setzt.

---

## 📹 Video-Demo

> **Platzhalter — Video wird nachträglich eingefügt.**
>
> Das Video zeigt den kompletten End-to-End-Ablauf:
>
> 1. Start der Anwendung **lokal via `docker compose`** (Entwicklungs-/Debug-Modus mit Hot Reload).
> 2. Hochfahren des **Kubernetes-Clusters (k3d)** inkl. ArgoCD-Bootstrapping über das PowerShell-Skript.
> 3. Die laufende Anwendung im Browser: **Live-Dashboard (WebSocket)** und **Detail-Chart (REST + Postgres-Historie)**.
> 4. Eine **Code-Änderung** wird vorgenommen und nach GitHub gepusht.
> 5. Die **CI/CD-Pipeline** läuft durch (GitHub Actions: Lint → Test → Build → Push → Manifest-Update).
> 6. **ArgoCD übernimmt die Änderung automatisch** (GitOps-Sync) — das Ergebnis wird live im Cluster sichtbar.

<!--
VIDEO HIER EINFÜGEN, z. B.:

https://github.com/fgrothaus/crypto-data-pipeline/assets/<user-id>/<video>.mp4

oder als klickbares Thumbnail:

[![Demo ansehen](docs/video-thumbnail.png)](https://link-zum-video)
-->

---

## Inhaltsverzeichnis

1. [Was macht die Anwendung?](#was-macht-die-anwendung)
2. [Tech-Stack im Überblick](#tech-stack-im-überblick)
3. [Architektur & Datenfluss](#architektur--datenfluss)
4. [Die Services im Detail](#die-services-im-detail)
5. [Datenhaltung: Redis vs. PostgreSQL vs. RabbitMQ](#datenhaltung-redis-vs-postgresql-vs-rabbitmq)
6. [API-Referenz](#api-referenz)
7. [Frontend-Architektur](#frontend-architektur)
8. [Betriebsmodelle: Docker Compose (Debug) vs. Kubernetes (Betrieb)](#betriebsmodelle-docker-compose-debug-vs-kubernetes-betrieb)
9. [Voraussetzungen](#voraussetzungen)
10. [Anwendung starten](#anwendung-starten)
11. [Konfiguration & Secrets](#konfiguration--secrets)
12. [Die CI/CD-Pipeline (GitOps)](#die-cicd-pipeline-gitops)
13. [Tests](#tests)
14. [Bekannte Punkte & Verbesserungspotenzial](#bekannte-punkte--verbesserungspotenzial)
15. [Projektstruktur](#projektstruktur)

---

## Was macht die Anwendung?

Die Anwendung zeigt in Echtzeit die Kurse von sieben Kryptowährungen in Euro an — inklusive der 24-Stunden-Veränderung — und bietet pro Coin eine **historische Kursentwicklung als Chart**.

**Beobachtete Coins:** `bitcoin`, `ethereum`, `solana`, `cardano`, `ripple`, `polkadot`, `dogecoin`

Der Ablauf in einem Satz:

> Ein Ingestion-Service holt alle 10 Sekunden die Kurse von der **CoinGecko-API**, schickt sie durch eine **RabbitMQ-Queue**; ein Consumer schreibt daraus den *aktuellen* Stand nach **Redis** und *jeden einzelnen Datenpunkt* nach **PostgreSQL**; eine **FastAPI**-Anwendung streamt den aktuellen Stand per **WebSocket** an ein **React-Frontend** und liefert die Historie über einen **REST-Endpunkt** aus.

Daraus ergeben sich zwei bewusst getrennte Datenpfade:

| Pfad | Zweck | Speicher | Transport ins Frontend | Latenz-Anspruch |
|---|---|---|---|---|
| **Hot Path** | „Was kostet Bitcoin *jetzt*?" | Redis (1 Key, wird überschrieben) | WebSocket (Server-Push, 1×/s) | niedrig, Push |
| **Cold Path** | „Wie hat sich Bitcoin entwickelt?" | PostgreSQL (Zeitreihe, viele Zeilen) | REST (`GET`, on demand) | unkritisch, Pull |

Genau diese Trennung ist der fachliche Kern des Projekts: **derselbe Datenstrom** wird für zwei völlig unterschiedliche Zugriffsmuster in zwei unterschiedlich geeigneten Speichern abgelegt.

---

## Tech-Stack im Überblick

### Anwendungsebene

| Bereich | Technologie | Wofür konkret |
|---|---|---|
| **Sprache Backend** | Python 3.11 | Alle drei Backend-Prozesse |
| **Async-Modell** | `asyncio` | Durchgängig async — kein Thread-Pool, kein blockierendes I/O |
| **Web-Framework** | **FastAPI** (Starlette/Uvicorn) | REST-Endpunkte, WebSocket-Endpunkt, CORS-Middleware, Health-Endpunkte |
| **ASGI-Server** | **Uvicorn** | Laufzeit für die API |
| **Validierung** | **Pydantic v2** | Schema-Validierung der CoinGecko-Antwort und jeder Queue-Nachricht (`PriceUpdate`, `CoinMetrics`) |
| **HTTP-Client** | **httpx** (async) | Abruf der CoinGecko-API |
| **AMQP-Client** | **aio-pika** | Publish/Consume gegen RabbitMQ, async |
| **Redis-Client** | **redis-py** (`redis.asyncio`) | Lesen/Schreiben des Latest-Value-Keys |
| **ORM / DB-Layer** | **SQLAlchemy 2.0** (async, `DeclarativeBase`) | Schema-Definition, Session-Handling, `create_all()`-Bootstrap |
| **DB-Treiber** | **asyncpg** | Async-Postgres-Treiber hinter `postgresql+asyncpg://` |
| **Konfiguration** | **python-dotenv** | `.env` lokal, ConfigMap/Secret im Cluster |
| **Hot Reload (dev)** | **hupper**, `uvicorn --reload` | Prozess-Neustart bei Codeänderung im Compose-Setup |

### Frontend

| Bereich | Technologie | Wofür konkret |
|---|---|---|
| **Framework** | **React 19** | UI |
| **Sprache** | **TypeScript** | Typisierte Payloads (`CryptoDataPayload`, `PricePoint`) |
| **Build-Tool** | **Vite** | Dev-Server mit HMR, Produktionsbuild |
| **Routing** | **react-router-dom v7** | `/` (Dashboard) und `/coin/:coinId` (Detailseite) |
| **Charts** | **Recharts** | `LineChart` der Kurshistorie |
| **Live-Daten** | **native WebSocket API** | Gekapselt im Custom Hook `useCryptoWebSocket` |
| **Auslieferung (prod)** | **Nginx (alpine)** | Statisches Bundle aus einem Multi-Stage-Docker-Build |

### Infrastruktur & Betrieb

| Bereich | Technologie | Wofür konkret |
|---|---|---|
| **Message Broker** | **RabbitMQ 4.0** (`-management`) | Durable Queue `crypto_prices`, entkoppelt Producer/Consumer |
| **Cache** | **Redis (alpine)** | Latest-Value-Store für den Hot Path |
| **Datenbank** | **PostgreSQL 16 (alpine)** | Zeitreihe der Kurse für den Cold Path |
| **Container** | **Docker**, Multi-Stage-Build (Frontend) | Ein Image je Service |
| **Lokale Orchestrierung** | **Docker Compose** | Entwicklungs- und Debug-Umgebung |
| **Cluster** | **Kubernetes via k3d** (k3s in Docker) | Zielplattform für den Betrieb |
| **Reverse Proxy / Ingress** | **Traefik v3** | In Compose als Container mit Docker-Labels, in k3d als mitgelieferter Ingress Controller |
| **CI** | **GitHub Actions** | Drei Workflows mit `paths`-Filter, je Service |
| **CD** | **ArgoCD** | GitOps-Controller, überwacht `k8s/`, `selfHeal` + `prune` |
| **Registry** | **Docker Hub** | `fgrothaus1/crypto-{backend,frontend,ingestion}` |
| **Linting** | **Ruff** (Python), **ESLint** + `tsc --noEmit` (TS) | Qualitäts-Gate in der CI |
| **Tests** | **pytest** + **pytest-asyncio**, FastAPI `TestClient` | Integrationstests gegen echte Redis-/Postgres-Service-Container in der CI |
| **Bootstrapping** | **PowerShell** | `crypto-data-pipeline_CD.ps1` erstellt Cluster + ArgoCD + Secrets |

---

## Architektur & Datenfluss

### Komponenten-Überblick

```mermaid
flowchart LR
    subgraph ext["Externe Welt"]
        CG[("CoinGecko API<br/>/simple/price")]
        Browser["🌐 Browser (User)"]
    end

    subgraph cluster["Kubernetes-Cluster / Docker-Netzwerk"]
        direction TB

        ING["<b>ingestion-service</b><br/><i>Producer</i><br/>httpx + aio-pika"]
        RMQ{{"<b>RabbitMQ</b><br/>Queue: crypto_prices<br/>durable"}}
        CON["<b>backend-consumer</b><br/><i>Consumer</i><br/>aio-pika + redis + SQLAlchemy"]

        RED[("<b>Redis</b><br/>Key: crypto:latest_prices")]
        PG[("<b>PostgreSQL</b><br/>Tabelle: crypto_price_history")]

        API["<b>backend-api</b><br/>FastAPI + Uvicorn<br/>WebSocket + REST"]
        FE["<b>frontend</b><br/>React SPA · Nginx"]
        TR["<b>Traefik</b><br/>Ingress / Reverse Proxy"]
    end

    CG -->|"HTTP GET, alle 10 s"| ING
    ING -->|"AMQP publish (persistent)"| RMQ
    RMQ -->|"AMQP consume + ack"| CON
    CON -->|"SET — aktueller Stand"| RED
    CON -->|"INSERT — jeder Datenpunkt"| PG

    API -->|"GET, 1×/s (Hot Path)"| RED
    API -->|"SELECT on demand (Cold Path)"| PG

    Browser -->|"HTTP crypto.localhost"| TR
    Browser -->|"WS/HTTP api.crypto.localhost"| TR
    TR --> FE
    TR --> API
```

### Zeitlicher Ablauf (Sequenz)

```mermaid
sequenceDiagram
    autonumber
    participant CG as CoinGecko
    participant ING as Ingestion
    participant RMQ as RabbitMQ
    participant CON as Consumer
    participant RED as Redis
    participant PG as PostgreSQL
    participant API as Backend-API
    participant FE as Frontend

    rect rgb(240,248,255)
    note over ING,RMQ: Ingestion-Loop
    loop alle 10 Sekunden
        ING->>CG: GET /simple/price
        CG-->>ING: JSON (7 Coins)
        ING->>ING: Pydantic-Validierung
        ING->>RMQ: publish "crypto_prices" (PERSISTENT)
    end
    end

    rect rgb(245,255,245)
    note over CON,PG: Consumer (schreibender Pfad)
    RMQ->>CON: deliver message
    CON->>CON: Pydantic-Validierung
    CON->>RED: SET crypto:latest_prices
    CON->>PG: INSERT (1 Zeile je Coin)
    CON-->>RMQ: ack
    end

    rect rgb(255,250,240)
    note over API,FE: Hot Path — Live-Kurse
    FE->>API: WebSocket connect /ws/prices
    loop jede Sekunde je Client
        API->>RED: GET crypto:latest_prices
        RED-->>API: JSON
        API-->>FE: WebSocket send
        FE->>FE: React-State aktualisieren
    end
    end

    rect rgb(253,245,255)
    note over API,FE: Cold Path — Historie
    FE->>API: GET /prices/history/{coin_id}
    API->>PG: SELECT timestamp, price_eur ORDER BY timestamp
    PG-->>API: Rows
    API-->>FE: JSON-Array
    FE->>FE: Recharts LineChart rendern
    end
```

### Netzwerk-/Routing-Schicht

Beide Betriebsmodelle verwenden **Traefik**, aber auf unterschiedlichem Weg — das ist bewusst so, weil es zeigt, dass Routing-Regeln deklarativ sind und die Anwendung selbst nichts davon wissen muss:

| | Docker Compose | Kubernetes (k3d) |
|---|---|---|
| **Traefik-Quelle** | Eigener `traefik:v3.0`-Container | Bei k3s/k3d bereits als Ingress Controller enthalten |
| **Konfiguration** | Docker-Provider liest **Container-Labels** | **`Ingress`-Ressource** (`k8s/frontend/ingress.yml`) |
| **Frontend-Route** | Label `traefik.http.routers.frontend.rule=Host(crypto.localhost)` → Port 5173 | `host: crypto.localhost` → `crypto-frontend-service:80` |
| **API-Route** | Label `traefik.http.routers.backend.rule=Host(api.crypto.localhost)` → Port 8000 | `host: api.crypto.localhost` → `crypto-api-service:8000` |
| **Zusätzlich** | `rabbitmq.localhost` → Management-UI :15672, Traefik-Dashboard :8080 | — |

Warum die API einen **eigenen Hostnamen** bekommt: Das Frontend läuft im Browser des Nutzers, nicht im Cluster. Cluster-interne DNS-Namen (`crypto-api-service`) sind für den Browser nicht auflösbar. Deshalb muss die API über den Ingress von außen erreichbar sein — sonst käme weder die WebSocket-Verbindung noch der REST-Call der Historie zustande.

---

## Die Services im Detail

| Service | Rolle | Kerntechnologien | Beschreibung |
|---|---|---|---|
| **ingestion-service** | Producer | `httpx`, `aio-pika`, Pydantic | Fragt alle 10 s die CoinGecko-API ab (API-Key im Header `x-cg-demo-api-key`), validiert die Antwort gegen `PriceUpdate` und publiziert sie als **persistente** Nachricht in die durable Queue `crypto_prices`. Enthält eine **Reconnect-Schleife**: Bricht die AMQP-Verbindung ab, wird nach 5 s neu verbunden statt den Prozess sterben zu lassen. |
| **backend-consumer** | Consumer / Writer | `aio-pika`, `redis.asyncio`, SQLAlchemy async | Lauscht auf `crypto_prices`. Pro Nachricht: (1) Validierung, (2) `SET` auf den Redis-Key `crypto:latest_prices`, (3) `INSERT` je Coin nach Postgres. Startet zusätzlich einen **Cleanup-Task**, der minütlich die Tabelle auf eine Obergrenze an Zeilen zurückschneidet. Wartet beim Start in einer Retry-Schleife auf RabbitMQ und legt danach das DB-Schema an. |
| **backend-api** | Reader / Auslieferung | FastAPI, Uvicorn, `redis.asyncio`, SQLAlchemy async | Stellt den WebSocket `/ws/prices` (Push aus Redis), den REST-Endpunkt `/prices/history/{coin_id}` (Lesen aus Postgres) sowie `/live` und `/ready` bereit. CORS ist offen (`allow_origins=["*"]`), da das Frontend unter einem anderen Host läuft. |
| **frontend** | UI | React 19, TS, Vite, react-router, Recharts | SPA mit zwei Routen. Dashboard konsumiert den WebSocket, Detailseite den REST-Endpunkt. Im Betrieb als statisches Bundle von Nginx ausgeliefert. |
| **RabbitMQ** | Message Broker | `rabbitmq:4.0-management` | Entkoppelt Producer und Consumer. Management-UI auf Port 15672. Im Cluster als **StatefulSet mit PVC**. |
| **Redis** | Cache | `redis:alpine` | Ein einziger Key mit dem aktuellen Stand. Bewusst **ohne Persistenz** im Cluster — der Wert ist nach spätestens 10 s ohnehin wieder da. |
| **PostgreSQL** | Persistenz | `postgres:16-alpine` | Zeitreihe der Kurse. Im Cluster als **StatefulSet mit `volumeClaimTemplates`** (2 Gi), lokal als Compose-Service mit nach außen gemapptem Port 5432 (für DBeaver o. ä.). |
| **Traefik** | Ingress | `traefik:v3` bzw. k3s-eigener Controller | Siehe Routing-Tabelle oben. |
| **ArgoCD** | GitOps-Controller | `argoproj/argo-cd` | Überwacht den `k8s/`-Ordner im Repo und gleicht den Cluster fortlaufend daran an. |

### Warum ist das Backend in zwei Prozesse geteilt?

`consumer.py` und `main.py` liegen im **selben Verzeichnis, teilen sich denselben Code (`models.py`, `database/`) und dasselbe Docker-Image** — laufen aber als **zwei getrennte Pods**. Das Image hat als Default-`CMD` den Uvicorn-Start; das Consumer-Deployment überschreibt das per `command: ["python", "consumer.py"]`.

Der Grund ist die **unabhängige Skalierbarkeit entlang der Lastachse**:

- Die **API** skaliert mit der Anzahl gleichzeitiger Browser-Verbindungen (jede WebSocket-Verbindung ist eine offene Verbindung mit eigenem Polling-Loop). Mehr Nutzer → mehr Repliken.
- Der **Consumer** skaliert mit dem eingehenden Nachrichtenvolumen. Bei einer Nachricht alle 10 Sekunden genügt exakt **eine** Replika — mehr wären sogar schädlich, weil dann konkurrierende Writer denselben Redis-Key überschreiben.

Ein einzelner monolithischer Prozess könnte diese beiden Achsen nicht getrennt bedienen. Zusätzlich isoliert die Trennung die Fehlerdomänen: Ein Absturz des Consumers reißt nicht die laufenden WebSocket-Verbindungen mit.

### Datenmodell (PostgreSQL)

Tabelle `crypto_price_history`, definiert in `services/backend/models.py`:

| Spalte | Typ | Anmerkung |
|---|---|---|
| `id` | `Integer`, PK | Autoincrement, indiziert |
| `coin_id` | `String(50)`, `NOT NULL` | **indiziert** — die History-Abfrage filtert darauf |
| `symbol` | `String(10)`, `NOT NULL` | Abgeleitet aus den ersten drei Zeichen der `coin_id` |
| `name` | `String(100)`, `NOT NULL` | Abgeleitet aus `coin_id.capitalize()` |
| `price_eur` | `Numeric(18, 8)`, `NOT NULL` | **`Numeric` statt `Float`** — bei Geldbeträgen bewusst exakt statt binär gerundet |
| `timestamp` | `DateTime(timezone=True)` | Default `datetime.now(timezone.utc)`, **indiziert** — die Abfrage sortiert danach |

Das Schema wird beim Consumer-Start per `Base.metadata.create_all()` angelegt (idempotent). Ein Migrationstool (Alembic) gibt es bewusst noch nicht — siehe [Verbesserungspotenzial](#bekannte-punkte--verbesserungspotenzial).

**Retention:** Der Cleanup-Task hält die Tabelle bei maximal **8.000 Zeilen**. Bei 7 Coins alle 10 Sekunden entstehen 42 Zeilen/Minute — das entspricht rund **3 Stunden** rollierender Historie. Das ist für einen Live-Chart bewusst so gewählt und verhindert, dass das PVC im Dauerbetrieb vollläuft.

---

## Datenhaltung: Redis vs. PostgreSQL vs. RabbitMQ

Drei Datenspeicher in einem Projekt sind erklärungsbedürftig. Jeder hat hier eine klar abgegrenzte Aufgabe:

### Redis — Latest-Value-Store (Hot Path)

Redis hält **genau einen Key** (`crypto:latest_prices`) mit dem aktuellen Stand aller Coins als JSON. Der Consumer schreibt, die API liest.

Der Nutzen ist die **Entkopplung des schreibenden vom lesenden Pfad**: Egal ob ein oder tausend Browser verbunden sind — sie belasten weder die CoinGecko-API noch RabbitMQ noch Postgres, sondern lesen einen In-Memory-Wert. Das ist ein sauberer, lehrbuchmäßiger Cache-Einsatz.

*Bekannte Schwäche:* Der WebSocket-Loop **pollt** Redis jede Sekunde, auch wenn sich nichts geändert hat (der Wert ändert sich nur alle 10 s). Eleganter wäre **Redis Pub/Sub** — der Consumer publiziert bei Änderung, die API pusht ereignisgetrieben. Bei diesem Volumen ist es unkritisch, bei vielen Verbindungen wäre es die erste Optimierung.

### PostgreSQL — Zeitreihe (Cold Path)

Postgres beantwortet die Frage, die Redis strukturell **nicht** beantworten kann: „Wie war der Verlauf?" Redis überschreibt bei jedem `SET` — Historie existiert dort nicht.

Die Wahl einer relationalen DB ist hier bewusst:

- **Zeitreihen mit Filter + Sortierung** (`WHERE coin_id = ? ORDER BY timestamp`) sind genau das, wofür ein B-Tree-Index gemacht ist. Beide Spalten sind indiziert.
- **`Numeric(18,8)`** statt Fließkomma — bei Kursen ist exakte Dezimaldarstellung das korrekte Werkzeug.
- **Transaktionen:** `save_price_update` schreibt alle 7 Coins eines Ticks in *einer* Transaktion (`async with session.begin()`) — entweder alle oder keiner. Ein halber Tick kann nicht entstehen.
- **Async durchgängig:** Über `asyncpg` und SQLAlchemys `create_async_engine` blockiert kein DB-Call den Event-Loop. `pool_pre_ping=True` fängt tote Verbindungen ab (z. B. nach einem Postgres-Neustart im Cluster).

Erst durch diese Erweiterung wird der Nachrichtenstrom über RabbitMQ **fachlich sinnvoll**: Es gibt jetzt zwei Konsumenten-Aufgaben (Cache aktualisieren *und* Historie persistieren), nicht nur eine.

### RabbitMQ — Message Broker

RabbitMQ entkoppelt den Producer (Ingestion) vom Consumer. Die Queue ist `durable`, die Nachrichten sind `PERSISTENT`, der Consumer bestätigt jede Nachricht (`async with message.process()` — Ack erst nach erfolgreicher Verarbeitung, bei Exception wird die Nachricht nicht verloren quittiert).

#### Kritische Betrachtung — ehrlich eingeordnet

**Für die ursprüngliche Fachlichkeit (nur „letzter Wert zählt") war RabbitMQ überdimensioniert.** Ein einzelner Producer, ein einzelner Consumer, kein Routing, kein Fan-out — und der Consumer machte nichts als ein `SET`. `durable` + `PERSISTENT` war dabei sogar kontraproduktiv: Fällt der Consumer aus und stauen sich Nachrichten, arbeitet er nach dem Neustart erst *veraltete* Kurse ab, bevor er den aktuellen erreicht — genau das will man bei „nur der letzte Wert zählt" nicht.

**Mit der Postgres-Erweiterung hat sich das verschoben.** Jetzt ist jede einzelne Nachricht ein Datenpunkt, der nicht verloren gehen soll: Nachrichten, die sich während eines Consumer-Ausfalls stauen, werden nach dem Neustart nachgearbeitet und landen als Historie in der DB — die Queue puffert also echten Wertverlust weg. Das ist genau der Anwendungsfall, für den `durable` + `PERSISTENT` gemacht sind.

**Was den Einsatz vollends rechtfertigen würde:** ein zweiter, unabhängiger Consumer auf demselben Strom (z. B. Preis-Alarme oder eine Aggregation auf Minutenkerzen) über ein Fanout-Exchange. Dann spielt RabbitMQ seine Kernstärke — Verteilung eines Stroms an mehrere unabhängige Verarbeiter — voll aus. Aktuell wird die Queue über das `default_exchange` mit `routing_key` angesprochen, also im einfachsten Modus.

> **Fazit:** Als Demonstrationsbaustein war RabbitMQ von Anfang an wertvoll (StatefulSet + PVC im Cluster, Ack-Semantik, Reconnect-Handling). Seit der Postgres-Erweiterung ist er zusätzlich fachlich begründet.

---

## API-Referenz

Basis-Host: `http://api.crypto.localhost` (via Traefik/Ingress)

| Methode | Pfad | Beschreibung | Antwort |
|---|---|---|---|
| `WS` | `/ws/prices` | Server-Push aller aktuellen Kurse, 1×/s. Liest aus Redis. | Textframes mit `{"coins": {"bitcoin": {"eur": …, "eur_24h_change": …}, …}}` |
| `GET` | `/prices/history/{coin_id}` | Kurshistorie eines Coins, aufsteigend nach Zeit. Liest aus Postgres. | `200` → `[{"timestamp": "…", "price_eur": …}, …]` · `404` wenn keine Daten vorliegen |
| `GET` | `/live` | **Liveness** — läuft der Prozess? Keine Abhängigkeiten geprüft. | `200` → `{"status": "ok"}` |
| `GET` | `/ready` | **Readiness** — Deep Check: `PING` gegen Redis mit 2 s Timeout. | `200` → `{"status": "ok", "redis": "connected"}` · `500` bei Redis-Fehler |

Die Trennung von `/live` und `/ready` ist bewusst und entspricht der Kubernetes-Semantik: Die **Liveness-Probe** darf keine externen Abhängigkeiten prüfen, sonst startet Kubernetes den Pod neu, obwohl nur Redis kurz weg ist. Die **Readiness-Probe** darf und soll das prüfen — der Pod wird dann lediglich aus dem Service-Endpoint genommen und bekommt keinen Traffic mehr, bis er wieder bereit ist. Beide sind in `k8s/backend/api-deployment.yml` verdrahtet.

---

## Frontend-Architektur

```
src/
├── main.tsx                        # Entry, BrowserRouter
├── App.tsx                         # Routing: "/" und "/coin/:coinId"
├── pages/
│   ├── Dashboard.tsx               # Kachel-Grid, Live-Kurse, Klick → Detailseite
│   └── CoinDetail.tsx              # Recharts-LineChart der Historie
└── hooks/
    ├── useCryptoWebSockets.ts      # WebSocket-Lifecycle (Hot Path)
    └── useCoinHistory.ts           # fetch() der Historie (Cold Path)
```

Die beiden **Custom Hooks** kapseln je einen Datenpfad und halten die Komponenten frei von Transport-Logik:

**`useCryptoWebSocket(url)`** → `{ data, isConnected }`
Baut im `useEffect` die Verbindung auf und behandelt alle vier Events (`onopen`, `onmessage`, `onclose`, `onerror`). Zwei Details, die in der Praxis Fehler vermeiden:

- Ein `isComponentMounted`-Flag verhindert `setState` nach dem Unmount — relevant, weil React 19 im StrictMode Effects doppelt ausführt.
- Die Cleanup-Funktion schließt den Socket nur, wenn er `OPEN` oder `CONNECTING` ist — ein `close()` auf einem bereits geschlossenen Socket würde sonst unnötige Fehler-Logs erzeugen.

**`useCoinHistory(coinId)`** → `{ history, loading }`
Lädt die Historie beim Wechsel der `coinId` neu, setzt einen Ladezustand und formatiert die Zeitstempel bereits im Hook (`toLocaleTimeString('de-DE')`) — die Chart-Komponente bekommt fertige Anzeigedaten.

Der Verbindungsstatus wird als Badge im Dashboard angezeigt („Verbunden" / „Getrennt"), sodass im Video sichtbar ist, wenn die Pipeline unterbrochen wird.

---

## Betriebsmodelle: Docker Compose (Debug) vs. Kubernetes (Betrieb)

Das Projekt hat **zwei bewusst unterschiedliche Umgebungen**. Das ist kein Duplikat, sondern eine Trennung nach Zweck:

| Aspekt | **Docker Compose** — Entwickeln & Debuggen | **Kubernetes (k3d)** — Betrieb & Showcase |
|---|---|---|
| **Zweck** | Schneller Feedback-Loop beim Coden | Realistischer Betrieb, Deployment-Kette demonstrieren |
| **Code-Herkunft** | **Bind Mounts** — lokaler Quellcode direkt im Container | **Fertige Images** von Docker Hub, per SHA-Tag gepinnt |
| **Backend-API** | `uvicorn --reload` | `uvicorn` ohne Reload (Image-`CMD`) |
| **Consumer** | `hupper -m consumer` (Prozess-Neustart bei Codeänderung) | `command: ["python", "consumer.py"]` |
| **Ingestion** | `hupper -m ingestion_main` | Image-`CMD` `python ingestion_main.py` |
| **Frontend** | **Vite Dev-Server** (`node:20-alpine`, `npm run dev`, HMR, Polling-Watcher für Windows) | **Nginx** mit statischem Produktionsbundle aus dem Multi-Stage-Build |
| **Konfiguration** | `.env`-Dateien je Service (`env_file:`) | **ConfigMaps** (unkritisch) + **Secrets** (API-Key, DB-Zugang) |
| **Postgres** | Compose-Service, Port **5432 nach außen gemappt** (Zugriff mit DBeaver o. ä.), Named Volume | **StatefulSet** mit `volumeClaimTemplates` (2 Gi PVC), nur cluster-intern per `ClusterIP` |
| **RabbitMQ** | Container mit Named Volume, Management-UI über `rabbitmq.localhost` | **StatefulSet** mit PVC |
| **Redis** | Container, ohne Persistenz | **Deployment** (kein StatefulSet — als reiner Cache bewusst zustandslos) |
| **Routing** | Traefik-Container, gesteuert über **Docker-Labels** | k3s-Traefik, gesteuert über **`Ingress`-Ressource** |
| **Startreihenfolge** | `depends_on` | Retry-/Reconnect-Schleifen im Anwendungscode + Probes |
| **Ressourcen** | unbegrenzt | `requests`/`limits` je Container (64 Mi/100 m bis 256 Mi/500 m) |
| **Health-Checks** | keine | `readinessProbe` `/ready`, `livenessProbe` `/live` (API) |
| **Deployment** | `docker compose up --build` | **Vollautomatisch** über GitHub Actions → Git-Commit → ArgoCD-Sync |

**Warum beides?** Im Cluster ist Debugging teuer: Für jede Codeänderung müsste ein Image gebaut, gepusht, das Manifest aktualisiert und gesynct werden. Compose gibt dagegen Sub-Sekunden-Feedback über Bind Mounts, `--reload` und `hupper`. Umgekehrt zeigt Compose nichts über Probes, Ressourcenkontrolle, Rolling Updates, Self-Healing oder GitOps. **Compose ist die Werkbank, Kubernetes die Zielplattform** — der Anwendungscode ist in beiden identisch, weil die gesamte Umgebungsdifferenz über Environment-Variablen und Startbefehle abgebildet wird.

Genau das ist der eigentliche Punkt: **Die Services kennen ihre Umgebung nicht.** Sie lesen `REDIS_URL`, `RABBITMQ_CONNECTION_STRING`, `DATABASE_URL` und `API_KEY` — ob diese aus einer `.env`, einer ConfigMap oder einem Secret kommen, ist ihnen egal (12-Factor-Prinzip „Config in the environment").

---

## Voraussetzungen

### Für alle Varianten

| Tool | Zweck |
|---|---|
| **Git** | Repository klonen |
| **Docker Desktop** bzw. Docker Engine | Container-Runtime, Basis für alles Weitere |
| **CoinGecko Demo-API-Key** | Kostenlos unter <https://www.coingecko.com/en/api>. Wird von der Ingestion benötigt. |

### Zusätzlich für das Compose-Setup

- **Docker Compose** (in Docker Desktop enthalten)

### Zusätzlich für das Kubernetes-Setup

| Tool | Zweck |
|---|---|
| **[k3d](https://k3d.io/)** | Erzeugt ein leichtgewichtiges Kubernetes-Cluster (k3s) in Docker |
| **[kubectl](https://kubernetes.io/docs/tasks/tools/)** | Kommandozeilen-Client für Kubernetes |
| **PowerShell** | Das Bootstrap-Skript `crypto-data-pipeline_CD.ps1` ist PowerShell (Windows) |
| *(optional)* **Docker-Hub-Account** | Nur nötig, wenn eigene Images gebaut/gepusht werden sollen. Für den reinen Betrieb genügen die veröffentlichten `fgrothaus1/*`-Images. |

---

## Anwendung starten

### Variante A — Lokal mit Docker Compose (schnellster Einstieg)

**1. Repository klonen**

```bash
git clone https://github.com/fgrothaus/crypto-data-pipeline.git
cd crypto-data-pipeline
```

**2. `.env`-Dateien anlegen** (nicht im Repo, siehe [Konfiguration & Secrets](#konfiguration--secrets))

`services/ingestion/.env`:
```env
API_KEY=dein_coingecko_demo_api_key
RABBITMQ_CONNECTION_STRING=amqp://guest:guest@rabbitmq:5672/
```

`services/backend/.env`:
```env
REDIS_URL=redis://redis:6379
RABBITMQ_CONNECTION_STRING=amqp://guest:guest@rabbitmq:5672/
DATABASE_URL=postgresql+asyncpg://crypto_user:crypto_password@postgres:5432/crypto_db
```

> Die Postgres-Zugangsdaten müssen zu den Werten im `postgres`-Service der `docker-compose.yml` passen (`crypto_user` / `crypto_password` / `crypto_db`). Der Host ist der **Compose-Servicename** `postgres`, nicht `localhost` — die Container sprechen über das Docker-Netzwerk `crypto-network` miteinander.

**3. Hostnamen auflösbar machen**

Auf den meisten Systemen zeigt `*.localhost` bereits auf `127.0.0.1`. Falls nicht, in der Hosts-Datei ergänzen (`C:\Windows\System32\drivers\etc\hosts` bzw. `/etc/hosts`):

```
127.0.0.1 crypto.localhost api.crypto.localhost rabbitmq.localhost
```

**4. Starten**

```bash
docker compose up --build
```

**5. Öffnen**

| Was | URL |
|---|---|
| Dashboard | <http://crypto.localhost> |
| Backend-API (WebSocket + REST) | <http://api.crypto.localhost> |
| Traefik-Dashboard | <http://localhost:8080> |
| RabbitMQ-Management | <http://rabbitmq.localhost> (`guest` / `guest`) |
| PostgreSQL (z. B. DBeaver) | `localhost:5432`, DB `crypto_db` |

**6. Stoppen**

```bash
docker compose down            # Container entfernen, Volumes behalten
docker compose down -v         # inklusive Volumes (Postgres-Daten weg)
```

### Variante B — Kubernetes mit k3d + ArgoCD (der eigentliche Showcase)

**1. Die beiden lokalen Secret-Manifeste anlegen** (gitignored, siehe unten)

`k8s/ingestion/secret.yml`:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: ingestion-secret
  namespace: crypto-project
type: Opaque
stringData:
  API_KEY: "dein_coingecko_demo_api_key"
```

`k8s/postgres/secret.yml`:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secret
  namespace: crypto-project
type: Opaque
stringData:
  POSTGRES_USER: "crypto_user"
  POSTGRES_PASSWORD: "crypto_password"
  POSTGRES_DB: "crypto_db"
  DATABASE_URL: "postgresql+asyncpg://crypto_user:crypto_password@postgres:5432/crypto_db"
```

> Dieses eine Secret wird an **drei** Stellen eingebunden: Das Postgres-StatefulSet zieht daraus `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` für die Initialisierung, API- und Consumer-Deployment ziehen daraus `DATABASE_URL`. Deshalb müssen die Werte in der `DATABASE_URL` zu den drei Einzelwerten passen. `postgres` im Connection-String ist der **Kubernetes-Servicename** (`k8s/postgres/service.yml`).

**2. Bootstrap-Skript ausführen** (PowerShell)

```powershell
./crypto-data-pipeline_CD.ps1
```

Das Skript erledigt automatisch:
- ein evtl. vorhandenes Cluster `crypto-cluster` löschen,
- ein neues **k3d-Cluster** mit Port-Forwarding (`80`, `443` auf den LoadBalancer) erstellen,
- **ArgoCD** im Namespace `argocd` installieren (`--server-side`) und auf `deployment/argocd-server` warten,
- den Namespace `crypto-project` sowie **Ingestion- und Postgres-Secret** anlegen,
- die **ArgoCD-Application** (`k8s/argocd-app.yml`) anwenden.

**3. ArgoCD synchronisiert** ab jetzt den kompletten `k8s/`-Ordner rekursiv in den Cluster (Frontend, API, Consumer, Ingestion, RabbitMQ, Redis, Postgres, Ingress). Mit `selfHeal: true` und `prune: true` wird der Cluster-Zustand fortlaufend gegen Git abgeglichen: Manuelle `kubectl edit`-Änderungen werden zurückgerollt, in Git gelöschte Ressourcen werden im Cluster entfernt.

**4. Dashboard öffnen** unter <http://crypto.localhost> (Hosts-Eintrag wie oben).

**5. Optional: ArgoCD-UI ansehen**

```bash
kubectl port-forward svc/argocd-server -n argocd 8081:443
# → https://localhost:8081, Benutzer: admin

# Initial-Passwort (Base64-dekodieren):
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}"
```

**Nützliche Befehle zur Kontrolle:**

```bash
kubectl get pods -n crypto-project                          # Alle Pods
kubectl logs -f -l app=crypto-consumer -n crypto-project    # Consumer-Logs live
kubectl get ingress -n crypto-project                       # Routing prüfen
kubectl exec -it postgres-0 -n crypto-project -- psql -U crypto_user -d crypto_db \
  -c "SELECT coin_id, count(*) FROM crypto_price_history GROUP BY coin_id;"
```

---

## Konfiguration & Secrets

Alle Services lesen ihre Konfiguration ausschließlich aus **Umgebungsvariablen**:

| Variable | Verwendet von | Beispiel (Compose) | Beispiel (K8s) | Quelle im Cluster |
|---|---|---|---|---|
| `API_KEY` | ingestion | `CG-…` | `CG-…` | **Secret** `ingestion-secret` |
| `RABBITMQ_CONNECTION_STRING` | ingestion, consumer | `amqp://guest:guest@rabbitmq:5672/` | dito | ConfigMap `ingestion-config` / `backend-config` |
| `REDIS_URL` | consumer, api | `redis://redis:6379` | dito | ConfigMap `backend-config` |
| `DATABASE_URL` | consumer, api | `postgresql+asyncpg://crypto_user:…@postgres:5432/crypto_db` | dito | **Secret** `postgres-secret` |
| `POSTGRES_USER` / `_PASSWORD` / `_DB` | postgres | in `docker-compose.yml` gesetzt | — | **Secret** `postgres-secret` |
| `PYTHONUNBUFFERED` | consumer | `1` | `1` | ConfigMap `backend-config` |

**Was bewusst NICHT im Git-Repo liegt** (per `.gitignore`: `**/.env` und `*secret.yml`):

- `services/ingestion/.env`, `services/backend/.env`
- `k8s/ingestion/secret.yml`, `k8s/postgres/secret.yml`

Das ist ein didaktisch wichtiger Punkt: Kubernetes-`Secret`s sind lediglich **Base64-kodiert, nicht verschlüsselt**. Sie unverschlüsselt in ein öffentliches GitOps-Repo zu legen wäre ein Klartext-Leak. In einem echten Setup würde man hier **Sealed Secrets**, den **External Secrets Operator** oder **SOPS** einsetzen — dann könnten auch die Secrets versioniert im Repo liegen und wären trotzdem sicher. Aktuell werden sie einmalig manuell per `kubectl apply` durch das Bootstrap-Skript eingespielt.

---

## Die CI/CD-Pipeline (GitOps)

Das Projekt folgt konsequent dem **GitOps-Prinzip**: Git ist die einzige Quelle der Wahrheit. Kein Entwickler deployt in den Cluster — **ArgoCD zieht** den gewünschten Zustand aus Git (Pull statt Push). Der Cluster braucht deshalb keine Credentials nach außen und die CI keine Credentials in den Cluster.

Für jeden der drei Services gibt es einen eigenen Workflow, der über `paths:`-Filter **nur bei Änderungen im jeweiligen Serviceordner** anläuft. Eine Frontend-Änderung baut also kein Backend-Image.

```mermaid
flowchart TD
    A["👨‍💻 git push<br/>(Änderung in services/…)"] --> B["GitHub Actions Workflow<br/>(paths-Filter greift)"]
    B --> C["<b>Job 1: test-and-lint</b><br/>Ruff / ESLint / tsc<br/>pytest gegen echte<br/>Postgres- & Redis-Container"]
    C -->|"rot"| X["❌ Stopp — kein Image"]
    C -->|"grün"| D["<b>Job 2: build-and-push</b><br/>Docker Buildx →<br/>Docker Hub"]
    D --> E["Tags:<br/>:latest + :git-sha"]
    E --> F["sed ersetzt Image-Tag<br/>im K8s-Manifest"]
    F --> G["Commit & Push ins Repo<br/>Message endet auf '[skip ci]'"]
    G --> H{{"ArgoCD erkennt<br/>Git-Änderung"}}
    H --> I["Automatischer Sync<br/>Rolling Update im Cluster"]
    I --> J["✅ Änderung live"]
```

### Die drei Etappen

**1. `test-and-lint` — das Qualitäts-Gate**

- **Backend:** Der Job startet über GitHub-Actions **Service-Container** eine echte `postgres:15-alpine` (mit `pg_isready`-Healthcheck) und eine `redis:alpine`. Danach `ruff check` und `pytest` gegen diese echten Abhängigkeiten — also **Integrationstests, keine Mocks**.
- **Ingestion:** `ruff check` und `pytest` (Erreichbarkeits-/Format-Test gegen die echte CoinGecko-API).
- **Frontend:** `npm ci`, `tsc --noEmit`, `npm run lint`.

**2. `build-and-push`** — läuft über `needs: test-and-lint` **nur bei grünem Gate**. Login bei Docker Hub über GitHub-Secrets (`DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`), Build via Buildx, Push mit **zwei Tags**: `:latest` und `:${{ github.sha }}`.

**3. GitOps-Update** — per `sed` wird der neue SHA-Tag in das passende K8s-Deployment-Manifest geschrieben und mit `[skip ci]` in der Commit-Message zurück ins Repo committet.

### Warum der SHA-Tag entscheidend ist

Würde man im Manifest nur `:latest` stehen lassen, sähe ArgoCD **keine Änderung an der Git-Ressource** — das Manifest wäre byte-identisch, der Sync würde nichts tun, und der Pod liefe unbemerkt mit dem alten Image weiter. Erst der geänderte, eindeutige SHA-Tag macht das Deployment für ArgoCD sichtbar und löst ein Rolling Update aus. Nebeneffekt: Jeder laufende Pod ist eindeutig auf einen Commit rückführbar — vollständige Nachvollziehbarkeit von „was läuft gerade" zu „welcher Code ist das".

Das `[skip ci]` verhindert eine **Endlosschleife**: Der Bot-Commit würde sonst denselben Workflow erneut triggern. Das `git pull --rebase origin master` vor dem Push fängt parallele Läufe ab (z. B. wenn Backend- und Frontend-Workflow gleichzeitig committen wollen).

Der **Backend-Workflow pinnt beide Deployments** — `api-deployment.yml` *und* `consumer-deployment.yml` — da sich beide dasselbe Image teilen und gemeinsam aktualisiert werden müssen.

---

## Tests

| Suite | Datei | Was geprüft wird |
|---|---|---|
| **Backend — DB-Integration** | `services/backend/tests/test_backend.py` | `save_price_update` → `get_coin_price_history` (Roundtrip inkl. exakter Betragsprüfung); `cleanup_old_prices` schneidet korrekt auf die Obergrenze zurück (15 geschrieben → 10 behalten) |
| **Backend — API** | dito | `/live` liefert `200`; `/ready` prüft echte Redis-Verbindung; `/prices/history/unknown_coin` liefert `404` mit passender Message |
| **Ingestion — externe API** | `services/ingestion/tests/test_ingestion_integration.py` | CoinGecko ist erreichbar und liefert das erwartete Schema (`eur`, `eur_24h_change`), inkl. Plausibilitäts-Check |

Bemerkenswert ist die Testphilosophie: Die Backend-Tests laufen **gegen echte Postgres- und Redis-Instanzen** (in der CI als Service-Container, lokal gegen die Compose-Umgebung), nicht gegen Mocks. Damit werden auch Treiber-, Schema- und Connection-String-Fehler gefunden — genau die Fehlerklasse, die ein Mock per Definition nicht abdecken kann.

Lokal ausführen:

```bash
cd services/backend
$env:DATABASE_URL="postgresql+asyncpg://crypto_user:crypto_password@localhost:5432/crypto_db"
$env:REDIS_URL="redis://localhost:6379"
pytest
```

*(Voraussetzung: `docker compose up postgres redis` läuft und Redis ist auf dem Host erreichbar.)*

---

## Bekannte Punkte & Verbesserungspotenzial

Ein Portfolio-Projekt gewinnt an Glaubwürdigkeit, wenn die eigenen Schwachstellen benannt sind. Diese Liste ist bewusst vollständig:

### 🔴 Konkrete Bugs / offene Punkte

| Punkt | Beschreibung | Fix |
|---|---|---|
| **Postgres-Manifeste ohne `namespace`** | `k8s/postgres/statefulset.yml` und `service.yml` haben — anders als alle anderen Manifeste — kein `metadata.namespace`. Über ArgoCD funktioniert das (das `destination.namespace` greift), bei einem manuellen `kubectl apply -f` landen sie aber im falschen Namespace. | `namespace: crypto-project` konsistent ergänzen |
| **`requirements.txt` in UTF-16** | Beide Dateien liegen als UTF-16 mit BOM vor (Windows-Artefakt). `pip` verarbeitet sie, aber Git zeigt sie als Binärdateien an — Diffs sind dadurch nicht lesbar. | Als UTF-8 neu speichern |
| **Hostnamen fest im Frontend-Code** | `ws://api.crypto.localhost/ws/prices` und `http://api.crypto.localhost/prices/history/…` sind hart verdrahtet. Ein Deployment unter einer echten Domain erfordert eine Codeänderung. | Über `import.meta.env.VITE_API_HOST` zur Build-Zeit konfigurierbar machen |

### 🟡 Architektur & Betrieb

| Thema | Beobachtung | Empfehlung |
|---|---|---|
| **Sekunden-Polling auf Redis** | Der WebSocket-Loop liest jede Sekunde, obwohl sich der Wert nur alle 10 s ändert — und sendet auch unveränderte Daten. | Redis Pub/Sub (ereignisgetrieben) oder zumindest „nur senden, wenn geändert" |
| **Keine DB-Migrationen** | Das Schema entsteht per `create_all()`. Spätere Spaltenänderungen an einer befüllten Tabelle sind damit nicht abbildbar. | **Alembic** einführen |
| **Kein Composite-Index** | `coin_id` und `timestamp` sind einzeln indiziert. Die Hauptabfrage filtert und sortiert kombiniert. | Composite-Index `(coin_id, timestamp)` |
| **History-Endpunkt ohne Limit** | `GET /prices/history/{coin_id}` liefert immer den kompletten Verlauf. Bei aktuell max. ~1.100 Punkten je Coin unkritisch, aber unbegrenzt. | Query-Parameter `?limit=` / `?since=` ergänzen |
| **Health-Probes nur bei der API** | Consumer, Ingestion, Postgres und RabbitMQ haben keine Probes. Ein hängender Consumer würde nicht neu gestartet. | TCP-/Exec-Probes ergänzen (z. B. `pg_isready`, `rabbitmq-diagnostics ping`) |
| **`/ready` prüft Postgres nicht** | Die Readiness-Probe prüft nur Redis, obwohl die API auch von Postgres abhängt. | `SELECT 1` gegen die DB ergänzen |
| **Keine Redis-Persistenz im Cluster** | Bewusste Entscheidung (reiner Cache, Wert nach ≤10 s wieder da) — hier nur zur Klarstellung dokumentiert. | So belassen |
| **Toleranz in der Frontend-CI** | Typecheck, Lint und Test laufen mit angehängtem `\|\| true` und können die Pipeline nicht rot färben. Zudem existiert kein `test`-Script in der `package.json`. | `\|\| true` entfernen und echte Tests (Vitest + Testing Library) ergänzen |
| **CORS offen** | `allow_origins=["*"]` bei gleichzeitigem `allow_credentials=True`. | Auf die konkreten Frontend-Origins einschränken |
| **Anmeldedaten** | RabbitMQ mit `guest/guest`, Redis ohne Passwort. | Für die lokale Demo vertretbar; in der Cloud über Secrets absichern |
| **Keine Redundanz** | Überall `replicas: 1`. | Für die Demo ausreichend; API und Frontend ließen sich problemlos hochskalieren, der Consumer bewusst nicht |
| **Secrets im Klartext auf der Platte** | Die lokalen `secret.yml`-Dateien sind gitignored, aber unverschlüsselt. | Sealed Secrets / SOPS / External Secrets Operator |
| **Kein Observability-Stack** | Kein Prometheus, keine Metriken, kein zentrales Logging — Diagnose läuft über `kubectl logs` und `print()`. | Strukturiertes Logging + `prometheus-fastapi-instrumentator` + Grafana wäre der nächste logische Ausbauschritt |

### 🟢 Naheliegende Erweiterungen

- **Zweiter Consumer** auf einem Fanout-Exchange (Preis-Alarme, Minutenkerzen-Aggregation) — damit wäre RabbitMQ vollständig ausgereizt.
- **Horizontal Pod Autoscaler** für die API, gekoppelt an die Anzahl aktiver WebSocket-Verbindungen.
- **TimescaleDB** statt Plain-Postgres, wenn die Historie wirklich groß werden soll.
- **Vitest-Testsuite** fürs Frontend, damit alle drei Pipelines ein echtes Test-Gate haben.

---

## Projektstruktur

```
crypto-data-pipeline/
├── .github/workflows/              # CI/CD — GitHub Actions
│   ├── backend-ci.yml              #   Lint → Test (mit PG+Redis) → Build → Push → GitOps-Update
│   ├── frontend-ci.yml             #   Lint/Typecheck → Build → Push → GitOps-Update
│   └── ingestion-ci.yml            #   Lint → Test → Build → Push → GitOps-Update
│
├── k8s/                            # Kubernetes-Manifeste — von ArgoCD überwacht
│   ├── argocd-app.yml              #   ArgoCD Application (GitOps-Verknüpfung, ausgeschlossen vom Sync)
│   ├── namespace.yml               #   Namespace 'crypto-project'
│   ├── backend/
│   │   ├── api-deployment.yml      #     API-Pod inkl. Probes & Resource Limits
│   │   ├── api-service.yml         #     ClusterIP :8000
│   │   ├── consumer-deployment.yml #     Gleiches Image, überschriebener command
│   │   └── configmap.yml           #     REDIS_URL, RABBITMQ_CONNECTION_STRING, PYTHONUNBUFFERED
│   ├── frontend/
│   │   ├── deployment.yml          #     Nginx-Pod
│   │   ├── service.yml             #     ClusterIP :80
│   │   └── ingress.yml             #     crypto.localhost + api.crypto.localhost
│   ├── ingestion/
│   │   ├── deployment.yml
│   │   ├── configmap.yml
│   │   └── secret.yml              #     ⚠️ gitignored, lokal anlegen
│   ├── postgres/
│   │   ├── statefulset.yml         #     StatefulSet + volumeClaimTemplates (2 Gi)
│   │   ├── service.yml             #     ClusterIP :5432
│   │   └── secret.yml              #     ⚠️ gitignored, lokal anlegen
│   ├── rabbitmq/                   #   StatefulSet (+ PVC) & Service
│   └── redis/                      #   Deployment & Service
│
├── services/
│   ├── ingestion/                  # Producer: CoinGecko → RabbitMQ
│   │   ├── ingestion_main.py       #   Fetch-Loop + Reconnect-Handling
│   │   ├── models.py               #   Pydantic-Schemas
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── tests/
│   │
│   ├── backend/                    # Consumer + API — ein Image, zwei Prozesse
│   │   ├── consumer.py             #   RabbitMQ → Redis + Postgres, Cleanup-Task
│   │   ├── main.py                 #   FastAPI: WebSocket, History-REST, Health
│   │   ├── models.py               #   Pydantic-Schemas + SQLAlchemy-Modell
│   │   ├── database/
│   │   │   ├── base.py             #     DeclarativeBase
│   │   │   └── database.py         #     Async-Engine, Session-Factory, Queries
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── tests/
│   │
│   └── frontend/                   # React + Vite + TypeScript
│       ├── src/
│       │   ├── App.tsx             #   Routing
│       │   ├── pages/              #   Dashboard, CoinDetail
│       │   └── hooks/              #   useCryptoWebSockets, useCoinHistory
│       ├── nginx.conf              #   SPA-Fallback (try_files) + Cache-Header
│       ├── package.json
│       └── Dockerfile              #   Multi-Stage: node build → nginx serve
│
├── docker-compose.yml              # Lokales Debug-Setup inkl. Traefik & Postgres
├── crypto-data-pipeline_CD.ps1     # Bootstrap: k3d-Cluster + ArgoCD + Secrets
└── DOKUMENTATION.md                # Dieses Dokument
```

---

*Die Image-Tags in den K8s-Manifesten werden von der CI/CD-Pipeline automatisch auf den jeweils aktuellen Commit-SHA gesetzt und ändern sich daher laufend.*
