<script setup lang="ts">
// Catch-all for unknown paths. The backend's SPA fallback serves index.html
// for anything, so a stale bookmark or typo lands here instead of an app bar
// over a blank page.
</script>

<template>
  <v-container class="fill-height">
    <v-row justify="center">
      <v-col cols="12" sm="8" md="5" class="text-center">
        <v-icon icon="mdi-file-question-outline" size="64" class="mb-4 text-medium-emphasis" />
        <h1 class="text-h5 mb-2">Page not found</h1>
        <p class="text-body-2 text-medium-emphasis mb-6">
          This page doesn't exist — the link may be out of date.
        </p>
        <v-btn color="primary" variant="flat" :to="{ name: 'dashboard' }">Back to dashboard</v-btn>
      </v-col>
    </v-row>
  </v-container>
</template>
