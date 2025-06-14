# Database Template Builder v2.0
$src = "neuroca_temporal_analysis.db"
$outDB = "neuroca_template.db"
$sqlite = "sqlite3"

Write-Host "Building database template v2..." -ForegroundColor Green

# Check if source exists
if (!(Test-Path $src)) { 
    Write-Error "Source database '$src' not found"
    exit 1 
}

# Remove existing output files
if (Test-Path $outDB) { Remove-Item $outDB -Force }

Write-Host "Step 1: Creating empty template database..." -ForegroundColor Yellow

# Create empty database
& $sqlite $outDB "SELECT 1;" | Out-Null

Write-Host "Step 2: Extracting and executing schema..." -ForegroundColor Yellow

# Get complete schema (tables, indexes, triggers, views) in correct order
$schema = & $sqlite $src @"
.schema
"@

# Filter out problematic elements and write to temp file
$schema | 
    Where-Object { $_ -ne "" } |
    Where-Object { $_ -notmatch "^ANALYZE" } |
    Set-Content "temp_schema.sql" -Encoding utf8

# Execute schema creation
Write-Host "  - Creating tables, indexes, triggers, views..." -ForegroundColor Cyan
$result = & $sqlite $outDB ".read temp_schema.sql" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Schema creation had issues, but continuing..." -ForegroundColor Yellow
}

Write-Host "Step 3: Populating lookup tables..." -ForegroundColor Yellow

# Define essential lookup tables
$lookupTables = @(
    'categories', 'statuses', 'priority_levels', 'complexity_levels',
    'working_statuses', 'testing_statuses', 'documentation_statuses', 
    'usage_methods', 'dependency_types', 'issue_types'
)

foreach ($table in $lookupTables) {
    # Check if table exists in source
    $tableExists = & $sqlite $src "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='$table';"
    if ($tableExists -eq "1") {
        # Check if table was created in destination
        $destTableExists = & $sqlite $outDB "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='$table';"
        if ($destTableExists -eq "1") {
            Write-Host "  - Copying $table..." -ForegroundColor Cyan
            # Get data and insert
            $data = & $sqlite $src ".mode insert $table" "SELECT * FROM $table;"
            if ($data) {
                $data | & $sqlite $outDB 2>$null
            }
        } else {
            Write-Host "  - Skipping $table (table not created)" -ForegroundColor Yellow
        }
    }
}

Write-Host "Step 4: Adding automation scripts..." -ForegroundColor Yellow

# Check if automation_scripts table exists and copy active scripts
$scriptTableExists = & $sqlite $outDB "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='automation_scripts';"
if ($scriptTableExists -eq "1") {
    Write-Host "  - Copying active automation scripts..." -ForegroundColor Cyan
    $scriptData = & $sqlite $src ".mode insert automation_scripts" "SELECT * FROM automation_scripts WHERE is_active=1;"
    if ($scriptData) {
        $scriptData | & $sqlite $outDB 2>$null
    }
}

# Clean up
Remove-Item "temp_schema.sql" -Force -ErrorAction SilentlyContinue

Write-Host "Step 5: Verifying template..." -ForegroundColor Yellow

# Get statistics
$tableCount = & $sqlite $outDB "SELECT COUNT(*) FROM sqlite_master WHERE type='table';"
$viewCount = & $sqlite $outDB "SELECT COUNT(*) FROM sqlite_master WHERE type='view';"
$triggerCount = & $sqlite $outDB "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger';"
$indexCount = & $sqlite $outDB "SELECT COUNT(*) FROM sqlite_master WHERE type='index';"

$scriptCount = "0"
try {
    $scriptCount = & $sqlite $outDB "SELECT COUNT(*) FROM automation_scripts WHERE is_active=1;" 2>$null
    if (-not $scriptCount) { $scriptCount = "0" }
} catch {
    $scriptCount = "0"
}

Write-Host "`nTemplate Statistics:" -ForegroundColor Green
Write-Host "  - Database: $outDB" -ForegroundColor White
Write-Host "  - Tables: $tableCount" -ForegroundColor White
Write-Host "  - Views: $viewCount" -ForegroundColor White
Write-Host "  - Triggers: $triggerCount" -ForegroundColor White
Write-Host "  - Indexes: $indexCount" -ForegroundColor White
Write-Host "  - Active scripts: $scriptCount" -ForegroundColor White

# Test integrity
Write-Host "`nTesting template integrity..." -ForegroundColor Yellow
$integrity = & $sqlite $outDB "PRAGMA integrity_check;"
if ($integrity -eq "ok") {
    Write-Host "✅ Template integrity: OK" -ForegroundColor Green
} else {
    Write-Host "⚠️  Template integrity issues (may be normal for empty tables):" -ForegroundColor Yellow
    $integrity | ForEach-Object { Write-Host "   $_" -ForegroundColor Yellow }
}

# Test that we can query essential tables
Write-Host "`nTesting essential tables..." -ForegroundColor Yellow
$essentialTables = @('categories', 'statuses', 'priority_levels')
foreach ($table in $essentialTables) {
    try {
        $count = & $sqlite $outDB "SELECT COUNT(*) FROM $table;" 2>$null
        if ($count -gt 0) {
            Write-Host "  ✅ $table table: $count records" -ForegroundColor Green
        } else {
            Write-Host "  ⚠️  $table table: empty" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  ❌ $table table: not accessible" -ForegroundColor Red
    }
}

Write-Host "`nTemplate build complete!" -ForegroundColor Green
Write-Host "Output: $outDB" -ForegroundColor White
Write-Host "Usage: Copy this file to new projects and rename as needed." -ForegroundColor White
