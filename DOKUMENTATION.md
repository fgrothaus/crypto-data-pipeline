# Crypto Data Pipeline — Dokumentation

Eine kleine, aber vollständige **Echtzeit-Krypto-Dashboard-Anwendung**, die live Kurse von CoinGecko einliest und im Browser anzeigt.

> [!IMPORTANT]
> **Zweck des Projekts:** Die Anwendung selbst (ein Krypto-Preis-Ticker) ist bewusst einfach gehalten. Sie dient **nur als Illustration** und ist der "Aufhänger", um einen kompletten, produktionsnahen Betriebs-Stack zu demonstrieren: **Microservices, Docker, Kubernetes (k3d), eine GitOps-CI/CD-Pipeline (GitHub Actions + ArgoCD), Message Queues (RabbitMQ), Caching (Redis) und einen Reverse Proxy / Ingress (Traefik).** Der Lerneffekt liegt im *Drumherum*, nicht in der Fachlichkeit.

---

## 📹 Video-Demo

> **Platzhalter für das Demo-Video.**
>
> Hier wird nach der Fertigstellung das Video eingebettet. Es zeigt den kompletten End-to-End-Ablauf:
>
> 1. **Start der Anwendung** (zunächst lokal via `docker-compose`).
> 2. **Hochfahren des Kubernetes-Clusters** (k3d) inkl. ArgoCD-Bootstrapping.
> 3. **Wie die laufende Anwendung im Browser aussieht** (Live-Dashboard).
> 4. **Eine Code-Änderung** wird vorgenommen und nach GitHub gepusht.
> 5. **Die CI/CD-Pipeline läuft durch** (GitHub Actions: Test → Build → Push → Manifest-Update).
> 6. **ArgoCD übernimmt die Änderung automatisch** (GitOps-Sync) und das Ergebnis wird live im Cluster sichtbar.

<!--
Video hier einfügen, z. B.:

https://github.com/fgrothaus/crypto-data-pipeline/assets/<id>/<video>.mp4

oder als Link/Thumbnail:

