/**
 * Auth store: the current user (or null if not logged in) plus a one-shot
 * `fetchMe()` used by the router's global guard (see router/index.ts).
 *
 * `fetched` (not `me`) is what guards re-fetching — `me` legitimately stays
 * null after a failed fetch, and we don't want every navigation to re-hit
 * `GET /auth/me`.
 */
import { defineStore } from "pinia";
import { computed, ref } from "vue";
import http from "../utils/http";
import type { User } from "../types";

export const useAuthStore = defineStore("auth", () => {
  const me = ref<User | null>(null);
  const fetched = ref(false);

  const isAdmin = computed(() => me.value?.is_admin ?? false);
  const canSend = computed(() => me.value?.can_send ?? false);

  async function fetchMe(): Promise<void> {
    if (fetched.value) return;
    try {
      const { data } = await http.get<User>("/auth/me", { skipAuthRedirect: true });
      me.value = data;
    } catch {
      me.value = null;
    } finally {
      fetched.value = true;
    }
  }

  /** Force a re-fetch on the next call (e.g. after logging out). */
  function reset(): void {
    me.value = null;
    fetched.value = false;
  }

  return { me, fetched, isAdmin, canSend, fetchMe, reset };
});
