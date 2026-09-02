import { describe, expect, it } from 'vitest';
import { LOGO_OUTPUT_HEIGHT, LOGO_OUTPUT_WIDTH, logoPlacement } from './logoCrop';

describe('logoPlacement', () => {
  it('covers the 10:3 crop without distorting a square image', () => {
    const placed = logoPlacement(500, 500, 1, 0, 0);
    expect(placed.width).toBe(600);
    expect(placed.height).toBe(600);
    expect(placed.x).toBe(0);
    expect(placed.y).toBe(-210);
  });

  it('keeps a matching wide logo centered and supports bounded repositioning', () => {
    expect(logoPlacement(1000, 300, 1, 0, 0)).toEqual({ x: 0, y: 0, width: LOGO_OUTPUT_WIDTH, height: LOGO_OUTPUT_HEIGHT });
    const shifted = logoPlacement(1000, 1000, 2, 100, -100);
    expect(shifted.x).toBeGreaterThanOrEqual(-LOGO_OUTPUT_WIDTH);
    expect(shifted.y).toBeLessThan(0);
  });
});
