import "vuetify/styles";
import "@mdi/font/css/materialdesignicons.css";
import { createVuetify } from "vuetify";
import * as components from "vuetify/components";
import * as directives from "vuetify/directives";

/**
 * Pumasi Sign theme. A single light theme on purpose: the product is
 * documents-on-white, and mixing a dark app shell with white PDF pages
 * reads worse than a consistently light UI. `style.css` pins
 * `color-scheme: light` for the same reason (native inputs overlaid on
 * PDF pages must not flip to dark UA styling on a dark-mode OS).
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
          primary: "#1C3A62", // Pumasi navy (wordmark color)
          secondary: "#2CA6E0", // Pumasi blue (logo mark)
          background: "#F7F6F3", // warm paper, not stock grey
          surface: "#FFFFFF",
          success: "#2E7D32",
          warning: "#B45309",
          error: "#B3261E",
          info: "#2CA6E0",
        },
      },
    },
  },
  defaults: {
    VBtn: { style: "text-transform: none; letter-spacing: normal;" },
  },
});
