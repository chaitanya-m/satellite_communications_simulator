# Docker Study Run

This setup packages the `study` branch so a nontechnical user can run the
research-hypothesis study with one command.

## Recommended

```bash
./run_study_docker.sh
```

What it does:
- builds the study image if needed;
- runs `tests/test_research_hypotheses.py` inside the container;
- writes `results.txt` back into the repo on the host;
- prints the contents of `results.txt`;
- tears the container down when finished.

## Standard Docker Compose

```bash
docker compose up --build
```

This runs the same workflow through the `study` service in `compose.yaml`.

## Output

After the container finishes, the main artifact is:

```text
results.txt
```

That file is already listed in `.gitignore`.
