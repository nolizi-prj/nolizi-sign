import { defineStore } from 'pinia';
import { ref } from 'vue';
import http from '../utils/http';

export interface BrandingState {
  companyName: string;
  logoDataUrl: string | null;
  primaryColor: string;
  welcomeMessage: string;
}

const DEFAULT_PRIMARY = '#1A56DB';
const BRAND_STYLE_ID = 'pumasi-workspace-brand-theme';

function normalizeHex(color: string): string | null {
  const value = color.trim();
  const short = /^#([0-9a-f]{3})$/i.exec(value);
  if (short) return `#${short[1].split('').map((digit) => digit + digit).join('')}`.toUpperCase();
  return /^#[0-9a-f]{6}$/i.test(value) ? value.toUpperCase() : null;
}

function rgbOf(hex: string): [number, number, number] {
  return [1, 3, 5].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16)) as [number, number, number];
}

function mix(hex: string, target: number, weight: number): string {
  const rgb = rgbOf(hex).map((channel) => Math.round(channel + (target - channel) * weight));
  return `#${rgb.map((channel) => channel.toString(16).padStart(2, '0')).join('')}`.toUpperCase();
}

export function brandThemeTokens(color: string) {
  const primary = normalizeHex(color) ?? DEFAULT_PRIMARY;
  const rgb = rgbOf(primary);
  return {
    primary,
    rgb: rgb.join(', '),
    hover: mix(primary, 0, 0.22),
    soft: mix(primary, 255, 0.91),
  };
}

export const useBrandingStore = defineStore('branding', () => {
  const companyName = ref('Nolizi Sign');
  const logoDataUrl = ref<string | null>(null);
  const primaryColor = ref(DEFAULT_PRIMARY);
  const welcomeMessage = ref('Please review and sign this document.');
  const loading = ref(false);

  function applyThemeColors(color: string) {
    const theme = brandThemeTokens(color);
    const root = document.documentElement.style;
    root.setProperty('--accent', theme.primary);
    root.setProperty('--accent-hover', theme.hover);
    root.setProperty('--accent-soft', theme.soft);
    root.setProperty('--v-theme-primary', theme.rgb);
    root.setProperty('--v-theme-primary-darken-1', rgbOf(theme.hover).join(', '));
    root.setProperty('--v-theme-secondary', theme.rgb);
    root.setProperty('--v-theme-accent', theme.rgb);
    root.setProperty('--v-theme-info', theme.rgb);
    let style = document.getElementById(BRAND_STYLE_ID) as HTMLStyleElement | null;
    if (!style) {
      style = document.createElement('style');
      style.id = BRAND_STYLE_ID;
      document.head.appendChild(style);
    }
    style.textContent = `.v-theme--pumasi {
      --v-theme-primary: ${theme.rgb} !important;
      --v-theme-primary-darken-1: ${rgbOf(theme.hover).join(', ')} !important;
      --v-theme-secondary: ${theme.rgb} !important;
      --v-theme-accent: ${theme.rgb} !important;
      --v-theme-info: ${theme.rgb} !important;
    }`;
  }

  async function fetchBranding() {
    loading.value = true;
    try {
      const { data } = await http.get<any>('/branding', { skipAuthRedirect: true });
      if (data) {
        companyName.value = data.company_name || 'Nolizi Sign';
        logoDataUrl.value = data.logo_data_url || null;
        primaryColor.value = brandThemeTokens(data.primary_color || DEFAULT_PRIMARY).primary;
        welcomeMessage.value = data.welcome_message || 'Please review and sign this document.';
        applyThemeColors(primaryColor.value);
      }
    } catch {
      // Use defaults
    } finally {
      loading.value = false;
    }
  }

  async function saveBranding(payload: {
    companyName: string;
    logoDataUrl: string | null;
    primaryColor: string;
    welcomeMessage: string;
  }) {
    loading.value = true;
    try {
      const normalizedPrimary = brandThemeTokens(payload.primaryColor).primary;
      const { data } = await http.put<any>('/branding', {
        company_name: payload.companyName,
        logo_data_url: payload.logoDataUrl,
        primary_color: normalizedPrimary,
        welcome_message: payload.welcomeMessage,
      });
      companyName.value = payload.companyName;
      logoDataUrl.value = payload.logoDataUrl;
      primaryColor.value = normalizedPrimary;
      welcomeMessage.value = payload.welcomeMessage;
      applyThemeColors(primaryColor.value);
      return data;
    } finally {
      loading.value = false;
    }
  }

  return {
    companyName,
    logoDataUrl,
    primaryColor,
    welcomeMessage,
    loading,
    fetchBranding,
    saveBranding,
    applyThemeColors,
  };
});
