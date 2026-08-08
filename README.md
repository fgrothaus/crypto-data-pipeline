

# Crypto Data Pipeline

**Eine Echtzeit-Datenpipeline für Kryptowährungskurse — von der externen API bis in den Browser, betrieben als Microservices auf Kubernetes mit vollautomatischer GitOps-Deployment-Kette.**

---

> [!IMPORTANT]
> **Zweck des Projekts (Portfolio-Kontext)**
>
> Die Fachlichkeit (ein Krypto-Preis-Ticker) ist bewusst schlank gehalten. Sie ist der *Aufhänger*, um einen vollständigen, produktionsnahen Stack zu demonstrieren:
>
> **Asynchrones Python (asyncio) · Message Broker (RabbitMQ) · In-Memory-Cache (Redis) · relationale Persistenz (PostgreSQL + SQLAlchemy 2.0 async) · WebSockets für Server-Push · REST für historische Abfragen · React/TypeScript-SPA · Docker & Multi-Stage-Builds · Kubernetes (k3d) mit Deployments, StatefulSets, Services, Ingress, ConfigMaps, Secrets, Probes & Resource Limits · Reverse Proxy (Traefik) · CI mit GitHub Actions · CD nach dem GitOps-Prinzip mit ArgoCD.**
>
> Der Lerneffekt liegt im *Drumherum*, nicht in der Domäne — die Domäne ist aber bewusst so gewählt, dass sie einen echten Datenstrom erzeugt und damit alle Bausteine sinnvoll unter Last setzt.

---

## 📹 Video-Demo

