# =====================================================
#  db_cli.ps1 - Supabase database management helper
#  Usage: .\db_cli.ps1 <command>
#
#  Commands:
#    push          Push local migrations to remote DB
#    pull          Pull remote schema to local
#    new <name>    Create a new migration file
#    status        Show migration status
#    reset         Reset local DB (local dev only)
#    diff          Diff local vs remote schema
# =====================================================

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Command,

    [Parameter(Position=1)]
    [string]$MigrationName = ""
)

# Load .env for SUPABASE_ACCESS_TOKEN
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

$PROJECT_REF = "cafyyamixidmgkbsqtwh"

# Ensure SUPABASE_ACCESS_TOKEN is set
if (-not $env:SUPABASE_ACCESS_TOKEN) {
    Write-Host ""
    Write-Host "  ERROR: SUPABASE_ACCESS_TOKEN not set." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Add it to your .env file:" -ForegroundColor Yellow
    Write-Host "    SUPABASE_ACCESS_TOKEN=sbp_your_token_here" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Get a token at: https://supabase.com/dashboard/account/tokens" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

switch ($Command) {

    "push" {
        Write-Host ""
        Write-Host "  Pushing migrations to Supabase..." -ForegroundColor Cyan
        npx supabase db push --project-ref $PROJECT_REF
        Write-Host "  Done!" -ForegroundColor Green
    }

    "pull" {
        Write-Host ""
        Write-Host "  Pulling remote schema..." -ForegroundColor Cyan
        npx supabase db pull --project-ref $PROJECT_REF
        Write-Host "  Done!" -ForegroundColor Green
    }

    "new" {
        if (-not $MigrationName) {
            Write-Host "  ERROR: Provide a migration name. Example: .\db_cli.ps1 new add_reports_table" -ForegroundColor Red
            exit 1
        }
        Write-Host ""
        Write-Host "  Creating migration: $MigrationName ..." -ForegroundColor Cyan
        npx supabase migration new $MigrationName
        Write-Host "  Edit the new file in supabase/migrations/" -ForegroundColor Yellow
    }

    "status" {
        Write-Host ""
        Write-Host "  Migration status:" -ForegroundColor Cyan
        npx supabase migration list --project-ref $PROJECT_REF
    }

    "diff" {
        Write-Host ""
        Write-Host "  Diffing local vs remote schema..." -ForegroundColor Cyan
        npx supabase db diff --project-ref $PROJECT_REF
    }

    "reset" {
        Write-Host ""
        Write-Host "  WARNING: This resets the LOCAL dev database only." -ForegroundColor Yellow
        npx supabase db reset
    }

    default {
        Write-Host ""
        Write-Host "  Unknown command: $Command" -ForegroundColor Red
        Write-Host ""
        Write-Host "  Available commands:" -ForegroundColor Yellow
        Write-Host "    push          Push local migrations to remote DB"
        Write-Host "    pull          Pull remote schema to local"
        Write-Host "    new <name>    Create a new migration file"
        Write-Host "    status        Show migration status"
        Write-Host "    diff          Diff local vs remote schema"
        Write-Host "    reset         Reset local DB (local dev only)"
        Write-Host ""
    }
}
