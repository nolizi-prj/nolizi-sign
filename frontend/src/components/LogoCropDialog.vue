<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import { LOGO_OUTPUT_HEIGHT, LOGO_OUTPUT_WIDTH, logoPlacement } from "../utils/logoCrop";

const props = defineProps<{ modelValue: boolean; file: File | null }>();
const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  cropped: [dataUrl: string];
}>();

const canvasRef = ref<HTMLCanvasElement | null>(null);
const source = ref<HTMLImageElement | null>(null);
const objectUrl = ref<string | null>(null);
const zoom = ref(1);
const offsetX = ref(0);
const offsetY = ref(0);

function render(): void {
  const canvas = canvasRef.value;
  const image = source.value;
  if (!canvas || !image) return;
  canvas.width = LOGO_OUTPUT_WIDTH;
  canvas.height = LOGO_OUTPUT_HEIGHT;
  const context = canvas.getContext("2d");
  if (!context) return;
  context.clearRect(0, 0, canvas.width, canvas.height);
  const placed = logoPlacement(image.naturalWidth, image.naturalHeight, zoom.value, offsetX.value, offsetY.value);
  context.drawImage(image, placed.x, placed.y, placed.width, placed.height);
}

async function loadFile(file: File | null): Promise<void> {
  if (objectUrl.value) URL.revokeObjectURL(objectUrl.value);
  objectUrl.value = null;
  source.value = null;
  if (!file) return;
  zoom.value = 1;
  offsetX.value = 0;
  offsetY.value = 0;
  const url = URL.createObjectURL(file);
  objectUrl.value = url;
  const image = new Image();
  image.src = url;
  await image.decode();
  source.value = image;
  await nextTick();
  render();
}

watch(() => props.file, (file) => { void loadFile(file); }, { immediate: true });
watch(() => props.modelValue, (open) => { if (open) void nextTick(render); });
watch([zoom, offsetX, offsetY], render);

onBeforeUnmount(() => {
  if (objectUrl.value) URL.revokeObjectURL(objectUrl.value);
});

function close(): void {
  emit("update:modelValue", false);
}

function useLogo(): void {
  render();
  const dataUrl = canvasRef.value?.toDataURL("image/png");
  if (!dataUrl) return;
  emit("cropped", dataUrl);
  close();
}
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="760" @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-card-title>Resize and crop logo</v-card-title>
      <v-card-subtitle>Output: {{ LOGO_OUTPUT_WIDTH }} × {{ LOGO_OUTPUT_HEIGHT }} px (10:3). Transparent PNG output is preserved.</v-card-subtitle>
      <v-card-text>
        <div class="logo-crop-stage mb-5">
          <canvas ref="canvasRef" aria-label="Cropped logo preview" />
        </div>
        <v-slider v-model="zoom" min="1" max="3" step="0.01" label="Zoom" thumb-label />
        <v-slider v-model="offsetX" min="-100" max="100" step="1" label="Horizontal position" thumb-label />
        <v-slider v-model="offsetY" min="-100" max="100" step="1" label="Vertical position" thumb-label />
        <p class="text-caption text-medium-emphasis mb-0">Keep important logo details inside the dashed safe area. Wide, transparent artwork works best.</p>
      </v-card-text>
      <v-card-actions class="pa-4 pt-0">
        <v-spacer />
        <v-btn variant="text" @click="close">Cancel</v-btn>
        <v-btn color="primary" variant="flat" prepend-icon="mdi-crop" @click="useLogo">Use cropped logo</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.logo-crop-stage { padding: 22px; overflow: hidden; border-radius: 10px; background-color: #f2f4f7; background-image: linear-gradient(45deg, #e4e7ec 25%, transparent 25%), linear-gradient(-45deg, #e4e7ec 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #e4e7ec 75%), linear-gradient(-45deg, transparent 75%, #e4e7ec 75%); background-size: 20px 20px; background-position: 0 0, 0 10px, 10px -10px, -10px 0; }
.logo-crop-stage canvas { display: block; width: 100%; height: auto; aspect-ratio: 10 / 3; border: 2px dashed rgba(var(--v-theme-primary), .7); background: transparent; }
</style>
