
# --- CONFIGURATION ---
$ReportsPath = "D:\Assemblyline\unified_app\reports"
$OutputCsv   = "D:\Assemblyline\unified_app\summary.csv"

Write-Host "Scanning pytest HTML reports in $ReportsPath..."

$Results = @()
$Reports = Get-ChildItem -Path $ReportsPath -Filter "*.html" -Recurse -ErrorAction SilentlyContinue

foreach ($report in $Reports) {
    $content = Get-Content -Path $report.FullName -Raw -ErrorAction SilentlyContinue
    if (-not $content) {
        Write-Warning "Unable to read: $($report.Name)"
        continue
    }

    $status = "PASSED"
    $errorMsg = ""

    # --- Extract data-jsonblob attribute ---
    $match = [regex]::Match($content, 'data-jsonblob=(["''])(.*?)\1', [System.Text.RegularExpressions.RegexOptions]::Singleline)
    if ($match.Success) {
        $jsonblob = $match.Groups[2].Value

        # Decode common HTML entities
        $jsonblob = $jsonblob -replace '&quot;', '"'
        $jsonblob = $jsonblob -replace '&#34;', '"'
        $jsonblob = $jsonblob -replace '&amp;', '&'
        $jsonblob = $jsonblob -replace '&#39;', "'"
        $jsonblob = $jsonblob -replace '&lt;', '<'
        $jsonblob = $jsonblob -replace '&gt;', '>'

        # Try to parse JSON
        $parsed = $null
        try {
            $parsed = $jsonblob | ConvertFrom-Json -ErrorAction Stop
        } catch {
            # fallback: unescape double backslashes
            $tryBlob = $jsonblob -replace '\\\\"', '\"' -replace '\\\\', '\'
            try {
                $parsed = $tryBlob | ConvertFrom-Json -ErrorAction SilentlyContinue
            } catch {
                $parsed = $null
            }
        }

        if ($null -ne $parsed -and $parsed.PSObject.Properties.Name -contains 'tests') {
            $foundFailed = $false
            foreach ($kv in $parsed.tests.PSObject.Properties) {
                $arr = $kv.Value
                foreach ($entry in $arr) {
                    $res = ($entry.result -as [string])
                    if ($res -and $res.ToLower() -eq 'failed') {
                        $foundFailed = $true

                        # --- Decode and clean log text ---
                        if ($entry.log -and $entry.log.Trim() -ne '') {
                            $decodedLog = $entry.log
                            $decodedLog = $decodedLog -replace '\\n', [Environment]::NewLine
                            $decodedLog = $decodedLog -replace '\\\\', '\'
                            $decodedLog = $decodedLog -replace '&quot;', '"'
                            $decodedLog = $decodedLog -replace '&#34;', '"'
                            $decodedLog = $decodedLog -replace '&amp;', '&'
                            $decodedLog = $decodedLog -replace '&lt;', '<'
                            $decodedLog = $decodedLog -replace '&gt;', '>'
                            $decodedLog = $decodedLog.Trim()
                            $errorMsg = $decodedLog
                        } elseif ($entry.extras -and $entry.extras.Count -gt 0) {
                            $extrasText = ($entry.extras | ForEach-Object {
                                ($_.content -as [string]) -replace '<.*?>',''
                            }) -join " | "
                            if ($extrasText.Trim()) { $errorMsg = $extrasText.Trim() }
                        }

                        break
                    }
                }
                if ($foundFailed) { break }
            }
            if ($foundFailed) { $status = "FAILED" }
        }
    }

    # --- Fallback: simple search ---
    if ($status -eq "PASSED") {
        if ($content -match '(?i)"result"\s*:\s*"failed"' -or $content -match '(?i)>\s*Failed\s*<') {
            $status = "FAILED"
            $logmatch = [regex]::Match($content, '(?ms)^.*?E\s+.*$')
            if ($logmatch.Success) { $errorMsg = $logmatch.Value.Trim() }
        }
    }

    # Limit log length
    if ($errorMsg.Length -gt 2000) {
        $errorMsg = $errorMsg.Substring(0,2000) + '... (truncated)'
    }

    $Results += [PSCustomObject]@{
        FileName = $report.Name
        FullPath = $report.FullName
        Status   = $status
        Error    = $errorMsg
    }
}

# --- Export CSV ---
$Results | Export-Csv -Path $OutputCsv -NoTypeInformation -Encoding UTF8

# --- Summary ---
$Passed = ($Results | Where-Object { $_.Status -eq "PASSED" }).Count
$Failed = ($Results | Where-Object { $_.Status -eq "FAILED" }).Count
$Total  = $Results.Count

Write-Host ""
Write-Host "Summary:"
Write-Host "  Passed: $Passed"
Write-Host "  Failed: $Failed"
Write-Host "  Total Reports: $Total"
Write-Host ""
Write-Host "Summary written to: $OutputCsv"
