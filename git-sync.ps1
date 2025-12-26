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

# Show status
Write-Host "`nCurrent status:" -ForegroundColor Cyan
git status --short

# Prompt for action choice
Write-Host "`nWhat would you like to do?" -ForegroundColor Yellow
Write-Host "  1) Pull - Get latest changes from remote" -ForegroundColor White
Write-Host "  2) Push - Commit and push local changes" -ForegroundColor White
$choice = Read-Host "`nEnter choice (1 or 2)"

if ($choice -eq "1") {
    # PULL MODE
    Write-Host "`n>>> Pulling from remote <<<" -ForegroundColor Cyan
    
    # Check if remote tracking branch exists
    $remoteBranch = git ls-remote --heads origin $branch 2>$null
    $remoteExists = $LASTEXITCODE -eq 0 -and $remoteBranch
    
    # Check if we have local commits
    git rev-parse --verify HEAD 2>$null | Out-Null
    $hasLocalCommits = $LASTEXITCODE -eq 0
    
    if ($remoteExists) {
        # Handle untracked files that might conflict with incoming changes
        # First, fetch to see what would come in
        Write-Host "Fetching remote changes..." -ForegroundColor Gray
        git fetch origin $branch 2>$null
        
        # Check for untracked files that might conflict
        $untrackedFiles = git ls-files --others --exclude-standard
        if ($untrackedFiles) {
            Write-Host "Found untracked files. Adding them to git to prevent conflicts..." -ForegroundColor Yellow
            git add .
            if ($LASTEXITCODE -eq 0) {
                # Only commit if we have local commits, otherwise just stage them
                if ($hasLocalCommits) {
                    git commit -m "Add local untracked files before pull" 2>$null
                    if ($LASTEXITCODE -eq 0) {
                        Write-Host "Committed untracked files." -ForegroundColor Green
                    }
                } else {
                    Write-Host "Staged untracked files (will be included in first commit)." -ForegroundColor Green
                }
            }
        }
        
        Write-Host "Pulling latest changes from '$branch'..." -ForegroundColor Yellow
        if ($hasLocalCommits) {
            # Normal pull with rebase if we have local commits
            git pull origin $branch --rebase
        } else {
            # First pull - allow unrelated histories if needed
            Write-Host "No local commits yet. Pulling from remote..." -ForegroundColor Gray
            git pull origin $branch --allow-unrelated-histories
            if ($LASTEXITCODE -ne 0) {
                # Try without allow-unrelated-histories (might be same history)
                git pull origin $branch
            }
        }
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: Pull failed. You may need to resolve conflicts manually." -ForegroundColor Red
            exit 1
        } else {
            Write-Host "Successfully pulled latest changes." -ForegroundColor Green
            Write-Host "`nUpdated status:" -ForegroundColor Cyan
            git status --short
        }
    } else {
        Write-Host "Remote branch '$branch' doesn't exist yet (first push needed)." -ForegroundColor Yellow
    }
} elseif ($choice -eq "2") {
    # PUSH MODE
    Write-Host "`n>>> Pushing to remote <<<" -ForegroundColor Cyan
    
    # Pull first to sync with remote
    git rev-parse --verify HEAD 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $remoteBranch = git ls-remote --heads origin $branch 2>$null
        if ($LASTEXITCODE -eq 0 -and $remoteBranch) {
            Write-Host "Pulling latest changes before push..." -ForegroundColor Yellow
            git pull origin $branch --rebase
            if ($LASTEXITCODE -ne 0) {
                Write-Host "Error: Pull failed. Please resolve conflicts and try again." -ForegroundColor Red
                exit 1
            }
            Write-Host "Up to date with remote." -ForegroundColor Green
        }
    }
    
    # Check if there are changes to commit
    $status = git status --porcelain
    if (-not $status) {
        Write-Host "No changes to commit." -ForegroundColor Gray
        exit 0
    }
    
    # Prompt for commit message
    $msg = Read-Host "`nCommit message (empty to skip)"
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
} else {
    Write-Host "Invalid choice. Exiting." -ForegroundColor Red
    exit 1
}