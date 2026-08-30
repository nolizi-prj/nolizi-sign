import { defineStore } from 'pinia';
import { ref } from 'vue';
import http from '../utils/http';

export interface BrandingState {
  companyName: string;
  logoDataUrl: string | null;
  primaryColor: string;
  welcomeMessage: string;
}

export const useBrandingStore = defineStore('branding', () => {
  const companyName = ref('Pumasi Sign');
  const logoDataUrl = ref<string | null>(null);
  const primaryColor = ref('#1A56DB');
  const welcomeMessage = ref('Please review and sign this document.');
  const loading = ref(false);

  function applyThemeColors(color: string) {
    if (!color) return;
    document.documentElement.style.setProperty('--accent', color);
    document.documentElement.style.setProperty('--v-theme-primary', color);
  }

  async function fetchBranding() {
    loading.value = true;
    try {
      const { data } = await http.get<any>('/branding', { skipAuthRedirect: true });
      if (data) {
        companyName.value = data.company_name || 'Pumasi Sign';
        logoDataUrl.value = data.logo_data_url || null;
        primaryColor.value = data.primary_color || '#1A56DB';
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
      const { data } = await http.put<any>('/branding', {
        company_name: payload.companyName,
        logo_data_url: payload.logoDataUrl,
        primary_color: payload.primaryColor,
        welcome_message: payload.welcomeMessage,
      });
      companyName.value = payload.companyName;
      logoDataUrl.value = payload.logoDataUrl;
      primaryColor.value = payload.primaryColor;
      welcomeMessage.value = payload.welcomeMessage;
      applyThemeColors(payload.primaryColor);
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
