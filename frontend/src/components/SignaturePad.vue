<script setup lang="ts">
/**
 * Signature capture dialog: draw with mouse/stylus/touch (signature_pad,
 * "Draw" tab), type a name rendered in a cursive font onto a canvas
 * ("Type" tab), or upload an existing signature image ("Upload" tab).
 * Supports DocuSign-style ink color selection (Navy Blue vs Pitch Black),
 * calligraphy font styles, vector stroke smoothing, and legal disclaimer.
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import SignaturePadLib from "signature_pad";

const props = defineProps<{
  modelValue: boolean;
  savedImageUrl?: string | null;
  /** "initials" captures a (smaller) initials stamp; defaults to a full signature. */
  mode?: "signature" | "initials";
  /** Prefill for the "Type" tab (e.g. derived initials like "YY"). */
  typedDefault?: string;
}>();

const isInitials = computed(() => props.mode === "initials");

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  save: [dataUrl: string];
  useSaved: [];
}>();

type Step = "choose" | "capture";
type Tab = "draw" | "type" | "upload";

const step = ref<Step>("capture");
const tab = ref<Tab>("draw");
const typedName = ref("");
const errorMessage = ref<string | null>(null);
const uploadedImage = ref<HTMLImageElement | null>(null);
const uploadedPreviewUrl = ref<string | null>(null);

// Ink Color Selection
const INK_NAVY = "#1A56DB";
const INK_BLACK = "#111827";
const inkColor = ref<string>(INK_NAVY);

// Cursive Font Styles for Type Tab
export interface FontStyleOption {
  id: string;
  name: string;
  fontFamily: string;
  fontSize: string;
}

const FONT_STYLES: FontStyleOption[] = [
  { id: "caveat", name: "Classic Cursive", fontFamily: "'Caveat', cursive, sans-serif", fontSize: "44px" },
  { id: "dancing", name: "Elegant Script", fontFamily: "'Dancing Script', cursive, sans-serif", fontSize: "40px" },
  { id: "greatvibes", name: "Formal Calligraphy", fontFamily: "'Great Vibes', cursive, serif", fontSize: "42px" },
  { id: "sacramento", name: "Casual Flow", fontFamily: "'Sacramento', cursive, sans-serif", fontSize: "46px" },
  { id: "nanum", name: "Brush Pen (한글/EN)", fontFamily: "'Nanum Pen Script', 'Caveat', cursive, sans-serif", fontSize: "46px" },
];

const selectedFontId = ref<string>("caveat");
const currentFont = computed(() => FONT_STYLES.find((f) => f.id === selectedFontId.value) || FONT_STYLES[0]);

const drawCanvasRef = ref<HTMLCanvasElement | null>(null);
const typeCanvasRef = ref<HTMLCanvasElement | null>(null);
let pad: SignaturePadLib | null = null;
let resizeObserver: ResizeObserver | null = null;

function resizeDrawCanvas(): void {
  const canvas = drawCanvasRef.value;
  if (!canvas || canvas.offsetWidth === 0 || canvas.offsetHeight === 0) return;
  const ratio = Math.max(window.devicePixelRatio || 1, 1);
  canvas.width = canvas.offsetWidth * ratio;
  canvas.height = canvas.offsetHeight * ratio;
  const ctx = canvas.getContext("2d");
  ctx?.scale(ratio, ratio);
  pad?.clear();
}

/** Create the SignaturePad instance with vector smoothing and active ink color */
function ensurePad(): void {
  const canvas = drawCanvasRef.value;
  if (!canvas) return;
  if (!pad) {
    pad = new SignaturePadLib(canvas, {
      backgroundColor: "rgba(255,255,255,0)",
      penColor: inkColor.value,
      minWidth: 1.5,
      maxWidth: 3.5,
      throttle: 16,
    });
  } else {
    pad.penColor = inkColor.value;
  }
  if (!resizeObserver) {
    resizeObserver = new ResizeObserver(() => resizeDrawCanvas());
    resizeObserver.observe(canvas);
  }
  resizeDrawCanvas();
}

watch(inkColor, (newColor) => {
  if (pad) pad.penColor = newColor;
  if (tab.value === "type") void renderTyped();
});

function clearDraw(): void {
  pad?.clear();
}

async function renderTyped(): Promise<void> {
  const canvas = typeCanvasRef.value;
  if (!canvas || canvas.offsetWidth === 0 || canvas.offsetHeight === 0) return;
  if ("fonts" in document) {
    try {
      await document.fonts.load(`${currentFont.value.fontSize} ${currentFont.value.fontFamily}`);
    } catch {}
  }
  const ratio = Math.max(window.devicePixelRatio || 1, 1);
  canvas.width = canvas.offsetWidth * ratio;
  canvas.height = canvas.offsetHeight * ratio;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.scale(ratio, ratio);
  ctx.clearRect(0, 0, canvas.offsetWidth, canvas.offsetHeight);
  ctx.font = `${currentFont.value.fontSize} ${currentFont.value.fontFamily}`;
  ctx.fillStyle = inkColor.value;
  ctx.textBaseline = "middle";
  ctx.fillText(typedName.value || (isInitials.value ? "AB" : "Adopt Signature"), 16, canvas.offsetHeight / 2);
}

