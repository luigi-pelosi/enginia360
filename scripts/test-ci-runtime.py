"""Verify the CI runtime configuration without starting any services."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class CiRuntimeTests(unittest.TestCase):
    def test_ci_executes_b03_runtime_acceptance(self):
        workflow = Path(".github/workflows/ci.yml").read_text()
        self.assertIn("run: sh scripts/run-b03-tests.sh", workflow)

    def test_ci_provides_runner_scratch_directory(self):
        workflow = Path(".github/workflows/ci.yml").read_text()
        self.assertNotIn("TMPDIR: ${{ runner.temp }}", workflow)
        self.assertIn("printf 'TMPDIR=%s\\n' \"$RUNNER_TEMP\" >> \"$GITHUB_ENV\"", workflow)

    def test_ci_initialization_satisfies_required_compose_configuration(self):
        workflow = Path(".github/workflows/ci.yml").read_text()
        lines = workflow.splitlines()
        command = []
        collecting = False
        for line in lines:
            if line == "      - name: Initialize ephemeral B02 configuration":
                collecting = True
                continue
            if collecting and line == "        run: |":
                continue
            if collecting:
                if not line.startswith("          "):
                    break
                command.append(line[10:])

        environment = {
            key: value for key, value in os.environ.items()
            if not key.startswith("B02_") and key != "COMPOSE_ENV_FILES"
        }
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as directory:
            github_env = Path(directory) / "github-env"
            github_env.touch(mode=0o600)
            environment["GITHUB_ENV"] = str(github_env)
            environment["RUNNER_TEMP"] = directory
            if command:
                subprocess.run(
                    ["sh", "-eu", "-c", "\n".join(command)],
                    env=environment,
                    check=True,
                    capture_output=True,
                )
            for entry in github_env.read_text().splitlines():
                key, value = entry.split("=", 1)
                environment[key] = value
            self.assertEqual(environment.get("TMPDIR"), directory)
            result = subprocess.run(
                ["docker", "compose", "config", "--quiet"],
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
