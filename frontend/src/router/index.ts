/**
 * The router: history, the route table (./routes.ts), and a global guard
 * that ensures `fetchMe()` has run before any route resolves and routes to
 * the `/login` page (preserving the target path as `next`) when there is no
 * session.
 */
import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../store/auth";
import { routes } from "./routes";

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();

  // The landing page is public, but it is a marketing page for people who do
  // not have an account yet. A signed-in visitor who opens the app root wants
  // the product, so resolve the session even though the route is public and
  // hand them to their dashboard. (In-app navigation never comes here — the
  // app bar's brand link targets `dashboard` directly.)
  if (to.name === "landing") {
    if (!auth.fetched) {
      await auth.fetchMe();
    }
    return auth.me ? { name: "dashboard" } : true;
  }

  if (to.meta.public) {
    return true;
  }
  if (!auth.fetched) {
    await auth.fetchMe();
  }
  if (!auth.me) {
    return { name: "login", query: { next: to.fullPath } };
  }
  if (to.meta.requiresAdmin && !auth.me.is_admin) {
    return { name: "dashboard" };
  }
  return true;
});

export default router;
