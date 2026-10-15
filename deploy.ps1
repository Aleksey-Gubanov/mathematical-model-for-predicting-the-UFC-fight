param([string]$Message = "update")
Set-Location $PSScriptRoot
git add -A
git commit -m $Message
git push
ssh root@201.51.30.5 "cd /root/mma && git pull && docker compose up -d --build"
Write-Host "Deploy finished" -ForegroundColor Green