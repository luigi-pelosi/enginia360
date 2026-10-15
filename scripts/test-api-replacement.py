#!/usr/bin/env python3
"""Exercise built Compose images in isolation; never replace the public stack."""
import json
import pathlib
import subprocess
import tempfile
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, cwd=ROOT, **kwargs).strip()


def inspect(container):
    return json.loads(run("docker", "inspect", container))[0]


def main():
    project = "enginia360-dns-test-" + uuid.uuid4().hex[:10]
    holder = project + "-ip-holder"
    config = json.loads(run("docker", "compose", "config", "--format", "json"))
    source_project = config.pop("name")
    for name, network in config["networks"].items():
        network["name"] = project + "_" + name
    for name, service in config["services"].items():
        service.pop("build", None)
        service["image"] = run("docker", "image", "inspect", "--format", "{{.Id}}", source_project + "-" + name)
        service["restart"] = "no"
    config["services"]["web"]["ports"] = ["127.0.0.1::8080"]
    with tempfile.TemporaryDirectory(prefix=project + "-") as directory:
        path = pathlib.Path(directory) / "compose.json"
        path.write_text(json.dumps(config))
        compose = ["docker", "compose", "-p", project, "-f", str(path)]

        def dc(*args):
            return run(*compose, *args)

        def web_identity():
            data = inspect(dc("ps", "-q", "web"))
            return data["Id"], data["State"]["StartedAt"], data["RestartCount"]

        try:
            dc("up", "-d", "--no-build", "--wait", "--wait-timeout", "120")
            base = "http://" + dc("port", "web", "8080")
            run("sh", "scripts/smoke.sh", base)
            original_web = web_identity()
            old_api = dc("ps", "-q", "api")
            network = project + "_backend"
            old_ip = inspect(old_api)["NetworkSettings"]["Networks"][network]["IPAddress"]
            dc("rm", "--stop", "--force", "api")
            # Occupy the released address so Docker cannot silently reuse it.
            run("docker", "run", "-d", "--name", holder, "--network", network,
                "--ip", old_ip, "--read-only", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges:true", "--memory", "32m",
                "--pids-limit", "16", "--entrypoint", "/bin/sh",
                config["services"]["web"]["image"], "-c", "sleep 300")
            dc("up", "-d", "--no-build", "--no-deps", "--wait", "--wait-timeout", "120", "api")
            new_api = dc("ps", "-q", "api")
            new_ip = inspect(new_api)["NetworkSettings"]["Networks"][network]["IPAddress"]
            assert old_api != new_api and old_ip != new_ip, "API was not replaced at a different IP"
            print(f"API replaced: {old_ip} -> {new_ip}", flush=True)
            deadline = time.monotonic() + 30
            last = ""
            while time.monotonic() < deadline:
                result = subprocess.run(["curl", "--fail", "--silent", "--show-error",
                                         "--connect-timeout", "1", "--max-time", "2",
                                         "-H", "X-Correlation-ID: dns-regression_123",
                                         "-D", "-", base + "/api/v1/system/status?dns=regression"],
                                        capture_output=True, text=True)
                last = result.stderr or result.stdout
                if result.returncode == 0 and "X-Correlation-ID: dns-regression_123".lower() in result.stdout.lower():
                    break
                time.sleep(1)
            else:
                raise AssertionError("Proxy did not recover within 30s after IP change: " + last)
            assert web_identity() == original_web, "web restarted or was replaced"
            print(run("sh", "scripts/smoke.sh", base), flush=True)
            print("PASS: API IP changed; unchanged web recovered and preserved correlation header/routes.", flush=True)
        finally:
            subprocess.run(["docker", "rm", "-f", holder], capture_output=True, text=True)
            dc("down", "--remove-orphans", "--timeout", "10")
            assert not run("docker", "ps", "-aq", "--filter", "name=" + project)
            assert not run("docker", "network", "ls", "-q", "--filter", "name=" + project)
            print("Cleanup verified: no regression containers/networks remain.", flush=True)


if __name__ == "__main__":
    main()
