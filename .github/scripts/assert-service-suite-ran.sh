#!/usr/bin/env sh
# Assert that the service/ suite actually ran, rather than reporting success
# having executed nothing.
#
# WHY THIS EXISTS. service/package.json's `test` script is
#
#     node --test dist/test/*.test.js
#
# which runs the COMPILED tree, and service/dist/ is .gitignore'd, so a fresh
# checkout has none. `node --test` exits 0 on an unmatched glob. Measured on a
# clean archive of a49f594 with dist/ removed: `# tests 0`, exit 0. So a CI
# job that forgot `npm run build` -- or a tsconfig change that quietly stopped
# emitting the tests -- would be a green job covering nothing. That is
# pumasi/lessons/L-006, and it is the exact failure spec/0002 exists to close;
# writing the job without this guard would have reproduced it one level up.
#
# This runs AFTER the suite and reads the suite's own reported counts and the
# compiled tree. It deliberately does not read the workflow's step list, so it
# still fails if the build step is deleted or moved.
#
# Exercised by frozen acceptance case A-104 (frontend/src/ci-covers-service.spec.ts),
# which executes this file against fixtures -- no npm, no network. Every exit
# below is 1; A-104 pins that rather than accepting "not 0".
#
# Usage: assert-service-suite-ran.sh <src-test-dir> <dist-test-dir> <tap-file>
set -eu

SRC_DIR=${1:?usage: assert-service-suite-ran.sh <src-test-dir> <dist-test-dir> <tap-file>}
DIST_DIR=${2:?missing <dist-test-dir>}
TAP=${3:?missing <tap-file>}

# Count matches without `ls`: an unmatched glob must not trip `set -e`.
count() {
  n=0
  for f in "$@"; do
    if [ -e "$f" ]; then n=$((n + 1)); fi
  done
  echo "$n"
}

src=$(count "$SRC_DIR"/*.test.ts)
dist=$(count "$DIST_DIR"/*.test.js)

if [ "$src" -lt 1 ]; then
  echo "assert-service-suite-ran: no test sources match $SRC_DIR/*.test.ts." >&2
  echo "  There is nothing to run, so a green suite would mean nothing." >&2
  exit 1
fi

if [ "$dist" -ne "$src" ]; then
  echo "assert-service-suite-ran: $DIST_DIR holds $dist compiled test file(s)" >&2
  echo "  for $src source file(s). The suite runs the compiled tree, so it was" >&2
  echo "  not built, or not fully built. This is the L-006 trap: node --test" >&2
  echo "  exits 0 on an unmatched glob. Run \`npm run build\` in service/." >&2
  exit 1
fi

if [ ! -f "$TAP" ]; then
  echo "assert-service-suite-ran: no suite output at $TAP -- the suite did not run." >&2
  exit 1
fi

pass=$(sed -n 's/^# pass \([0-9][0-9]*\)$/\1/p' "$TAP" | tail -1)
fail=$(sed -n 's/^# fail \([0-9][0-9]*\)$/\1/p' "$TAP" | tail -1)

if [ -z "$pass" ] || [ -z "$fail" ]; then
  echo "assert-service-suite-ran: $TAP carries no '# pass'/'# fail' summary." >&2
  echo "  The runner did not report, so its exit code is not evidence." >&2
  exit 1
fi

if [ "$fail" -ne 0 ]; then
  echo "assert-service-suite-ran: the service suite reported $fail failing test(s)." >&2
  exit 1
fi

if [ "$pass" -lt "$src" ]; then
  echo "assert-service-suite-ran: the service suite reported $pass passing test(s)" >&2
  echo "  for $src test source file(s). It did not run the suite it is read as" >&2
  echo "  covering (L-006)." >&2
  exit 1
fi

echo "assert-service-suite-ran: $pass passing, $fail failing, from $dist compiled"
echo "  file(s) for $src source file(s) under $SRC_DIR."
