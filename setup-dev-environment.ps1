# OnMemOS v3 Development Environment Setup Script for Windows
# Run this script to set up your development environment

Write-Host "🚀 Setting up OnMemOS v3 Development Environment" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin) {
    Write-Host "⚠️  This script should be run as Administrator for best results" -ForegroundColor Yellow
}

# Install system dependencies using winget
Write-Host "📦 Installing system dependencies..." -ForegroundColor Cyan

$packages = @(
    "Google.CloudSDK",
    "Kubernetes.kubectl",
    "Docker.DockerDesktop"
)

foreach ($package in $packages) {
    Write-Host "Installing $package..." -ForegroundColor Yellow
    winget install $package --accept-package-agreements --accept-source-agreements
}

Write-Host "✅ System dependencies installed!" -ForegroundColor Green

# Instructions for manual setup
Write-Host "`n📋 Manual Setup Steps:" -ForegroundColor Cyan
Write-Host "1. Restart your terminal/PowerShell to refresh PATH" -ForegroundColor White
Write-Host "2. Authenticate with Google Cloud:" -ForegroundColor White
Write-Host "   gcloud auth login" -ForegroundColor Gray
Write-Host "   gcloud auth application-default login" -ForegroundColor Gray
Write-Host "3. Set your project:" -ForegroundColor White
Write-Host "   gcloud config set project ai-engine-448418" -ForegroundColor Gray
Write-Host "4. Install GKE auth plugin:" -ForegroundColor White
Write-Host "   gcloud components install gke-gcloud-auth-plugin" -ForegroundColor Gray
Write-Host "5. Set up kubectl context for your cluster:" -ForegroundColor White
Write-Host "   gcloud container clusters get-credentials onmemos-autopilot --region us-central1" -ForegroundColor Gray
Write-Host "   # OR for the other cluster:" -ForegroundColor Gray
Write-Host "   gcloud container clusters get-credentials imru-cluster --region us-central1" -ForegroundColor Gray
Write-Host "6. Verify kubectl connection:" -ForegroundColor White
Write-Host "   kubectl get nodes" -ForegroundColor Gray
Write-Host "7. Install Python dependencies:" -ForegroundColor White
Write-Host "   pip install -r requirements.txt" -ForegroundColor Gray
Write-Host "8. Install Starbase SDK:" -ForegroundColor White
Write-Host "   pip install -e starbase_local/" -ForegroundColor Gray
Write-Host "9. Configure your .env file with correct Windows paths" -ForegroundColor White

Write-Host "`n🎉 Setup complete! Follow the manual steps above." -ForegroundColor Green




