/**
 * Where the signing tour's Next button should go.
 *
 * Scans cyclically from the field after `currentIndex`, ending with the
 * current field itself, and returns the first incomplete one — so Next
 * always lands somewhere useful, including re-scrolling to the current
 * field when it's the only one left (the "Field 1 of 1" case). With every
 * field complete it returns the cyclically next field so Next still moves.
 * Returns null only when there are no fields at all.
 */
export function nextTourIndex(complete: readonly boolean[], currentIndex: number): number | null {
  const count = complete.length;
  if (count === 0) return null;
  const start = ((currentIndex % count) + count) % count;
  for (let step = 1; step <= count; step++) {
    const index = (start + step) % count;
    if (!complete[index]) return index;
  }
  return (start + 1) % count;
}
