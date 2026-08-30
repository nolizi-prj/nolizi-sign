<script setup lang="ts">
/**
 * Signature capture dialog: draw with a mouse/stylus/touch (signature_pad,
 * "Draw" tab), type a name rendered in a cursive font onto a canvas
 * ("Type" tab), or upload an existing signature image ("Upload" tab,
 * PNG/JPEG — re-rendered to a bounded transparent PNG). Either way, "Save"
 * emits a PNG data URL for the caller to upload via
 * POST /sign/{submitterId}/signature.
 *
 * When `savedImageUrl` is set (the caller already has an image to show —
 * either this user's account-level saved signature, or whatever was
 * captured earlier in this session for the field currently being edited),
 * the dialog opens on a "use saved / redraw" choice screen instead of
 * straight into the draw/type tabs. Picking "use saved" emits `useSaved`
 * (no re-upload needed — the caller already knows the signature id behind
 * that image) instead of `save`.
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

/** Create the SignaturePad instance (once) and (re)size its canvas whenever it's actually laid out. */
function ensurePad(): void {
  const canvas = drawCanvasRef.value;
  if (!canvas) return;
  if (!pad) {
    pad = new SignaturePadLib(canvas, { backgroundColor: "rgba(255,255,255,0)" });
  }
  if (!resizeObserver) {
    resizeObserver = new ResizeObserver(() => resizeDrawCanvas());
    resizeObserver.observe(canvas);
  }
  resizeDrawCanvas();
}

function clearDraw(): void {
  pad?.clear();
}

function renderTyped(): void {
  const canvas = typeCanvasRef.value;
  if (!canvas || canvas.offsetWidth === 0 || canvas.offsetHeight === 0) return;
  const ratio = Math.max(window.devicePixelRatio || 1, 1);
  canvas.width = canvas.offsetWidth * ratio;
  canvas.height = canvas.offsetHeight * ratio;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.scale(ratio, ratio);
  ctx.clearRect(0, 0, canvas.offsetWidth, canvas.offsetHeight);
  ctx.font = "42px 'Brush Script MT', 'Segoe Script', cursive";
  ctx.fillStyle = "#1a1a2e";
  ctx.textBaseline = "middle";
  ctx.fillText(typedName.value, 12, canvas.offsetHeight / 2);
}

watch(typedName, () => {
  if (tab.value === "type") nextTick(renderTyped);
});

// Output bounds for uploaded images: plenty for a signature box while
// keeping the re-rendered PNG far below the backend's 1 MB cap.
const UPLOAD_MAX_W = 800;
const UPLOAD_MAX_H = 300;

function onFileChosen(event: Event): void {
  errorMessage.value = null;
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = ""; // allow re-picking the same file
  if (!file) return;
  if (!["image/png", "image/jpeg"].includes(file.type)) {
    errorMessage.value = "Please choose a PNG or JPEG image.";
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

/** Re-render the uploaded image to a bounded PNG (aspect-fit, transparent padding-free). */
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
  else nextTick(renderTyped);
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
    max-width="520"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <v-card>
      <v-card-title>{{ isInitials ? "Initials" : "Signature" }}</v-card-title>
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
          <v-tabs v-model="tab">
            <v-tab value="draw">Draw</v-tab>
            <v-tab value="type">Type</v-tab>
            <v-tab value="upload">Upload</v-tab>
          </v-tabs>

          <v-window v-model="tab" class="mt-4">
            <v-window-item value="draw">
              <div class="canvas-frame">
                <canvas ref="drawCanvasRef" class="signature-canvas" />
              </div>
              <div class="d-flex justify-end mt-2">
                <v-btn size="small" variant="text" @click="clearDraw">Clear</v-btn>
              </div>
            </v-window-item>
            <v-window-item value="type">
              <v-text-field
                v-model="typedName"
                :label="isInitials ? 'Type your initials' : 'Type your name'"
                autofocus
                class="mb-2"
                hide-details
              />
              <div class="canvas-frame mt-2">
                <canvas ref="typeCanvasRef" class="signature-canvas" />
              </div>
            </v-window-item>
            <v-window-item value="upload">
              <v-file-input
                accept="image/png,image/jpeg"
                :label="isInitials ? 'Choose an initials image' : 'Choose a signature image'"
                prepend-icon="mdi-image-outline"
                density="compact"
                hide-details
                class="mb-2"
                @change="onFileChosen"
              />
              <div v-if="uploadedPreviewUrl" class="canvas-frame upload-preview mt-2">
                <img :src="uploadedPreviewUrl" alt="Uploaded signature preview" />
              </div>
              <p v-else class="text-medium-emphasis text-body-2 mt-2">
                PNG or JPEG. A photo or scan of your signature works best on a plain background.
              </p>
            </v-window-item>
          </v-window>
        </template>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="cancel">Cancel</v-btn>
        <v-btn v-if="step === 'capture'" color="primary" @click="save">Save</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.canvas-frame {
  border: 1px dashed rgba(0, 0, 0, 0.3);
  border-radius: 4px;
}

.signature-canvas {
  width: 100%;
  height: 160px;
  display: block;
  touch-action: none;
}

.saved-preview {
  border: 1px solid rgba(0, 0, 0, 0.15);
  border-radius: 4px;
  padding: 8px;
  display: flex;
  justify-content: center;
}

.saved-preview img {
  max-width: 100%;
  max-height: 160px;
}

.upload-preview {
  display: flex;
  justify-content: center;
  padding: 8px;
}

.upload-preview img {
  max-width: 100%;
  max-height: 160px;
}
</style>
