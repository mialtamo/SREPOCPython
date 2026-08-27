# Azure SRE Agent Windows POC

A deliberately fault-injectable Python application for demonstrating Azure SRE Agent investigations against a GitHub repository.

## Requirements

- Windows 10/11 or Windows Server
- Python 3.10+
- No third-party Python packages required

## Run

```powershell
python .\app.py cpu --duration 120 --workers 8
python .\app.py memory --mb 2048 --hold 120
python .\app.py leak --rate-mb 25 --duration 180
python .\app.py exception
python .\app.py intermittent --duration 300 --interval 5 --fail-every 4
```

## Modes

### CPU
Creates bounded CPU load using worker threads for a fixed duration.

### Memory
Allocates a specific amount of memory, holds it, and releases it.

### Leak
Gradually retains memory at a configured rate for a fixed duration. This is intended to look like a real leak in monitoring data.

### Exception
Raises an intentional unhandled Python exception and writes the traceback to the log.

### Intermittent
Produces healthy heartbeat events plus recurring simulated downstream timeout errors.

## Logs

Logs are written to:

```text
%LOCALAPPDATA%\sre-agent-poc\logs\app.log
```

Each operational event is emitted as JSON inside the log message so it is easy to collect with Azure Monitor Agent or another log collector.

## Suggested SRE Agent POC

1. Push this repository to GitHub.
2. Connect the repository to Azure SRE Agent.
3. Run the application on a Windows VM or Azure Arc-enabled Windows machine.
4. Collect Windows CPU and memory metrics in Azure Monitor.
5. Optionally collect `app.log` into Log Analytics.
6. Configure CPU and memory alerts.
7. Trigger one of the fault modes.
8. Ask SRE Agent to investigate the alert and inspect the connected repository.

Suggested investigation prompt:

```text
Investigate the alert on this Windows machine. Correlate Azure Monitor telemetry and application logs with the connected GitHub repository. Determine which code path caused the condition, identify the relevant file and function, and recommend both an immediate mitigation and a permanent code fix.
```

## Safety

The POC puts explicit upper bounds on memory allocation and runtime. Start with conservative values and increase gradually on disposable lab systems.
