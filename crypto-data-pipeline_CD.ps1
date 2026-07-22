# crypto-data-pipeline_CD.ps1
$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🚀 Starte k3d & ArgoCD Bootstrapping (Home Setup)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Altes Cluster aufräumen, falls vorhanden
$clusterExists = k3d cluster list | Select-String "crypto-cluster"
if ($clusterExists) {
    Write-Host "🧹 Lösche altes k3d Cluster 'crypto-cluster'..." -ForegroundColor Yellow
    k3d cluster delete crypto-cluster
}

# 2. Frisches k3d Cluster mit Port-Forwarding erstellen
Write-Host "🏗️ Erstelle k3d Cluster..." -ForegroundColor Green
k3d cluster create crypto-cluster `
    -p "80:80@loadbalancer" `
    -p "443:443@loadbalancer"

# Kurze Pause, damit die K8s API vollständig da ist
Start-Sleep -Seconds 8

# Ab hier lockern wir die ErrorAction, damit reine stderr-Warnungen das Skript nicht killen
$ErrorActionPreference = "Continue"

# 3. ArgoCD Namespace & Manifeste installieren (--server-side löst das CRD-Size-Limit)
Write-Host "📦 Installiere ArgoCD Core-Komponenten..." -ForegroundColor Green
kubectl create namespace argocd 2>$null
kubectl apply -n argocd --server-side --validate=false -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# 4. Warten, bis der ArgoCD-Server bereit ist
Write-Host "⏳ Warte, bis ArgoCD hochgefahren ist (kann bis zu 2 Min. dauern)..." -ForegroundColor Yellow
kubectl wait --for=condition=available deployment/argocd-server -n argocd --timeout=300s

# 5. Lokales Secret vorab anlegen (falls noch nicht in Git)
Write-Host "🔐 Wende lokales Ingestion-Secret an..." -ForegroundColor Green
kubectl create namespace crypto-project 2>$null
kubectl apply -f k8s/ingestion/secret.yml

# 6. GitOps Application verknüpfen
Write-Host "🔗 Verknüpfe ArgoCD mit deiner GitHub-Pipeline..." -ForegroundColor Green
kubectl apply -f k8s/argocd-app.yml

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🎉 FINISH! Das Cluster läuft & ArgoCD synchronisiert!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan