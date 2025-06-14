# Debug script to see what schema creation issues occurred
$src = "neuroca_temporal_analysis.db"
$outDB = "debug_template.db"
$sqlite = "sqlite3"

Write-Host "Debugging schema creation issues..." -ForegroundColor Yellow

# Clean start
if (Test-Path $outDB) { Remove-Item $outDB -Force }
if (Test-Path "temp_schema_debug.sql") { Remove-Item "temp_schema_debug.sql" -Force }

# Create empty database
& $sqlite $outDB "SELECT 1;" | Out-Null

# Extract schema with line numbers for debugging
Write-Host "Extracting schema..." -ForegroundColor Cyan
$schema = & $sqlite $src ".schema"

# Save to file for inspection
$schema | Set-Content "temp_schema_debug.sql" -Encoding utf8

Write-Host "Schema file created: temp_schema_debug.sql" -ForegroundColor Green
Write-Host "Total lines: $($schema.Count)" -ForegroundColor White

# Try to execute and capture detailed errors
Write-Host "`nExecuting schema creation with detailed error capture..." -ForegroundColor Cyan

$output = & $sqlite $outDB ".read temp_schema_debug.sql" 2>&1
$exitCode = $LASTEXITCODE

Write-Host "Exit code: $exitCode" -ForegroundColor $(if ($exitCode -eq 0) { "Green" } else { "Red" })

if ($output) {
    Write-Host "`nDetailed output/errors:" -ForegroundColor Yellow
    $output | ForEach-Object { 
        Write-Host "  $_" -ForegroundColor $(if ($_ -match "error|Error|ERROR") { "Red" } else { "White" })
    }
} else {
    Write-Host "No output captured (silent execution)" -ForegroundColor Green
}

# Check what was actually created
Write-Host "`nWhat was created:" -ForegroundColor Green
$tableCount = & $sqlite $outDB "SELECT COUNT(*) FROM sqlite_master WHERE type='table';"
$viewCount = & $sqlite $outDB "SELECT COUNT(*) FROM sqlite_master WHERE type='view';"
$triggerCount = & $sqlite $outDB "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger';"
$indexCount = & $sqlite $outDB "SELECT COUNT(*) FROM sqlite_master WHERE type='index';"

Write-Host "  Tables: $tableCount" -ForegroundColor White
Write-Host "  Views: $viewCount" -ForegroundColor White  
Write-Host "  Triggers: $triggerCount" -ForegroundColor White
Write-Host "  Indexes: $indexCount" -ForegroundColor White

# Show any tables that might be missing
Write-Host "`nComparing to original database:" -ForegroundColor Green
$origTableCount = & $sqlite $src "SELECT COUNT(*) FROM sqlite_master WHERE type='table';"
$origViewCount = & $sqlite $src "SELECT COUNT(*) FROM sqlite_master WHERE type='view';"
$origTriggerCount = & $sqlite $src "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger';"
$origIndexCount = & $sqlite $src "SELECT COUNT(*) FROM sqlite_master WHERE type='index';"

Write-Host "Original - Tables: $origTableCount, Views: $origViewCount, Triggers: $origTriggerCount, Indexes: $origIndexCount" -ForegroundColor White
Write-Host "Created  - Tables: $tableCount, Views: $viewCount, Triggers: $triggerCount, Indexes: $indexCount" -ForegroundColor White

# Check for specific missing objects
Write-Host "`nChecking for missing critical tables..." -ForegroundColor Yellow
$criticalTables = @('components', 'categories', 'statuses', 'component_usage_analysis')
foreach ($table in $criticalTables) {
    $exists = & $sqlite $outDB "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='$table';"
    if ($exists -eq "1") {
        Write-Host "  ✅ $table exists" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $table MISSING" -ForegroundColor Red
    }
}

Write-Host "`nSchema file preserved for inspection: temp_schema_debug.sql" -ForegroundColor Cyan