[![Demo ansehen](docs/video-thumbnail.png)](https://link-zum-video)
-->

---

## Inhaltsverzeichnis

1. [Was macht die Anwendung?](#was-macht-die-anwendung)
2. [Architektur & Datenfluss](#architektur--datenfluss)
3. [Die Services im Detail](#die-services-im-detail)
4. [Rolle von RabbitMQ und Redis (mit kritischer Betrachtung)](#rolle-von-rabbitmq-und-redis)
5. [Voraussetzungen](#voraussetzungen)
6. [Anwendung starten](#anwendung-starten)
7. [Die CI/CD-Pipeline (GitOps)](#die-cicd-pipeline-gitops)
8. [Kritische Gesamtbetrachtung & Verbesserungspotenzial](#kritische-gesamtbetrachtung--verbesserungspotenzial)
9. [Projektstruktur](#projektstruktur)

---

## Was macht die Anwendung?

Die Anwendung ist eine **Datenpipeline**, die in Echtzeit die Preise von sieben Kryptowährungen (Bitcoin, Ethereum, Solana, Cardano, Ripple, Polkadot, Dogecoin) in Euro anzeigt — inklusive der 24-Stunden-Veränderung.

Der Ablauf in einem Satz: Ein Service holt alle 10 Sekunden die Kurse von der **CoinGecko-API**, schickt sie durch eine **RabbitMQ-Queue**, ein zweiter Service schreibt den jeweils neuesten Stand in **Redis**, und eine **WebSocket-API** streamt diesen Stand live an ein **React-Frontend** im Browser.

---

## Architektur & Datenfluss

### Komponenten-Überblick

```mermaid
flowchart LR
    subgraph ext[Externe Welt]
        CG[("CoinGecko API<br/>simple/price")]
        Browser["🌐 Browser<br/>(User)"]
    end

    subgraph cluster["Kubernetes / Docker-Netzwerk"]
        direction LR
        ING["ingestion-service<br/><i>Producer</i>"]
        RMQ{{"RabbitMQ<br/>Queue: crypto_prices"}}
        CON["backend-consumer<br/><i>Consumer</i>"]
        RED[("Redis<br/>Key: crypto:latest_prices")]
        API["backend-api<br/>FastAPI + WebSocket"]
        FE["frontend<br/>React + Nginx"]
        TR["Traefik<br/>(Ingress / Proxy)"]
    end

    CG -->|"HTTP GET (alle 10s)"| ING
    ING -->|"AMQP publish"| RMQ
    RMQ -->|"AMQP consume"| CON
    CON -->|"SET (neuester Stand)"| RED
    API -->|"GET (1x pro Sekunde)"| RED
    Browser -->|"HTTP: crypto.localhost"| TR
    TR --> FE
    Browser -->|"WebSocket: api.crypto.localhost/ws/prices"| TR
    TR --> API
```

### Zeitlicher Ablauf (Sequenz)

```mermaid
sequenceDiagram
    participant CG as CoinGecko API
    participant ING as Ingestion
    participant RMQ as RabbitMQ
    participant CON as Consumer
    participant RED as Redis
    participant API as Backend-API
    participant FE as Frontend

    loop alle 10 Sekunden
        ING->>CG: GET /simple/price
        CG-->>ING: JSON (Kurse)
        ING->>ING: Validierung (Pydantic)
        ING->>RMQ: publish "crypto_prices" (persistent)
    end

    RMQ->>CON: deliver message
    CON->>CON: Validierung (Pydantic)
    CON->>RED: SET crypto:latest_prices

    loop jede Sekunde (pro WebSocket-Client)
        API->>RED: GET crypto:latest_prices
        RED-->>API: JSON
        API-->>FE: WebSocket send
        FE->>FE: React-State aktualisieren & rendern
    end
```

---

## Die Services im Detail

| Service | Technologie | Aufgabe |
|---|---|---|
| **ingestion-service** | Python, `httpx`, `aio-pika` | **Producer.** Fragt alle 10 s die CoinGecko-API ab, validiert die Antwort mit Pydantic und publiziert sie als persistente Nachricht in die RabbitMQ-Queue `crypto_prices`. |
| **backend-consumer** | Python, `aio-pika`, `redis` | **Consumer.** Lauscht auf der Queue `crypto_prices`, validiert jede Nachricht und schreibt den *neuesten* Stand per `SET` in den Redis-Key `crypto:latest_prices` (der alte Wert wird überschrieben). |
| **backend-api** | Python, FastAPI, `redis` | **Auslieferung.** Stellt einen WebSocket-Endpunkt `/ws/prices` bereit, der einmal pro Sekunde den Redis-Key liest und an verbundene Browser pusht. Bietet zusätzlich Health-Endpunkte `/live` (Liveness) und `/ready` (Readiness, prüft die Redis-Verbindung). |
| **frontend** | React 19, Vite, TypeScript, Nginx | **UI.** Ein „Crypto Live Dashboard". Baut per Custom-Hook (`useCryptoWebSocket`) eine WebSocket-Verbindung auf, zeigt Verbindungsstatus, Preise und 24h-Trend an. Wird als statisches Bundle von Nginx ausgeliefert. |
| **RabbitMQ** | `rabbitmq:4.0-management` | **Message Broker.** Entkoppelt Producer (Ingestion) und Consumer. Enthält ein Management-Dashboard (Port 15672). |
| **Redis** | `redis:alpine` | **Cache / Shared State.** Speichert genau einen Key mit dem aktuellen Kursstand. Puffer zwischen Consumer (schreibt) und API (liest). |
| **Traefik** | `traefik:v3` (Compose) bzw. mitgeliefert in k3d | **Reverse Proxy / Ingress.** Leitet `crypto.localhost` → Frontend und `api.crypto.localhost` → Backend-API. |
| **ArgoCD** | `argoproj/argo-cd` | **GitOps-Controller** (nur im Kubernetes-Setup). Überwacht den `k8s/`-Ordner im Git-Repo und gleicht den Cluster-Zustand automatisch daran an. |

> **Warum ist das Backend in zwei Teile (Consumer + API) aufgeteilt?**
> Beide teilen sich denselben Code und dasselbe Docker-Image, laufen aber als **zwei getrennte Prozesse/Pods**: Der Consumer verarbeitet den Nachrichtenstrom (schreibend Richtung Redis), die API liefert an die Clients aus (lesend). Dadurch könnte man beide **unabhängig skalieren** — z. B. mehrere API-Repliken für viele Browser-Verbindungen, während ein einzelner Consumer genügt.

---

## Rolle von RabbitMQ und Redis

### Redis — als Cache / „Latest Value Store"

Redis wird hier als **schneller, gemeinsamer Zwischenspeicher** genutzt. Der Consumer schreibt den jeweils aktuellen Kursstand unter einem einzigen Key (`crypto:latest_prices`), die API liest ihn dort aus. Redis entkoppelt so den *schreibenden* vom *lesenden* Pfad: Egal wie viele Browser verbunden sind, sie belasten nie die Ingestion oder RabbitMQ, sondern lesen nur den zwischengespeicherten Wert. Das ist ein **sinnvoller und passender** Einsatz von Redis.

*Kleiner Hinweis:* Die API liest im WebSocket-Loop **jede Sekunde per Polling** aus Redis — auch wenn sich nichts geändert hat. Für dieses Demo-Volumen völlig unkritisch; eleganter wäre **Redis Pub/Sub** (Consumer publiziert bei Änderung, API wird benachrichtigt), womit man das Sekunden-Polling einsparen könnte.

### RabbitMQ — Message Broker

RabbitMQ entkoppelt den **Producer** (Ingestion) vom **Consumer**. Der Producer publiziert Nachrichten in eine `durable` Queue mit `PERSISTENT`-Nachrichten; der Consumer verarbeitet sie und bestätigt sie (`message.process()`).

#### ⚠️ Kritische Betrachtung: Ist RabbitMQ hier wirklich sinnvoll?

Diese Frage ist berechtigt — und die ehrliche Antwort lautet: **Für die reine Fachlichkeit ist RabbitMQ hier überdimensioniert.** Die Gründe:

- **Nur der neueste Wert zählt.** Der Consumer macht nichts anderes als `SET` auf *einen* Redis-Key — jede neue Nachricht überschreibt die vorherige. Es gibt keine Historie, keine Aggregation, keine Weiterverarbeitung einzelner Nachrichten. Ein garantiert-vollständiger, geordneter Nachrichtenstrom (die Kernstärke von RabbitMQ) wird also gar nicht gebraucht.
- **`durable` + `PERSISTENT` wirkt hier sogar kontraproduktiv.** Fällt der Consumer aus und stauen sich Nachrichten in der Queue, arbeitet er nach dem Neustart erst *veraltete* Kurse ab, bevor er den aktuellen erreicht. Bei „nur der letzte Wert zählt" möchte man genau das *nicht* — man will sofort den neuesten Stand.
- **Ein einziger Producer, ein einziger Consumer, kein Routing, kein Fan-out.** Klassische RabbitMQ-Szenarien (Arbeitsverteilung auf viele Worker, komplexes Topic-Routing, Publish/Subscribe an mehrere Abnehmer) kommen nicht vor.
- **Die Alternative wäre schlanker:** Die Ingestion könnte den Wert direkt nach Redis schreiben, oder man nutzt **Redis Pub/Sub** — beides würde eine komplette Infrastruktur-Komponente einsparen.

**Wann RabbitMQ trotzdem die richtige Wahl wäre** (und wie man den Einsatz rechtfertigt):

- Als **bewusster Lern-/Demonstrationsbaustein** — genau das ist der erklärte Zweck dieses Projekts. Es zeigt, *dass* und *wie* man einen Message Broker in K8s als `StatefulSet` mit `PersistentVolume` betreibt.
- Als **Vorbereitung auf realistische Erweiterungen:** Sobald mehrere Consumer denselben Strom unterschiedlich verarbeiten sollen (z. B. einer schreibt in Redis, einer in eine Zeitreihen-DB für Charts, einer erkennt Preis-Alarme), spielt RabbitMQ mit Fan-out/Routing seine Stärke aus.
- Zur **echten Entkopplung von Lastspitzen**, wenn Producer deutlich schneller liefern als Consumer verarbeiten kann (hier nicht der Fall, da nur alle 10 s eine kleine Nachricht kommt).

> **Fazit:** Für den *illustrativen* Zweck ist RabbitMQ gerechtfertigt und didaktisch wertvoll. Für die *tatsächliche Fachlichkeit* dieser Anwendung wäre es weglassbar; ehrlicherweise sollte man es als „bewusst eingebaut, um den Umgang mit Message Brokern zu zeigen" deklarieren — nicht als technisch zwingend notwendig. Wenn man den Nutzen echt machen möchte, wäre die naheliegende Erweiterung ein zweiter Consumer, der eine Kurshistorie persistiert.

---

## Voraussetzungen

Je nachdem, ob du **nur lokal** (Docker Compose) oder das **komplette Kubernetes-Setup** ausprobieren willst, brauchst du unterschiedlich viel.

### Für alle Varianten

| Tool | Zweck |
|---|---|
| **Git** | Repository klonen |
| **Docker Desktop** (Windows/Mac) bzw. Docker Engine | Container-Runtime; Basis für alles Weitere |
| **CoinGecko Demo-API-Key** | Kostenlos unter <https://www.coingecko.com/en/api> registrieren. Wird für die Ingestion benötigt. |

### Zusätzlich für das lokale Compose-Setup

- **Docker Compose** (ist in Docker Desktop enthalten).

### Zusätzlich für das Kubernetes-Setup

| Tool | Zweck |
|---|---|
| **[k3d](https://k3d.io/)** | Erzeugt ein leichtgewichtiges Kubernetes-Cluster (k3s) in Docker. |
| **[kubectl](https://kubernetes.io/docs/tasks/tools/)** | Kommandozeilen-Client für Kubernetes. |
| **PowerShell** | Das Bootstrap-Skript `crypto-data-pipeline_CD.ps1` ist in PowerShell geschrieben (Windows). |
| *(optional)* **Docker Hub Account** | Nur nötig, wenn du **eigene** Images bauen/pushen willst. Für den reinen Betrieb reichen die bereits veröffentlichten `fgrothaus1/*`-Images. |

> **Hinweis zu Secrets:** Zwei Dinge liegen **bewusst nicht im Git-Repo** und müssen lokal angelegt werden:
> - `.env`-Dateien für die Services (Compose-Setup)
> - `k8s/ingestion/secret.yml` (Kubernetes-Setup)
>
> Siehe die Details im nächsten Abschnitt.

---

## Anwendung starten

### Variante A — Lokal mit Docker Compose (schnellster Einstieg)

1. **Repository klonen:**
   ```bash
   git clone https://github.com/fgrothaus/crypto-data-pipeline.git
   cd crypto-data-pipeline
   ```

2. **`.env`-Dateien anlegen** (werden von `docker-compose.yml` erwartet):

   `services/ingestion/.env`:
   ```env
   API_KEY=dein_coingecko_demo_api_key
   RABBITMQ_CONNECTION_STRING=amqp://guest:guest@rabbitmq:5672/
   ```

   `services/backend/.env`:
   ```env
   REDIS_URL=redis://redis:6379
   RABBITMQ_CONNECTION_STRING=amqp://guest:guest@rabbitmq:5672/
   ```

3. **`crypto.localhost` / `api.crypto.localhost` auflösbar machen.**
   Unter den meisten Systemen zeigt `*.localhost` bereits auf `127.0.0.1`. Falls nicht, ergänze in der Hosts-Datei
   (`C:\Windows\System32\drivers\etc\hosts` bzw. `/etc/hosts`):
   ```
   127.0.0.1 crypto.localhost api.crypto.localhost rabbitmq.localhost
   ```

4. **Starten:**
   ```bash
   docker compose up --build
   ```

5. **Öffnen im Browser:**
   - Dashboard: <http://crypto.localhost>
   - Backend-API (WebSocket-Host): <http://api.crypto.localhost>
   - Traefik-Dashboard: <http://localhost:8080>
   - RabbitMQ-Management: <http://rabbitmq.localhost> (Login `guest` / `guest`)

6. **Stoppen:**
   ```bash
   docker compose down
   ```

### Variante B — Kubernetes mit k3d + ArgoCD (der eigentliche Showcase)

1. **CoinGecko-Secret als Kubernetes-Manifest anlegen** — `k8s/ingestion/secret.yml` (nicht im Repo enthalten):
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

2. **Bootstrap-Skript ausführen** (PowerShell):
   ```powershell
   ./crypto-data-pipeline_CD.ps1
   ```
   Das Skript erledigt automatisch:
   - ein evtl. vorhandenes Cluster `crypto-cluster` löschen,
   - ein neues **k3d-Cluster** mit Port-Forwarding (`80`, `443`) erstellen,
   - **ArgoCD** im Namespace `argocd` installieren und auf dessen Bereitschaft warten,
   - den Namespace `crypto-project` und das **Ingestion-Secret** anlegen,
   - die **ArgoCD-Application** (`k8s/argocd-app.yml`) anwenden, die ab jetzt den `k8s/`-Ordner überwacht.

3. **ArgoCD synchronisiert automatisch** den kompletten `k8s/`-Ordner in den Cluster (Frontend, Backend-API, Consumer, Ingestion, RabbitMQ, Redis, Ingress). Dank `selfHeal: true` und `prune: true` wird der Cluster-Zustand fortlaufend mit Git abgeglichen.

4. **`crypto.localhost` in der Hosts-Datei** wie oben eintragen und das Dashboard unter <http://crypto.localhost> öffnen.

5. *(Optional)* **ArgoCD-Oberfläche ansehen:**
   ```bash
   kubectl port-forward svc/argocd-server -n argocd 8081:443
   # dann https://localhost:8081 öffnen
   # Initial-Passwort:
   kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}"
   # (Base64-dekodieren) — Benutzer: admin
   ```

---

## Die CI/CD-Pipeline (GitOps)

Das Projekt folgt dem **GitOps-Prinzip**: Git ist die *einzige Quelle der Wahrheit*. Nicht der Entwickler deployt in den Cluster, sondern **ArgoCD zieht** den gewünschten Zustand aus Git.

Für jeden der drei Services (`frontend`, `backend`, `ingestion`) gibt es einen eigenen GitHub-Actions-Workflow, der **nur** anläuft, wenn sich Dateien im jeweiligen Service-Ordner ändern (`paths:`-Filter).

```mermaid
flowchart TD
    A["👨‍💻 Entwickler: git push<br/>(Änderung in services/…)"] --> B[GitHub Actions Workflow startet]
    B --> C["Job 1: Test & Lint<br/>(Ruff / ESLint / tsc / pytest)"]
    C -->|grün| D["Job 2: Docker Build & Push<br/>Tags: :latest + :git-sha"]
    D --> E["Image-Tag im K8s-Manifest<br/>per sed ersetzen (git-sha)"]
    E --> F["Commit & Push zurück ins Repo<br/>'[skip ci]'"]
    F --> G{{"ArgoCD erkennt<br/>Git-Änderung"}}
    G --> H["Automatischer Sync:<br/>neues Image im Cluster"]
    H --> I["✅ Änderung live sichtbar"]
```

**Die Etappen eines Workflows:**

1. **Test & Lint** — Python-Services werden mit `ruff` gelintet, das Frontend mit `eslint` und `tsc --noEmit` geprüft; Tests laufen via `pytest` bzw. `npm test`.
2. **Build & Push** — nur wenn Etappe 1 grün ist (`needs: test-and-lint`), wird das Docker-Image gebaut und mit **zwei Tags** (`:latest` und der eindeutigen `:${{ github.sha }}`) zu Docker Hub gepusht.
3. **GitOps-Update** — per `sed` wird der neue, SHA-basierte Image-Tag ins passende K8s-Deployment-Manifest geschrieben und mit `[skip ci]` zurück ins Repo committet. Dieser Commit ist der **Trigger für ArgoCD**, das die neue Version anschließend automatisch in den Cluster ausrollt.

Der SHA-Tag (statt nur `:latest`) ist wichtig: Erst durch den **geänderten Tag im Manifest** erkennt ArgoCD überhaupt, dass sich etwas geändert hat, und rollt gezielt und nachvollziehbar aus.

---

## Kritische Gesamtbetrachtung & Verbesserungspotenzial

Das Projekt ist als Lern- und Demo-Umgebung **sehr gut aufgebaut** und deckt einen realistischen DevOps-Stack ab. Ein paar Punkte, die man in einem „echten" Betrieb anders lösen würde (und die auch als Ausblick spannend sind):

| Thema | Beobachtung | Empfehlung |
|---|---|---|
| **RabbitMQ-Nutzen** | Nur „letzter Wert zählt" → Broker fachlich überdimensioniert (siehe [oben](#rolle-von-rabbitmq-und-redis)). | Als Demo ok; für echten Nutzen einen zweiten Consumer (z. B. Kurshistorie) ergänzen — oder durch Redis Pub/Sub ersetzen. |
| **Consumer-Deployment nicht in GitOps-Update** | `consumer-deployment.yml` nutzt `:latest`; nur `api-deployment.yml` wird von der Backend-CI per `sed` gepinnt. Der Consumer bekommt so **keinen automatischen, nachvollziehbaren Rollout** (ArgoCD sieht keinen Tag-Wechsel). | Auch das Consumer-Manifest im Workflow auf den SHA-Tag umstellen. |
| **Health-Probes nur bei der API** | Consumer und Ingestion haben keine Liveness-/Readiness-Probes. | Einfache TCP-/Prozess-Probes ergänzen, damit K8s hängende Pods neu startet. |
| **Redis ohne Persistenz in K8s** | Das Redis-Deployment hat kein PersistentVolume (im Gegensatz zu Compose). Als reiner Cache akzeptabel — der Wert wird ohnehin alle 10 s neu geschrieben. | Für reinen Cache ok; bewusst dokumentieren. |
| **Sekunden-Polling der API auf Redis** | WebSocket-Loop liest jede Sekunde, auch ohne Änderung, und sendet immer. | Redis Pub/Sub oder Vergleich „nur senden, wenn geändert". |
| **CI-Toleranz** | Tests/Typecheck laufen mit `|| true` und werden nicht erzwungen; zudem existiert kein `npm test`-Script im Frontend. | Sobald echte Tests existieren, `|| true` entfernen, damit die Pipeline bei Fehlern rot wird. |
| **Feste Hostnamen im Frontend** | Die WebSocket-URL `ws://api.crypto.localhost/...` ist hart im Code (`App.tsx`) verdrahtet. | Über Build-Zeit-Env-Variable (`VITE_...`) konfigurierbar machen. |
| **Einzelne Repliken / keine HA** | Überall `replicas: 1`. | Für Demo völlig ausreichend; für „echte" HA API/Frontend hochskalieren. |
| **Anmeldedaten** | RabbitMQ läuft mit `guest/guest`; Redis ohne Passwort. | Für lokale Demo ok, in der Cloud durch Secrets/Auth absichern. |

---

## Projektstruktur

```
crypto-data-pipeline/
├── .github/workflows/          # CI/CD-Pipelines (GitHub Actions)
│   ├── backend-ci.yml          #   Test → Build → Push → GitOps-Update (Backend)
│   ├── frontend-ci.yml         #   dito (Frontend)
│   └── ingestion-ci.yml        #   dito (Ingestion)
├── k8s/                        # Kubernetes-Manifeste (von ArgoCD überwacht)
│   ├── argocd-app.yml          #   ArgoCD Application (GitOps-Verknüpfung)
│   ├── namespace.yml           #   Namespace 'crypto-project'
│   ├── backend/                #   API-Deployment+Service, Consumer-Deployment, ConfigMap
│   ├── frontend/               #   Deployment, Service, Ingress
│   ├── ingestion/              #   Deployment, ConfigMap (Secret liegt lokal!)
│   ├── rabbitmq/               #   StatefulSet (+ PVC) & Service
│   └── redis/                  #   Deployment & Service
├── services/
│   ├── ingestion/              # Producer: CoinGecko → RabbitMQ
│   │   ├── ingestion_main.py
│   │   ├── models.py           #   Pydantic-Validierung
│   │   └── Dockerfile
│   ├── backend/                # Consumer + API (ein Image, zwei Prozesse)
│   │   ├── consumer.py         #   RabbitMQ → Redis
│   │   ├── main.py             #   FastAPI: WebSocket + Health-Checks
│   │   ├── models.py
│   │   └── Dockerfile
│   └── frontend/               # React + Vite + TypeScript, ausgeliefert via Nginx
│       ├── src/App.tsx
│       ├── src/hooks/useCryptoWebSockets.ts
│       └── Dockerfile
├── docker-compose.yml          # Lokales Setup (inkl. Traefik-Proxy)
├── crypto-data-pipeline_CD.ps1 # Bootstrap: k3d-Cluster + ArgoCD
└── DOKUMENTATION.md            # Dieses Dokument
```

---

*Diese Dokumentation beschreibt den Stand des Repositorys zum Zeitpunkt der Erstellung. Da die CI/CD-Pipeline die Image-Tags in den K8s-Manifesten automatisch aktualisiert, können sich die konkreten `:git-sha`-Werte laufend ändern.*
