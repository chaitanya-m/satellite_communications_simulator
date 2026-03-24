#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/workspace"
TEST_PATH="tests/test_research_hypotheses.py"
RESULTS_PATH="${REPO_ROOT}/results.txt"

cd "${REPO_ROOT}"

echo "[study] running ${TEST_PATH}"
# Disable pytest's cache provider so the container leaves behind only the
# research result artifact, not extra cache directories.
python -m pytest -q -p no:cacheprovider "${TEST_PATH}"

if [[ ! -f "${RESULTS_PATH}" ]]; then
  echo "[study] expected ${RESULTS_PATH} to be created by the test run" >&2
  exit 1
fi

echo "[study] results written to ${RESULTS_PATH}"
echo "[study] ----- begin results.txt -----"
cat "${RESULTS_PATH}"
echo "[study] ----- end results.txt -----"
