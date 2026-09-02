<script setup lang="ts">
/**
 * Pumasi Sign — Front-End Design & Branding Customizer.
 * Allows organizations to customize logo, brand colors, company title, and recipient experience.
 */
import { onMounted, ref, watch } from "vue";
import { useBrandingStore } from "../store/branding";
import { useUiStore } from "../store/ui";
import LogoCropDialog from "../components/LogoCropDialog.vue";

const branding = useBrandingStore();
const ui = useUiStore();

const companyName = ref(branding.companyName);
const logoDataUrl = ref<string | null>(branding.logoDataUrl);
const primaryColor = ref(branding.primaryColor);
const welcomeMessage = ref(branding.welcomeMessage);
const saving = ref(false);
const cropOpen = ref(false);
const selectedLogoFile = ref<File | null>(null);

const COLOR_PRESETS = [
  { name: "Pumasi Indigo", hex: "#1A56DB" },
  { name: "Emerald Forest", hex: "#067647" },
  { name: "Royal Violet", hex: "#6941C6" },
  { name: "Crimson Rose", hex: "#E11D48" },
  { name: "Warm Amber", hex: "#B54708" },
  { name: "Midnight Slate", hex: "#0F172A" },
];

onMounted(async () => {
  await branding.fetchBranding();
  companyName.value = branding.companyName;
  logoDataUrl.value = branding.logoDataUrl;
  primaryColor.value = branding.primaryColor;
  welcomeMessage.value = branding.welcomeMessage;
});

watch(primaryColor, (newColor) => {
  branding.applyThemeColors(newColor);
});

function onLogoSelected(event: Event) {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;

  if (file.size > 2 * 1024 * 1024) {
    ui.toast("Logo file should be under 2 MB.");
    target.value = "";
    return;
  }
  selectedLogoFile.value = file;
  cropOpen.value = true;
  target.value = "";
}

function useCroppedLogo(dataUrl: string) {
  logoDataUrl.value = dataUrl;
  selectedLogoFile.value = null;
}

function removeLogo() {
  logoDataUrl.value = null;
}

