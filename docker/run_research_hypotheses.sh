#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/workspace"
TEST_PATH="tests/test_research_hypotheses.py"
SUMMARY_PATH="${REPO_ROOT}/result_summary.txt"
TABLE_PATH="${REPO_ROOT}/result_table.txt"

cd "${REPO_ROOT}"

echo "[study] running ${TEST_PATH}"
# Disable pytest's cache provider so the container leaves behind only the
# research result artifact, not extra cache directories.
python -m pytest -q -p no:cacheprovider "${TEST_PATH}"

if [[ ! -f "${SUMMARY_PATH}" ]]; then
  echo "[study] expected ${SUMMARY_PATH} to be created by the test run" >&2
  exit 1
fi

if [[ ! -f "${TABLE_PATH}" ]]; then
  echo "[study] expected ${TABLE_PATH} to be created by the test run" >&2
  exit 1
fi

echo "[study] summary written to ${SUMMARY_PATH}"
echo "[study] raw table written to ${TABLE_PATH}"
echo "[study] ----- begin result_summary.txt -----"
cat "${SUMMARY_PATH}"
echo "[study] ----- end result_summary.txt -----"
