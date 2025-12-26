$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "`n>>> Telecom Project Sync <<<" -ForegroundColor Cyan

# Initialize git repository if needed
if (-not (Test-Path .git)) {
    Write-Host "Initializing git repository..." -ForegroundColor Yellow
    git init
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to initialize git repository!" -ForegroundColor Red
        exit 1
    }
    git branch -M main
}

# Check if remote exists, add if missing
git remote get-url origin 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Remote not found! Linking to GitHub..." -ForegroundColor Yellow
    git remote add origin https://github.com/bogachev-alex/telecom_project.git
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to add remote!" -ForegroundColor Red
        exit 1
    }
}

# Get current branch name (default to main if no commits)
$branch = git rev-parse --abbrev-ref HEAD 2>$null
if ($LASTEXITCODE -ne 0) {
    $branch = "main"
}

# Pull changes from remote (skip if first commit)
git rev-parse --verify HEAD 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Syncing with cloud..." -ForegroundColor Gray
    git pull origin $branch --rebase 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Warning: Pull failed (may be first push)" -ForegroundColor Yellow
    }
}

# Show status
git status --short

# Check if there are changes to commit
$status = git status --porcelain
if (-not $status) {
    Write-Host "No changes to commit." -ForegroundColor Gray
    exit 0
}

# Prompt for commit message
$msg = Read-Host "Commit message (empty to skip)"
if ($msg) {
    git add .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to stage files!" -ForegroundColor Red
        exit 1
    }
    
    git commit -m "$msg"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Commit failed!" -ForegroundColor Red
        exit 1
    }
    
    # Push to remote
    Write-Host "Pushing to GitHub..." -ForegroundColor Yellow
    git push -u origin $branch
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Push failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "Done!" -ForegroundColor Green
} else {
    Write-Host "Commit skipped." -ForegroundColor Gray
}