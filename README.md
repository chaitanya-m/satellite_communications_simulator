# Satellite Attenuation Study

This repository contains the current `study`-branch workflow for running the
attenuation research experiment and writing:
- a structured summary to `result_summary.txt`;
- a raw output table to `result_table.txt`.

The intended path is:
- install Docker Desktop;
- open Terminal;
- run one command from the repository root;
- wait for the study to finish;
- read `result_summary.txt` and `result_table.txt`.

## What This Run Does

The Docker workflow runs:

```text
tests/test_research_hypotheses.py
```

That test:
- runs the current research-scale attenuation experiment;
- writes a structured summary to `result_summary.txt`;
- writes raw output tables to `result_table.txt`;
- prints the summary to the terminal.

No local Python setup is required if you use Docker.

## Mac Prerequisites

You need:
- macOS
- Docker Desktop for Mac
- Terminal access
- this repository checked out on the `study` branch

## 1. Install Docker Desktop

Install Docker Desktop for Mac from Docker's official site, then launch it
once and wait until Docker reports that it is running.

Quick check in Terminal:

```bash
docker --version
docker compose version
```

Both commands should print version information without errors.

## 2. Open the Repository

In Terminal, move into the repository root:

```bash
cd /path/to/satsim
```

Confirm you are on the `study` branch:

```bash
git branch --show-current
```

Expected output:

```text
study
```

If needed:

```bash
git checkout study
```

## 3. Run the Study

Recommended command:

```bash
./run_study_docker.sh
```

What this command does:
- builds the Docker image if needed;
- runs the research study inside the container;
- writes `result_summary.txt` and `result_table.txt` back into the repository
  on your Mac;
- prints the summary file to the terminal;
- stops the container when the run is complete.

The first run may take a few minutes because Docker has to build the image.
Later runs should be faster.

## 4. Verify the Output

When the run finishes successfully, you should see output ending with lines of
this form:

```text
2 passed in ...
[study] summary written to /workspace/result_summary.txt
[study] raw table written to /workspace/result_table.txt
```

On your Mac, the generated files will be:

```text
result_summary.txt
result_table.txt
```

You can inspect it with:

```bash
cat result_summary.txt
cat result_table.txt
```

or open it in VS Code:

```bash
code result_summary.txt
code result_table.txt
```

## Standard Docker Compose Alternative

If you prefer the standard Docker command directly, you can run:

```bash
docker compose up --build
```

This runs the same study service defined in `compose.yaml`.

## Expected Result Sections

`result_summary.txt` is written in a stable sectioned format:

```text
[experiment]
[pooled_certificate]
[scenario.square_center]
[scenario.vertical_bands]
[scenario.multi_circles]
```

`result_table.txt` contains the corresponding raw outputs, including:

```text
[trial_level_certificate_rows]
[seed_level_dimensioning_rows]
```

These structures are intentional so future experiments can extend the files in
a consistent way.

## Troubleshooting

### `docker: command not found`

Docker Desktop is not installed, or Terminal cannot see it yet.

Action:
- install Docker Desktop;
- restart Terminal;
- rerun `docker --version`.

### Docker is installed but the daemon is not running

You may see an error about connecting to the Docker daemon.

Action:
- open Docker Desktop;
- wait until it shows as running;
- rerun the study command.

### `./run_study_docker.sh: permission denied`

Make the wrapper executable once:

```bash
chmod +x run_study_docker.sh
```

Then rerun:

```bash
./run_study_docker.sh
```

### The run takes a long time on the first attempt

That is expected. The initial build downloads the base Python image and
installs container dependencies before the test runs.

## Files Relevant to the Docker Workflow

- `README.md`
- `Dockerfile.study`
- `compose.yaml`
- `run_study_docker.sh`
- `docker/run_research_hypotheses.sh`
- `tests/test_research_hypotheses.py`

## Notes

- `result_summary.txt` and `result_table.txt` are intentionally ignored by Git.
- The Docker workflow was verified on the `study` branch before writing this
  README.
