#!/usr/bin/env sh
# Run service/'s own test suite from the repository root, and prove it ran.
#
# WHY THIS EXISTS. pumasi/tools/gate.sh step 1 is `npm test` at this
# repository's root -- that is the whole merge gate for this repository, since
# `GET /repos/pumasi-ai/pumasi-sign/branches/main/protection` is 404 "Branch
# not protected" and the CI jobs report without blocking. Until this script,
# that root script was `cd frontend && npm run test:unit && npx vue-tsc -b
# --force`: 69 frontend assertions and ZERO on service/, the Cloudflare Worker
# that answers sign.pumasi.ai. So `GATE: PASS` could be printed having run
# nothing at all against the tree users meet. That is roadmap/BACKLOG.md item
# 2 and pumasi/DECISIONS.md Q-025 rider (a).
#
# THE TRAP IT IS BUILT AROUND. service/package.json's `test` script is
# `node --test dist/test/*.test.js` -- the COMPILED tree -- and service/dist/
# is .gitignore'd. `node --test` exits 0 on an unmatched glob, so running the
# suite without building first would be a green gate covering nothing: the
# same defect one level up from the one being closed (pumasi/lessons/L-006).
# Hence install, then build, then run, then assert.
#
# The assertion is NOT a second guard. It is the same file ci.yaml's `service`
# job calls, with the same arguments -- one guard in one place, because two
# copies of a rule fork (L-007). Frozen case A-207 asserts both callers name
# the same path; A-104 (spec/0002) exercises the guard itself.
#
# Usage: .github/scripts/run-service-suite.sh   (from anywhere)
set -eu

cd "$(dirname "$0")/../.."

TAP="$(mktemp)"
# shellcheck disable=SC2064  # $TAP is expanded now on purpose.
trap "rm -f '$TAP'" EXIT

echo "── service/ · install"
( cd service && npm ci --no-audit --no-fund )

echo "── service/ · build (dist/ is .gitignore'd; the suite runs dist/)"
( cd service && npm run build )

echo "── service/ · suite"
# The suite's output is captured so the guard can read the runner's own
# reported counts, then echoed in full. A pipe to tee would be tidier and
# needs `pipefail`, which is not POSIX sh.
set +e
( cd service && npm test ) > "$TAP" 2>&1
SUITE_STATUS=$?
set -e
cat "$TAP"

echo "── service/ · did it run? (L-006)"
.github/scripts/assert-service-suite-ran.sh service/src/test service/dist/test "$TAP"

# Reached only when the guard passed. The guard reports a non-zero `# fail`
# count itself, so this exit is about a runner that died without reporting.
if [ "$SUITE_STATUS" -ne 0 ]; then
  echo "run-service-suite: the service suite exited $SUITE_STATUS." >&2
  exit "$SUITE_STATUS"
fi
