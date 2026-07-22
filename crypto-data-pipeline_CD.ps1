$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Starte k3d & ArgoCD Bootstrapping (Home Setup)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Altes Cluster aufräumen, falls vorhanden
$clusterExists = k3d cluster list | Select-String "crypto-cluster"
if ($clusterExists) {
    Write-Host "Lösche altes Cluster 'crypto-cluster'..." -ForegroundColor Yellow
    k3d cluster delete crypto-cluster
}

# k3d Cluster mit Port-Forwarding erstellen
Write-Host "Erstelle Cluster..." -ForegroundColor Green
k3d cluster create crypto-cluster `
    -p "80:80@loadbalancer" `
    -p "443:443@loadbalancer"


Start-Sleep -Seconds 8
$ErrorActionPreference = "Continue"


# ArgoCD Namespace & Manifeste installieren
Write-Host "Installiere ArgoCD Core-Komponenten..." -ForegroundColor Green
kubectl create namespace argocd 2>$null
kubectl apply -n argocd --server-side --validate=false -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

Write-Host "Warte, bis ArgoCD hochgefahren ist..." -ForegroundColor Yellow
kubectl wait --for=condition=available deployment/argocd-server -n argocd --timeout=300s

# Lokales Secret vorab anlegen (falls noch nicht in Git)
Write-Host "Wende lokales Ingestion-Secret an..." -ForegroundColor Green
kubectl create namespace crypto-project 2>$null
kubectl apply -f k8s/ingestion/secret.yml

# GitOps Application verknüpfen
Write-Host "Verknüpfe ArgoCD mit deiner GitHub-Pipeline..." -ForegroundColor Green
kubectl apply -f k8s/argocd-app.yml

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "FINISH! Das Cluster läuft & ArgoCD synchronisiert!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan