# crypto-data-pipeline

crypto-data-pipeline/
├── .github/workflows/    # Deine GitHub Actions (CI/CD)
├── traefik/              # Traefik-Konfiguration
├── k8s/                  # Kubernetes-Manifeste
├── services/
│   ├── ingestion/        # FastAPI 1: Holt Daten von CoinGecko -> Pusht zu RabbitMQ
│   ├── backend/          # FastAPI 2: Holt Daten aus RabbitMQ -> Liefert an Frontend
│   └── frontend/         # Vite + React App
└── docker-compose.yml    # Lokales Orchestrierungs-Setup