/**
 * MediaOS Playwright smoke tests.
 */
import { test, expect } from "@playwright/test";

const base = process.env.PLAYWRIGHT_BASE_URL || "";

test.beforeEach(() => {
  test.skip(!base, "Set PLAYWRIGHT_BASE_URL to run E2E against a live MediaOS UI");
});

test("home loads", async ({ page }) => {
  await page.goto(base + "/");
  await expect(page.locator("body")).toBeVisible();
});

test("movies page reachable", async ({ page }) => {
  await page.goto(base + "/");
  const nav = page.getByRole("button", { name: /movies/i }).or(page.getByText(/^Movies$/i));
  if (await nav.first().isVisible().catch(() => false)) await nav.first().click();
  await expect(page.locator("body")).toBeVisible();
});

test("tracking page reachable", async ({ page }) => {
  await page.goto(base + "/");
  const nav = page.getByRole("button", { name: /track/i }).or(page.getByText(/^Tracking$/i));
  if (await nav.first().isVisible().catch(() => false)) await nav.first().click();
  await expect(page.locator("body")).toBeVisible();
});

test("livetv page reachable", async ({ page }) => {
  await page.goto(base + "/");
  const nav = page.getByRole("button", { name: /live/i }).or(page.getByText(/Live TV/i));
  if (await nav.first().isVisible().catch(() => false)) await nav.first().click();
  await expect(page.locator("body")).toBeVisible();
});

test("games page reachable", async ({ page }) => {
  await page.goto(base + "/");
  const nav = page.getByRole("button", { name: /games/i }).or(page.getByText(/^Games$/i));
  if (await nav.first().isVisible().catch(() => false)) await nav.first().click();
  await expect(page.locator("body")).toBeVisible();
});
