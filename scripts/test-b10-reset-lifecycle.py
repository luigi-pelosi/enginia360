#!/usr/bin/env python3
"""Reproduce fixture TRUNCATE vs outbox discovery on real ephemeral PostgreSQL."""
from pathlib import Path
import re
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "postgres:18.0-alpine3.22@sha256:48c8ad3a7284b82be4482a52076d47d879fd6fb084a1cbfccbd551f9331b0e40"


def run(first_table):
    runner = (ROOT / "scripts/run-b10-tests.sh").read_text()
    reset = runner.split("reset(){", 1)[1].split("\n}", 1)[0]
    match = re.search(r"TRUNCATE ([^;]+);", reset)
    assert match is not None, "fixture reset TRUNCATE missing"
    truncate = match.group(0)
    tables = [table.strip() for table in truncate.removeprefix("TRUNCATE ").rstrip(";").split(",")]
    assert all(re.fullmatch(r"[a-z_]+\.[a-z_]+", table) for table in tables)
    name = "enginia360-reset-lock-" + uuid.uuid4().hex[:12]
    processes = []

    def sql(statement, check=True):
        return subprocess.run(command, input=statement, text=True, capture_output=True,
                              timeout=15, check=check)

    command = ["docker", "exec", "-i", name, "psql", "-h", "127.0.0.1", "-U", "postgres", "-qAt", "-v", "ON_ERROR_STOP=1"]
    try:
        subprocess.run(["docker", "run", "--rm", "-d", "--name", name, "--network", "none",
                        "--user", "postgres", "--read-only", "--cap-drop", "ALL",
                        "--security-opt", "no-new-privileges:true", "--memory", "256m",
                        "--cpus", "1", "--pids-limit", "128", "--log-opt", "max-size=1m",
                        "--log-opt", "max-file=1", "--tmpfs", "/var/lib/postgresql:rw,uid=70,gid=70",
                        "--tmpfs", "/var/run/postgresql:rw,uid=70,gid=70", "--tmpfs", "/tmp",
                        "-e", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE], check=True,
                       capture_output=True, text=True, timeout=90)
        deadline = time.monotonic() + 30
        while sql("SELECT 1;", check=False).returncode:
            assert time.monotonic() < deadline, "ephemeral PostgreSQL did not become ready"
            time.sleep(.1)
        for schema in sorted({table.split(".")[0] for table in tables}):
            sql(f"CREATE SCHEMA {schema};")
        for table in tables:
            sql(f"CREATE TABLE {table}(id integer);")

        # The real pending-outbox function reads outbox before outcomes. Hold its
        # first lock, start the actual reset TRUNCATE, then let it read outcomes.
        reader = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True)
        processes.append(reader)
        assert reader.stdin is not None and reader.stdout is not None and reader.stderr is not None
        assert first_table in ("administrative_outbox", "administrative_requests")
        reader.stdin.write("SET deadlock_timeout='100ms'; SET statement_timeout='5s'; BEGIN; "
                           f"LOCK TABLE workshop.{first_table} IN ACCESS SHARE MODE; SELECT 'ready';\n")
        reader.stdin.flush()
        assert reader.stdout.readline().strip() == "ready", "reader barrier not reached"
        truncator = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True)
        processes.append(truncator)
        assert truncator.stdin is not None and truncator.stderr is not None
        truncator.stdin.write("SET application_name='fixture-reset'; SET deadlock_timeout='100ms'; "
                             "SET statement_timeout='5s'; " + truncate + "\n")
        truncator.stdin.flush()
        deadline = time.monotonic() + 3
        while sql("SELECT count(*) FROM pg_stat_activity WHERE application_name='fixture-reset' AND wait_event_type='Lock';").stdout.strip() != "1":
            assert time.monotonic() < deadline, "reset never queued behind reader"
            time.sleep(.02)
        reader.stdin.write("LOCK TABLE workshop.administrative_outcomes IN ACCESS SHARE MODE; COMMIT;\n")
        reader.stdin.flush()
        reader.stdin.close()
        reader.wait(timeout=10)
        reader_error = reader.stderr.read()
        truncator.stdin.close()
        truncator.wait(timeout=10)
        reset_error = truncator.stderr.read()
        assert reader.returncode == 0 and truncator.returncode == 0, (
            "fixture lock inversion: " + reader_error + reset_error)
        print("PASS real PostgreSQL reset/dispatcher interleaving: both transactions complete without deadlock")
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=20)
        remaining = subprocess.run(["docker", "ps", "-aq", "--filter", f"name=^{name}$"],
                                   capture_output=True, text=True, check=True, timeout=10)
        assert not remaining.stdout.strip(), "ephemeral PostgreSQL not removed"


if __name__ == "__main__":
    for first in ("administrative_outbox", "administrative_requests"):
        run(first)
