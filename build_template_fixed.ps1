# Fixed PowerShell script to create database template
$src = "neuroca_temporal_analysis.db"
$outDB = "neuroca_template.db"
$sqlite = "sqlite3"

Write-Host "Building database template..." -ForegroundColor Green

# Check if source exists
if (!(Test-Path $src)) { 
    Write-Error "Source database '$src' not found"
    exit 1 
}

# Remove existing output files
if (Test-Path $outDB) { Remove-Item $outDB -Force }
if (Test-Path "neuroca_template_v1.sql") { Remove-Item "neuroca_template_v1.sql" -Force }

Write-Host "Creating fresh template database..." -ForegroundColor Yellow

# Create fresh database and extract schema only (no data)
& $sqlite $src ".dump" | 
    Where-Object { 
        $_ -match "^CREATE " -or 
        $_ -match "^INSERT INTO sqlite_sequence" 
    } |
    Where-Object { 
        $_ -notmatch "INSERT INTO components" -and
        $_ -notmatch "INSERT INTO component_usage_analysis" -and
        $_ -notmatch "INSERT INTO component_dependencies" -and
        $_ -notmatch "INSERT INTO component_issues" -and
        $_ -notmatch "INSERT INTO file_activity_log" -and
        $_ -notmatch "INSERT INTO git_activity_log" -and
        $_ -notmatch "INSERT INTO audit_log" -and
        $_ -notmatch "INSERT INTO current_drift_alerts"
    } | 
    Set-Content "schema_only.sql" -Encoding utf8

Write-Host "Extracting lookup table data..." -ForegroundColor Yellow

# Define lookup tables to preserve
$lookupTables = @(
    'categories', 'statuses', 'priority_levels', 'complexity_levels',
    'working_statuses', 'testing_statuses', 'documentation_statuses', 
    'usage_methods', 'dependency_types', 'issue_types'
)

# Extract data from lookup tables
"" | Set-Content "lookup_data.sql" -Encoding utf8
foreach ($table in $lookupTables) {
    $checkTable = & $sqlite $src "SELECT name FROM sqlite_master WHERE type='table' AND name='$table';" 2>$null
    if ($checkTable -eq $table) {
        Write-Host "  - Extracting $table data..." -ForegroundColor Cyan
        & $sqlite $src ".mode insert $table" ".output stdout" "SELECT * FROM $table;" 2>$null |
            Add-Content "lookup_data.sql"
    }
}

Write-Host "Extracting active automation scripts..." -ForegroundColor Yellow

# Extract automation scripts
& $sqlite $src ".mode insert automation_scripts" ".output stdout" "SELECT * FROM automation_scripts WHERE is_active=1;" 2>$null |
    Add-Content "lookup_data.sql"

Write-Host "Building final template..." -ForegroundColor Yellow

# Create the final template database
& $sqlite $outDB ".read schema_only.sql"
& $sqlite $outDB ".read lookup_data.sql"

# Clean up temporary files
Remove-Item "schema_only.sql", "lookup_data.sql" -Force

# Verify the template
$tableCount = & $sqlite $outDB "SELECT COUNT(*) FROM sqlite_master WHERE type='table';"
$scriptCount = & $sqlite $outDB "SELECT COUNT(*) FROM automation_scripts WHERE is_active=1;" 2>$null

Write-Host "Template created successfully!" -ForegroundColor Green
Write-Host "  - Database: $outDB" -ForegroundColor White
Write-Host "  - Tables: $tableCount" -ForegroundColor White
Write-Host "  - Active scripts: $scriptCount" -ForegroundColor White

# Test the template
Write-Host "`nTesting template integrity..." -ForegroundColor Yellow
$integrity = & $sqlite $outDB "PRAGMA integrity_check;"
if ($integrity -eq "ok") {
    Write-Host "✅ Template integrity: OK" -ForegroundColor Green
} else {
    Write-Host "❌ Template integrity issues:" -ForegroundColor Red
    Write-Host $integrity -ForegroundColor Red
}

Write-Host "`n🎉 Template ready for use!" -ForegroundColor Green
Write-Host "To use: Copy '$outDB' to your new project and rename it." -ForegroundColor White
