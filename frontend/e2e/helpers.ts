import { expect, type Page } from "@playwright/test";

export const DEMO_PASSWORD = "Demo-Valitrack-2026";

/** Sign in with the one-click demo account of a person (their full name is on the button). */
export async function signInAs(page: Page, fullName: string) {
  await page.goto("/login");
  await page.getByRole("button", { name: new RegExp(fullName) }).click();
  await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible();
}

export async function sign(page: Page, buttonName: RegExp | string, comment?: string) {
  const dialog = page.getByRole("dialog");
  if (comment) await dialog.getByLabel(/comment|reason|justification/i).fill(comment);
  await dialog.getByLabel("Password").fill(DEMO_PASSWORD);
  await dialog.getByRole("button", { name: buttonName }).click();
}
