param(
    [ValidateSet('cpu','memory','leak','exception','intermittent')]
    [string]$Mode = 'cpu'
)

$Python = Get-Command python -ErrorAction Stop

switch ($Mode) {
    'cpu'          { & $Python.Source .\app.py cpu --duration 120 --workers 8 }
    'memory'       { & $Python.Source .\app.py memory --mb 2048 --hold 120 }
    'leak'         { & $Python.Source .\app.py leak --rate-mb 25 --duration 180 }
    'exception'    { & $Python.Source .\app.py exception }
    'intermittent' { & $Python.Source .\app.py intermittent --duration 300 --interval 5 --fail-every 4 }
}
