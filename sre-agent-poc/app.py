import argparse
import json
import logging
import math
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

APP_NAME = "sre-agent-poc"
LOG_DIR = Path(os.environ.get("LOCALAPPDATA", ".")) / APP_NAME / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(APP_NAME)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def log_event(event_type, **details):
    payload = {
        "timestamp_utc": utc_now(),
        "event_type": event_type,
        "pid": os.getpid(),
        **details,
    }
    logger.info(json.dumps(payload, default=str))


def cpu_worker(stop_event):
    value = 1.000001
    while not stop_event.is_set():
        value = math.sqrt(value * value + 1.234567)
        if value > 1_000_000:
            value = 1.000001


def cpu_stress(duration, workers):
    stop_event = threading.Event()
    threads = []
    log_event("cpu_stress_started", duration_seconds=duration, workers=workers)

    for _ in range(workers):
        t = threading.Thread(target=cpu_worker, args=(stop_event,), daemon=True)
        t.start()
        threads.append(t)

    time.sleep(duration)
    stop_event.set()
    for t in threads:
        t.join(timeout=2)

    log_event("cpu_stress_completed", duration_seconds=duration, workers=workers)


def memory_stress(target_mb, hold_seconds, chunk_mb=10):
    allocated = []
    total_mb = 0
    log_event("memory_stress_started", target_mb=target_mb, hold_seconds=hold_seconds)

    try:
        while total_mb < target_mb:
            allocate_mb = min(chunk_mb, target_mb - total_mb)
            allocated.append(bytearray(allocate_mb * 1024 * 1024))
            total_mb += allocate_mb
            log_event("memory_allocated", total_mb=total_mb)
            time.sleep(0.25)

        log_event("memory_target_reached", total_mb=total_mb)
        time.sleep(hold_seconds)
    except MemoryError:
        log_event("memory_error", total_mb=total_mb)
        raise
    finally:
        allocated.clear()
        log_event("memory_released", total_mb=total_mb)


def simulated_memory_leak(rate_mb, duration, max_mb=4096):
    leaked = []
    start = time.time()
    total_mb = 0
    log_event("memory_leak_started", rate_mb_per_second=rate_mb, duration_seconds=duration, max_mb=max_mb)

    try:
        while time.time() - start < duration:
            if total_mb + rate_mb > max_mb:
                log_event("memory_leak_cap_reached", leaked_mb=total_mb, max_mb=max_mb)
                break
            leaked.append(bytearray(rate_mb * 1024 * 1024))
            total_mb += rate_mb
            log_event("memory_leak_growth", leaked_mb=total_mb)
            time.sleep(1)

        log_event("memory_leak_completed", leaked_mb=total_mb)
        time.sleep(5)
    except MemoryError:
        log_event("memory_leak_oom", leaked_mb=total_mb)
        logger.exception("MemoryError during simulated_memory_leak")
    finally:
        leaked.clear()
        log_event("memory_leak_released", leaked_mb=total_mb)


def exception_test():
    log_event("exception_test_started")
    data = {"customer": None}
    try:
        return data["customer"]["id"]
    except Exception as exc:
        log_event("unhandled_exception", exception_type=type(exc).__name__, message=str(exc))
        logger.exception("Intentional POC exception")
        raise


def intermittent_errors(duration, interval, fail_every):
    start = time.time()
    counter = 0
    log_event(
        "intermittent_error_test_started",
        duration_seconds=duration,
        interval_seconds=interval,
        fail_every=fail_every,
    )

    while time.time() - start < duration:
        counter += 1
        if counter % fail_every == 0:
            try:
                raise TimeoutError("Intentional simulated downstream timeout")
            except TimeoutError as exc:
                log_event("dependency_timeout", iteration=counter, message=str(exc))
                logger.exception("Simulated dependency failure")
        else:
            log_event("heartbeat", iteration=counter, status="healthy")
        time.sleep(interval)

    log_event("intermittent_error_test_completed", iterations=counter)


def parse_args():
    parser = argparse.ArgumentParser(description="Controlled Windows reliability POC for Azure SRE Agent demos")
    sub = parser.add_subparsers(dest="mode", required=True)

    cpu = sub.add_parser("cpu", help="Generate bounded CPU load")
    cpu.add_argument("--duration", type=int, default=60)
    cpu.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 1))

    mem = sub.add_parser("memory", help="Allocate and hold a bounded amount of memory")
    mem.add_argument("--mb", type=int, default=1024)
    mem.add_argument("--hold", type=int, default=60)

    leak = sub.add_parser("leak", help="Simulate gradual memory leak")
    leak.add_argument("--rate-mb", type=int, default=25)
    leak.add_argument("--duration", type=int, default=120)
    leak.add_argument("--max-mb", type=int, default=4096, help="Safety cap in MB (1-16384)")

    sub.add_parser("exception", help="Generate an intentional unhandled exception")

    intermittent = sub.add_parser("intermittent", help="Generate periodic simulated dependency failures")
    intermittent.add_argument("--duration", type=int, default=180)
    intermittent.add_argument("--interval", type=int, default=5)
    intermittent.add_argument("--fail-every", type=int, default=4)

    return parser.parse_args()


def validate_args(args):
    if getattr(args, "duration", 1) < 1:
        raise ValueError("duration must be at least 1 second")
    if hasattr(args, "workers") and not 1 <= args.workers <= 128:
        raise ValueError("workers must be between 1 and 128")
    if hasattr(args, "mb") and not 1 <= args.mb <= 8192:
        raise ValueError("memory allocation must be between 1 and 8192 MB")
    if hasattr(args, "hold") and not 0 <= args.hold <= 3600:
        raise ValueError("hold must be between 0 and 3600 seconds")
    if hasattr(args, "rate_mb") and not 1 <= args.rate_mb <= 100:
        raise ValueError("rate-mb must be between 1 and 100 MB/sec")
    if hasattr(args, "max_mb") and not 1 <= args.max_mb <= 16384:
        raise ValueError("max-mb must be between 1 and 16384 MB")
    if hasattr(args, "fail_every") and args.fail_every < 1:
        raise ValueError("fail-every must be at least 1")


def main():
    args = parse_args()
    validate_args(args)
    log_event("application_started", mode=args.mode, argv=sys.argv)

    if args.mode == "cpu":
        cpu_stress(args.duration, args.workers)
    elif args.mode == "memory":
        memory_stress(args.mb, args.hold)
    elif args.mode == "leak":
        simulated_memory_leak(args.rate_mb, args.duration, args.max_mb)
    elif args.mode == "exception":
        exception_test()
    elif args.mode == "intermittent":
        intermittent_errors(args.duration, args.interval, args.fail_every)

    log_event("application_completed", mode=args.mode)


if __name__ == "__main__":
    main()
