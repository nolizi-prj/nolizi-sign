<script setup lang="ts">
/**
 * Page-thumbnail rail for field-placement canvases — the template builder's
 * rail extracted so the send wizard's place-fields step gets the same
 * navigation instead of blind chevron paging. One button per page with a
 * live field-count badge; PdfPage's document cache means all thumbnails
 * share a single pdf.js document, so the rail stays cheap for long files.
 */
import PdfPage from "./PdfPage.vue";

const props = defineProps<{
  src: string;
  pageCount: number;
  current: number;
  /** Per-page field counts (index = 0-based page); missing entries read as 0. */
  fieldCounts?: number[];
}>();

const emit = defineEmits<{ "update:current": [page: number] }>();

function countOn(page: number): number {
  return props.fieldCounts?.[page] ?? 0;
}
</script>

<template>
  <nav v-if="pageCount > 1" class="thumb-rail" aria-label="Pages">
    <button
      v-for="n in pageCount"
      :key="n - 1"
      type="button"
      class="thumb"
      :class="{ on: n - 1 === current }"
      :aria-label="`Page ${n}${countOn(n - 1) > 0 ? `, ${countOn(n - 1)} fields` : ''}`"
      :aria-current="n - 1 === current ? 'page' : undefined"
      @click="emit('update:current', n - 1)"
    >
      <PdfPage :src="src" :page="n - 1" />
      <span class="thumb-label">
        {{ n }}
        <v-badge v-if="countOn(n - 1) > 0" :content="countOn(n - 1)" color="primary" inline />
      </span>
    </button>
  </nav>
</template>

<style scoped>
.thumb-rail {
  width: 74px;
  flex: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 80vh;
  overflow-y: auto;
  padding: 2px;
}

.thumb {
  border: 1px solid rgba(0, 0, 0, 0.15);
  border-radius: 4px;
  padding: 0;
  background: #fff;
  cursor: pointer;
  overflow: hidden;
  position: relative;
}

.thumb.on {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 1px;
}

.thumb-label {
  position: absolute;
  bottom: 2px;
  right: 4px;
  font-size: 10px;
  color: rgba(0, 0, 0, 0.6);
  background: rgba(255, 255, 255, 0.85);
  border-radius: 3px;
  padding: 0 3px;
  display: inline-flex;
  align-items: center;
}
</style>
