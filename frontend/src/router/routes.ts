/**
 * The application's route table.
 *
 * Lives apart from ./index.ts so it can be resolved without a DOM: index.ts
 * calls `createWebHistory()` at module scope, which needs `document`, and the
 * frozen acceptance case that proves "Sign in again" targets a route this app
 * actually has (spec/0003 A-203) runs under vitest's `node` environment.
 * Route names are the stable identifiers other tasks navigate by.
 */
import type { RouteRecordRaw } from "vue-router";

export const routes: RouteRecordRaw[] = [
  {
    path: "/",
    name: "landing",
    component: () => import("../views/LandingView.vue"),
    meta: { public: true },
  },
  {
    path: "/dashboard",
    name: "dashboard",
    component: () => import("../views/DashboardView.vue"),
  },
  {
    path: "/templates",
    name: "templates",
    component: () => import("../views/TemplatesView.vue"),
  },
  {
    path: "/templates/:id/build",
    name: "template-builder",
    component: () => import("../views/TemplateBuilderView.vue"),
    props: true,
  },
  {
    path: "/envelopes/:id",
    name: "envelope-detail",
    component: () => import("../views/EnvelopeDetailView.vue"),
    props: true,
  },
  {
    path: "/send/:templateId?",
    name: "send",
    component: () => import("../views/SendView.vue"),
    props: true,
  },
  {
    path: "/send/draft/:draftId",
    name: "send-draft",
    component: () => import("../views/SendView.vue"),
    props: true,
  },
  {
    path: "/sign/t/:accessUid",
    name: "sign-external",
    component: () => import("../views/ExternalSignView.vue"),
    props: true,
    // External signers have no session — access is proven by the emailed
    // token + verification code, not by login.
    meta: { public: true },
  },
  {
    path: "/sign/:submitterId",
    name: "sign",
    component: () => import("../views/SignView.vue"),
    props: true,
  },
  {
    path: "/branding",
    name: "branding",
    component: () => import("../views/BrandingView.vue"),
  },
  {
    path: "/admin/users",
    name: "admin-users",
    component: () => import("../views/AdminUsersView.vue"),
    // Backend writes are admin-gated anyway; this keeps the user directory
    // from being browsable by any signed-in non-admin who types the URL.
    meta: { requiresAdmin: true },
  },
  {
    path: "/login",
    name: "login",
    component: () => import("../views/LoginView.vue"),
    // Reachable without a session, or nobody could ever log in.
    meta: { public: true },
  },
  {
    path: "/terms",
    name: "terms",
    component: () => import("../views/TermsView.vue"),
    meta: { public: true },
  },
  {
    path: "/privacy",
    name: "privacy",
    component: () => import("../views/PrivacyView.vue"),
    meta: { public: true },
  },
  {
    path: "/signed-out",
    name: "signed-out",
    component: () => import("../views/SignedOutView.vue"),
    // Reachable without a session — otherwise the guard would bounce a
    // freshly-logged-out user straight back into the Entra login flow,
    // where SSO silently signs them in again.
    meta: { public: true },
  },
  {
    // Catch-all: the backend serves index.html for any path (SPA fallback),
    // so without this a stale bookmark renders an app bar over a blank page.
    path: "/:pathMatch(.*)*",
    name: "not-found",
    component: () => import("../views/NotFoundView.vue"),
    meta: { public: true },
  },
];