watch([typedName, selectedFontId], () => {
  if (tab.value === "type") nextTick(() => void renderTyped());
});

// Output bounds for uploaded images
const UPLOAD_MAX_W = 800;
const UPLOAD_MAX_H = 300;

function onFileChosen(event: Event): void {
  errorMessage.value = null;
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
    errorMessage.value = "Please choose a PNG, JPEG, or WebP image.";
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    const image = new Image();
    image.onload = () => {
      uploadedImage.value = image;
      uploadedPreviewUrl.value = reader.result as string;
    };
    image.onerror = () => {
      errorMessage.value = "Couldn't read that image. Please try another file.";
    };
    image.src = reader.result as string;
  };
  reader.onerror = () => {
    errorMessage.value = "Couldn't read that file. Please try again.";
  };
  reader.readAsDataURL(file);
}

function uploadedToDataUrl(): string | null {
  const image = uploadedImage.value;
  if (!image || !image.naturalWidth || !image.naturalHeight) return null;
  const scale = Math.min(UPLOAD_MAX_W / image.naturalWidth, UPLOAD_MAX_H / image.naturalHeight, 1);
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
  canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/png");
}

watch(tab, (t) => {
  if (t === "draw") nextTick(ensurePad);
  else if (t === "type") nextTick(renderTyped);
});

function reset(): void {
  step.value = props.savedImageUrl ? "choose" : "capture";
  tab.value = "draw";
  typedName.value = props.typedDefault ?? "";
  errorMessage.value = null;
  uploadedImage.value = null;
  uploadedPreviewUrl.value = null;
  pad?.clear();
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    reset();
    nextTick(() => {
      if (step.value === "capture" && tab.value === "draw") ensurePad();
      else if (step.value === "capture" && tab.value === "type") renderTyped();
    });
  },
);

function chooseRedraw(): void {
  step.value = "capture";
  nextTick(() => {
    if (tab.value === "draw") ensurePad();
  });
}

function useSaved(): void {
  emit("useSaved");
  emit("update:modelValue", false);
}

function save(): void {
  errorMessage.value = null;
  if (tab.value === "draw") {
    if (!pad || pad.isEmpty()) {
      errorMessage.value = isInitials.value ? "Please draw your initials first." : "Please draw your signature first.";
      return;
    }
    emit("save", pad.toDataURL("image/png"));
  } else if (tab.value === "upload") {
    const dataUrl = uploadedToDataUrl();
    if (!dataUrl) {
      errorMessage.value = "Please choose an image first.";
      return;
    }
    emit("save", dataUrl);
  } else {
    if (!typedName.value.trim()) {
      errorMessage.value = isInitials.value ? "Please type your initials first." : "Please type your name first.";
      return;
    }
    renderTyped();
    const dataUrl = typeCanvasRef.value?.toDataURL("image/png");
    if (!dataUrl) {
      errorMessage.value = "Couldn't render the signature. Please try again.";
      return;
    }
    emit("save", dataUrl);
  }
  emit("update:modelValue", false);
}

function cancel(): void {
  emit("update:modelValue", false);
}

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
});
</script>