async function save() {
  saving.value = true;
  try {
    await branding.saveBranding({
      companyName: companyName.value,
      logoDataUrl: logoDataUrl.value,
      primaryColor: primaryColor.value,
      welcomeMessage: welcomeMessage.value,
    });
    ui.toast("Branding and design settings saved!");
  } catch (err: any) {
    ui.toast("Could not save branding settings.");
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <v-container class="py-8" max-width="1100">
    <div class="mb-6">
      <h1 class="text-h4 font-weight-bold text-slate-900 mb-1">Branding &amp; Design Customization</h1>
      <p class="text-medium-emphasis">
        Personalize your signing portal with your company logo, custom colors, and recipient welcome experience.
      </p>
    </div>

    <v-row>
      <!-- Left Column: Customization Controls -->
      <v-col cols="12" md="6">
        <v-card class="pa-5 mb-6" variant="flat" border>
          <h2 class="text-h6 font-weight-bold mb-4">Organization Identity</h2>

          <v-text-field
            v-model="companyName"
            label="Company / Organization Name"
            hint="Displayed on navigation headers, emails, and completion certificates."
            persistent-hint
            class="mb-4"
          />

          <v-textarea
            v-model="welcomeMessage"
            label="Recipient Welcome Message"
            rows="3"
            hint="Shown to external signers when they open a signature request."
            persistent-hint
            class="mb-4"
          />

          <div class="mb-5">
            <label class="text-subtitle-2 font-weight-bold d-block mb-2">Company Logo</label>
            <div v-if="logoDataUrl" class="d-flex align-center gap-3 p-3 border rounded bg-slate-50 mb-3">
              <img :src="logoDataUrl" alt="Company Logo" style="max-height: 48px; max-width: 160px; object-fit: contain;" />
              <v-spacer />
              <v-btn size="small" variant="text" color="error" prepend-icon="mdi-delete" @click="removeLogo">
                Remove Logo
              </v-btn>
            </div>
            <div class="mb-3">
              <input type="file" accept="image/png,image/jpeg,image/webp" @change="onLogoSelected" class="d-block" />
              <span class="text-caption text-medium-emphasis d-block mt-1">Recommended output: 600 × 180 px (10:3). PNG, JPEG, or WebP up to 2 MB.</span>
              <span class="text-caption text-medium-emphasis">After choosing an image, resize and crop it before saving.</span>
            </div>
          </div>

          <div class="mb-6">
            <label class="text-subtitle-2 font-weight-bold d-block mb-2">Primary Brand Color</label>
            <div class="d-flex flex-wrap mb-3" style="gap: 8px;">
              <v-btn
                v-for="preset in COLOR_PRESETS"
                :key="preset.hex"
                size="small"
                variant="flat"
                :style="{ backgroundColor: preset.hex, color: '#ffffff' }"
                @click="primaryColor = preset.hex"
                class="mr-2 mb-2 text-none"
              >
                <v-icon v-if="primaryColor.toLowerCase() === preset.hex.toLowerCase()" icon="mdi-check" start size="16" />
                {{ preset.name }}
              </v-btn>
            </div>

            <div class="d-flex align-center gap-3">
              <input type="color" v-model="primaryColor" style="width: 44px; height: 38px; cursor: pointer; border: 1px solid #e4e7ec; border-radius: 6px;" />
              <v-text-field v-model="primaryColor" label="Custom Hex Color" density="compact" hide-details style="max-width: 160px;" />
            </div>
          </div>

          <v-btn
            color="primary"
            size="large"
            block
            :loading="saving"
            prepend-icon="mdi-content-save"
            @click="save"
          >
            Save Design Settings
          </v-btn>
        </v-card>
      </v-col>

      <!-- Right Column: Live Recipient Signing Preview -->
      <v-col cols="12" md="6">
        <v-card class="pa-5 bg-slate-50" variant="flat" border>
          <div class="d-flex align-center justify-space-between mb-4">
            <h2 class="text-h6 font-weight-bold">Live Recipient Preview</h2>
            <v-chip size="small" color="primary" variant="tonal">Real-time</v-chip>
          </div>
          <p class="text-caption text-medium-emphasis mb-4">
            This is how your clients and external signers will experience your signing links.
          </p>

          <!-- Mock Signing Portal Card -->
          <div class="pumasi-card pa-6 bg-white border rounded-lg shadow-sm">
            <!-- Header with Custom Logo -->
            <div class="d-flex align-center pb-4 mb-4 border-b">
              <img
                :src="logoDataUrl || '/logo-mark.png'"
                alt="Logo"
                style="height: 36px; max-width: 140px; object-fit: contain;"
                class="mr-3"
              />
              <span class="text-h6 font-weight-bold">{{ companyName || 'Pumasi Sign' }}</span>
            </div>

            <!-- Recipient Banner -->
            <div class="pa-4 rounded mb-4" :style="{ backgroundColor: primaryColor + '12', borderLeft: '4px solid ' + primaryColor }">
              <p class="text-subtitle-2 font-weight-bold mb-1" :style="{ color: primaryColor }">
                Signature Requested
              </p>
              <p class="text-body-2 mb-0 text-slate-700">
                {{ welcomeMessage || 'Please review and sign this document.' }}
              </p>
            </div>

            <!-- Sample Document Title -->
            <div class="mb-4">
              <span class="text-caption text-medium-emphasis d-block">Document Title</span>
              <span class="text-body-1 font-weight-medium">Mutual Non-Disclosure Agreement.pdf</span>
            </div>

            <!-- Action Button Preview -->
            <div class="pt-2">
              <v-btn
                block
                size="large"
                :style="{ backgroundColor: primaryColor, color: '#ffffff' }"
                prepend-icon="mdi-draw"
                class="mb-3"
              >
                Review &amp; Sign Document
              </v-btn>
              <div class="text-center">
                <span class="text-caption text-medium-emphasis">
                  Powered by Pumasi Sign &middot; Cryptographic Audit Trail
                </span>
              </div>
            </div>
          </div>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
  <LogoCropDialog v-model="cropOpen" :file="selectedLogoFile" @cropped="useCroppedLogo" />
</template>
