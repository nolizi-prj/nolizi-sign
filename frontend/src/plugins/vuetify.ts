import "vuetify/styles";
import "@mdi/font/css/materialdesignicons.css";
import { createVuetify } from "vuetify";
import * as components from "vuetify/components";
import * as directives from "vuetify/directives";

/**
 * Pumasi Sign Theme — Official Pumasi Design System.
 * Primary: #1A56DB (Pumasi Sapphire Indigo)
 * Secondary: #3B82F6 (Pumasi Blue Accent)
 * Background: #F8FAFC (Clean slate canvas)
 * Surface: #FFFFFF
 * Success: #067647 (Emerald)
 * Warning: #B54708 (Amber)
 * Error: #B42318 (Crimson)
 */
export const vuetify = createVuetify({
  components,
  directives,
  icons: {
    defaultSet: "mdi",
  },
  theme: {
    defaultTheme: "pumasi",
    themes: {
      pumasi: {
        dark: false,
        colors: {
          primary: "#1A56DB", // Pumasi Sapphire Indigo
          "primary-darken-1": "#1E40AF",
          secondary: "#3B82F6", // Pumasi Blue Accent
          accent: "#1A56DB",
          background: "#F8FAFC", // Clean crisp background
          surface: "#FFFFFF",
          success: "#067647",
          warning: "#B54708",
          error: "#B42318",
          info: "#1A56DB",
        },
      },
    },
  },
  defaults: {
    VBtn: {
      style: "text-transform: none; letter-spacing: normal; font-weight: 550; border-radius: 8px;",
    },
    VCard: {
      style: "border-radius: 10px; border-color: #E4E7EC;",
    },
    VTextField: {
      variant: "outlined",
      density: "comfortable",
    },
    VSelect: {
      variant: "outlined",
      density: "comfortable",
    },
    VTextarea: {
      variant: "outlined",
      density: "comfortable",
    },
  },
});
