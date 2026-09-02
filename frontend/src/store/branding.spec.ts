import { describe, expect, it } from 'vitest';
import { brandThemeTokens } from './branding';

describe('brandThemeTokens', () => {
  it('converts a saved hex color into the RGB token Vuetify expects', () => {
    expect(brandThemeTokens('#067647')).toEqual({
      primary: '#067647',
      rgb: '6, 118, 71',
      hover: '#055C37',
      soft: '#E9F3EE',
    });
  });

  it('normalizes shorthand and rejects malformed values', () => {
    expect(brandThemeTokens('#abc').primary).toBe('#AABBCC');
    expect(brandThemeTokens('not-a-color').primary).toBe('#1A56DB');
  });
});