[![Video Demo](https://img.shields.io/badge/▶_Video_Demo-Ansehen-blue?style=for-the-badge)](https://github.com/fgrothaus/crypto-data-pipeline/releases/download/v1.0.0/crypto-data-pipeline.mp4)


https://github.com/user-attachments/assets/8b77736e-dc0a-490b-8c4d-96905931b9fc


---

## Inhaltsverzeichnis

1. [Was macht die Anwendung?](#was-macht-die-anwendung)
2. [Tech-Stack im Überblick](#tech-stack-im-überblick)
3. [Architektur & Datenfluss](#architektur--datenfluss)
4. [Die Services im Detail](#die-services-im-detail)
5. [Voraussetzungen](#voraussetzungen)
6. [Anwendung starten](#anwendung-starten)
7. [Die CI/CD-Pipeline (GitOps)](#die-cicd-pipeline-gitops)
8. [Tests](#tests)
9. [Projektstruktur](#projektstruktur)

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
| **Tests** | **pytest** + **pytest-asyncio** | Integrationstests gegen echte Redis-/Postgres-Service-Container in der CI |
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

---

## Die Services im Detail

| Service | Rolle | Kerntechnologien | Beschreibung |
|---|---|---|---|
| **ingestion-service** | Producer | `httpx`, `aio-pika`, Pydantic | Fragt alle 10 s die CoinGecko-API ab (API-Key im Header `x-cg-demo-api-key`), validiert die Antwort gegen `PriceUpdate` und publiziert sie als **persistente** Nachricht in die durable Queue `crypto_prices`. Enthält eine **Reconnect-Schleife**: Bricht die AMQP-Verbindung ab, wird nach 5 s neu verbunden statt den Prozess sterben zu lassen. |
| **backend-consumer** | Consumer / Writer | `aio-pika`, `redis.asyncio`, SQLAlchemy async | Lauscht auf `crypto_prices`. Pro Nachricht: (1) Validierung, (2) `SET` auf den Redis-Key `crypto:latest_prices`, (3) `INSERT` je Coin nach Postgres. Startet zusätzlich einen **Cleanup-Task**, der minütlich die Tabelle auf eine Obergrenze an Zeilen zurückschneidet. Wartet beim Start in einer Retry-Schleife auf RabbitMQ und legt danach das DB-Schema an. |
| **backend-api** | Reader / Auslieferung | FastAPI, Uvicorn, `redis.asyncio`, SQLAlchemy async | Stellt den WebSocket `/ws/prices` (Push aus Redis), den REST-Endpunkt `/prices/history/{coin_id}` (Lesen aus Postgres) sowie `/live` und `/ready` bereit. CORS ist offen (`allow_origins=["*"]`), da das Frontend unter einem anderen Host läuft. |
| **frontend** | UI | React 19, TS, Vite, react-router, Recharts | SPA mit zwei Routen. Dashboard konsumiert den WebSocket, Detailseite den REST-Endpunkt. |
| **RabbitMQ** | Message Broker | `rabbitmq:4.0-management` | Entkoppelt Producer und Consumer. Management-UI auf Port 15672. Im Cluster als **StatefulSet mit PVC**. |
| **Redis** | Cache | `redis:alpine` | Ein einziger Key mit dem aktuellen Stand. Bewusst **ohne Persistenz** im Cluster — der Wert ist nach spätestens 10 s ohnehin wieder da. |
| **PostgreSQL** | Persistenz | `postgres:16-alpine` | Zeitreihe der Kurse. Im Cluster als **StatefulSet mit `volumeClaimTemplates`** (2 Gi), lokal als Compose-Service mit nach außen gemapptem Port 5432 (für DBeaver o. ä.). |
| **Traefik** | Ingress | `traefik:v3` bzw. k3s-eigener Controller | Bei k3s/k3d bereits als Ingress Controller enthalten |
| **ArgoCD** | GitOps-Controller | `argoproj/argo-cd` | Überwacht den `k8s/`-Ordner im Repo und gleicht den Cluster fortlaufend daran an. |


### Datenmodell (PostgreSQL)

Tabelle `crypto_price_history`, definiert in `services/backend/models.py`:

| Spalte | Typ | Anmerkung |
|---|---|---|
| `id` | `Integer`, PK | Autoincrement, indiziert |
| `coin_id` | `String(50)`, `NOT NULL` | **indiziert** — die History-Abfrage filtert darauf |
| `symbol` | `String(10)`, `NOT NULL` | Abgeleitet aus den ersten drei Zeichen der `coin_id` |
| `name` | `String(100)`, `NOT NULL` | Abgeleitet aus `coin_id.capitalize()` |
| `price_eur` | `Numeric(18, 8)`, `NOT NULL` | **`Numeric` statt `Float`** |
| `timestamp` | `DateTime(timezone=True)` | Default `datetime.now(timezone.utc)`, **indiziert** — die Abfrage sortiert danach |

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

**2. `.env`-Dateien anlegen** (nicht im Repo)

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

**3. Starten**

```bash
docker compose up --build
```

**4. Öffnen**

| Was | URL |
|---|---|
| Dashboard | <http://crypto.localhost> |
| Backend-API Docs | <http://api.crypto.localhost/docs> |

**5. Stoppen**

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

**Nützliche Befehle zur Kontrolle:**

```bash
kubectl get pods -n crypto-project                          # Alle Pods
kubectl logs -f -l app=crypto-consumer -n crypto-project    # Consumer-Logs live
kubectl get ingress -n crypto-project                       # Routing prüfen
kubectl exec -it postgres-0 -n crypto-project -- psql -U crypto_user -d crypto_db \
  -c "SELECT coin_id, count(*) FROM crypto_price_history GROUP BY coin_id;"
```

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

---

## Tests

| Suite | Datei | Was geprüft wird |
|---|---|---|
| **Backend — DB-Integration** | `services/backend/tests/test_backend.py` | `save_price_update` → `get_coin_price_history` (Roundtrip inkl. exakter Betragsprüfung); `cleanup_old_prices` schneidet korrekt auf die Obergrenze zurück (15 geschrieben → 10 behalten) |
| **Backend — API** | `services/backend/tests/test_backend.py` | `/live` liefert `200`; `/ready` prüft echte Redis-Verbindung; `/prices/history/unknown_coin` liefert `404` mit passender Message |
| **Ingestion — externe API** | `services/ingestion/tests/test_ingestion_integration.py` | CoinGecko ist erreichbar und liefert das erwartete Schema (`eur`, `eur_24h_change`), inkl. Plausibilitäts-Check |

---

## Projektstruktur

```text
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
