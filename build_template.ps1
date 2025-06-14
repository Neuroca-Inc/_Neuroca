$src  = "neuroca_temporal_analysis.db"
$tmp  = "template_build.db"
$outSQL = "neuroca_template_v1.sql"
$outDB  = "neuroca_template.db"
$sqlite = "sqlite3"

if (!(Test-Path $src)) { Write-Error "source missing"; exit 1 }
if (Test-Path $outDB) { Remove-Item $outDB }

Copy-Item $src $tmp -Force
& $sqlite $tmp "VACUUM;"

& $sqlite $tmp ".schema" |
  Where-Object { $_ -notmatch 'sqlite_sequence' } |
  Set-Content schema.ddl.sql -Encoding utf8

$lookups = @(
  'categories','statuses','priority_levels','complexity_levels',
  'working_statuses','testing_statuses','documentation_statuses',
  'usage_methods','dependency_types','issue_types'
)

Set-Content seed_data.sql "" -Encoding utf8
foreach ($t in $lookups) {
  if (& $sqlite $tmp ".schema $t" 2>$null) {
    @(".mode insert $t","SELECT * FROM $t;") |
      & $sqlite $tmp |
      Out-File seed_data.sql -Append -Encoding utf8
  }
}
@(".mode insert automation_scripts",
  "SELECT * FROM automation_scripts WHERE is_active=1;") |
  & $sqlite $tmp |
  Out-File seed_data.sql -Append -Encoding utf8

@(".bail on","") | Out-File $outSQL -Encoding utf8
Get-Content schema.ddl.sql | Add-Content $outSQL
"`n" | Add-Content $outSQL
Get-Content seed_data.sql | Add-Content $outSQL

& $sqlite $outDB ".read $outSQL"

Remove-Item $tmp, schema.ddl.sql, seed_data.sql
