param([string]$Message = "update")
Set-Location $PSScriptRoot
if ($Message -eq "tariffs") {
    git add tariffs.json
    git commit -m "update tariffs" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "No changes in tariffs.json - skip" -ForegroundColor Yellow
        exit 0
    }
    git push
    ssh root@201.51.30.5 "cd /root/mma && git pull && docker compose up -d --build"
    Write-Host "Tariffs deployed" -ForegroundColor Green
    exit 0
}
git add -A
git commit -m $Message
git push
ssh root@201.51.30.5 "cd /root/mma && git pull && docker compose up -d --build"
Write-Host "Deploy finished" -ForegroundColor Green