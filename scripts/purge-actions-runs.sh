#!/usr/bin/env bash
# Delete all GitHub Actions workflow runs for this repo (keeps workflows themselves).
# Requires: gh auth login (repo + actions scope)
set -euo pipefail

OWNER="${OWNER:-redmanxp}"
REPO="${REPO:-MailArchive-OSS}"
FULL="${OWNER}/${REPO}"

if ! gh auth status -h github.com >/dev/null 2>&1; then
  echo "Not logged in. Run: gh auth login -h github.com -p https -s 'delete:packages,workflow,repo'"
  exit 1
fi

echo "Listing runs for ${FULL}..."
mapfile -t IDS < <(gh api --paginate "repos/${FULL}/actions/runs" --jq '.workflow_runs[].id')
echo "Found ${#IDS[@]} run(s). Deleting..."

n=0
for id in "${IDS[@]}"; do
  n=$((n + 1))
  echo "[$n/${#IDS[@]}] delete run ${id}"
  gh api -X DELETE "repos/${FULL}/actions/runs/${id}" >/dev/null || echo "  (skip/fail ${id})"
  # gentle rate limit
  sleep 0.15
done

echo "Done. Check https://github.com/${FULL}/actions"