<template>
  <v-dialog
    :model-value="modelValue"
    max-width="560"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <v-card>
      <v-card-title class="d-flex align-center">
        <span>Adopt {{ isInitials ? "Initials" : "Signature" }}</span>
        <v-spacer />
        <!-- Ink Color Selector -->
        <div v-if="step === 'capture'" class="d-flex align-center ga-1 mr-1">
          <span class="text-caption text-medium-emphasis mr-1">Ink:</span>
          <button
            type="button"
            class="ink-chip"
            :class="{ 'ink-active': inkColor === INK_NAVY }"
            style="background-color: #1A56DB;"
            title="Navy Blue Ink"
            aria-label="Navy Blue Ink"
            @click="inkColor = INK_NAVY"
          />
          <button
            type="button"
            class="ink-chip"
            :class="{ 'ink-active': inkColor === INK_BLACK }"
            style="background-color: #111827;"
            title="Black Ink"
            aria-label="Black Ink"
            @click="inkColor = INK_BLACK"
          />
        </div>
      </v-card-title>

      <v-card-text>
        <v-alert v-if="errorMessage" type="error" density="compact" class="mb-4">{{ errorMessage }}</v-alert>

        <template v-if="step === 'choose'">
          <p class="text-medium-emphasis mb-2">
            {{ isInitials ? "Use your initials from earlier, or draw new ones." : "Use your saved signature, or draw a new one." }}
          </p>
          <div class="saved-preview mb-4">
            <img :src="savedImageUrl ?? ''" :alt="isInitials ? 'Saved initials' : 'Saved signature'" />
          </div>
          <div class="d-flex justify-end ga-2">
            <v-btn variant="text" @click="chooseRedraw">Redraw</v-btn>
            <v-btn color="primary" @click="useSaved">Use saved</v-btn>
          </div>
        </template>

        <template v-else>
          <v-tabs v-model="tab" density="comfortable" color="primary">
            <v-tab value="draw" prepend-icon="mdi-draw-pen">Draw</v-tab>
            <v-tab value="type" prepend-icon="mdi-format-font">Type</v-tab>
            <v-tab value="upload" prepend-icon="mdi-upload">Upload</v-tab>
          </v-tabs>

          <v-window v-model="tab" class="mt-3">
            <!-- Draw Tab -->
            <v-window-item value="draw">
              <div class="canvas-frame">
                <canvas ref="drawCanvasRef" class="signature-canvas" />
              </div>
              <div class="d-flex align-center justify-space-between mt-2">
                <span class="text-caption text-medium-emphasis">Draw with your mouse, stylus, or fingertip</span>
                <v-btn size="small" variant="text" prepend-icon="mdi-eraser" @click="clearDraw">Clear</v-btn>
              </div>
            </v-window-item>

            <!-- Type Tab -->
            <v-window-item value="type">
              <v-text-field
                v-model="typedName"
                :label="isInitials ? 'Type your initials' : 'Type your legal name'"
                placeholder="e.g. John Doe"
                autofocus
                density="comfortable"
                class="mb-2"
                hide-details
              />

              <!-- Style Selection Cards -->
              <div class="style-cards-grid mt-2 mb-3">
                <button
                  v-for="font in FONT_STYLES"
                  :key="font.id"
                  type="button"
                  class="font-style-card"
                  :class="{ 'font-card-active': selectedFontId === font.id }"
                  @click="selectedFontId = font.id"
                >
                  <span class="font-preview-sample" :style="{ fontFamily: font.fontFamily, color: inkColor }">
                    {{ typedName.trim() || (isInitials ? "JD" : "John Doe") }}
                  </span>
                  <span class="font-name-label">{{ font.name }}</span>
                </button>
              </div>

              <div class="canvas-frame mt-1">
                <canvas ref="typeCanvasRef" class="signature-canvas" />
              </div>
            </v-window-item>

            <!-- Upload Tab -->
            <v-window-item value="upload">
              <v-file-input
                accept="image/png,image/jpeg,image/webp"
                :label="isInitials ? 'Choose an initials image' : 'Choose a signature image'"
                prepend-icon="mdi-image-outline"
                density="comfortable"
                hide-details
                class="mb-2"
                @change="onFileChosen"
              />
              <div v-if="uploadedPreviewUrl" class="canvas-frame upload-preview mt-2">
                <img :src="uploadedPreviewUrl" alt="Uploaded signature preview" />
              </div>
              <p v-else class="text-medium-emphasis text-body-2 mt-2">
                PNG, JPEG, or WebP. High-contrast scans or photos on a white background work best.
              </p>
            </v-window-item>
          </v-window>

          <!-- Legal Binding Consent Disclaimer -->
          <div class="legal-disclaimer mt-3 pa-2 rounded bg-grey-lighten-4">
            <p class="text-caption text-medium-emphasis mb-0">
              <v-icon icon="mdi-shield-check" size="14" color="primary" class="mr-1" />
              By clicking <strong>Adopt & Sign</strong>, I agree that this electronic signature is the legally binding equivalent of my physical handwritten signature.
            </p>
          </div>
        </template>
      </v-card-text>

      <v-card-actions class="pa-4 pt-1">
        <v-spacer />
        <v-btn variant="text" @click="cancel">Cancel</v-btn>
        <v-btn v-if="step === 'capture'" color="primary" variant="flat" aria-label="Save" @click="save">Adopt &amp; Sign</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.ink-chip {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  outline: none;
  transition: transform 0.15s ease, border-color 0.15s ease;
}

.ink-chip:hover {
  transform: scale(1.15);
}

.ink-active {
  border-color: #ffffff;
  box-shadow: 0 0 0 2px #1A56DB;
}

.canvas-frame {
  border: 1px dashed rgba(0, 0, 0, 0.25);
  border-radius: 6px;
  background-color: #fafbfc;
}

.signature-canvas {
  width: 100%;
  height: 150px;
  display: block;
  touch-action: none;
}

.style-cards-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.font-style-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 12px;
  border: 1px solid rgba(0, 0, 0, 0.15);
  border-radius: 6px;
  background: #ffffff;
  cursor: pointer;
  transition: all 0.15s ease;
}

.font-style-card:hover {
  border-color: #1A56DB;
  background: #F0F5FF;
}

.font-card-active {
  border-color: #1A56DB;
  background: #EFF6FF;
  box-shadow: 0 0 0 1px #1A56DB;
}

.font-preview-sample {
  font-size: 1.35rem;
  line-height: 1.3;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.font-name-label {
  font-size: 0.72rem;
  color: rgba(0, 0, 0, 0.55);
  margin-top: 2px;
}

.saved-preview,
.upload-preview {
  border: 1px solid rgba(0, 0, 0, 0.15);
  border-radius: 6px;
  padding: 8px;
  display: flex;
  justify-content: center;
  background: #ffffff;
}

.saved-preview img,
.upload-preview img {
  max-width: 100%;
  max-height: 140px;
}

.legal-disclaimer {
  border: 1px solid rgba(0, 0, 0, 0.08);
}
</style>
