import { expect, test } from "@playwright/test";
import { signInAs } from "./helpers";

// Not a test: it takes the pictures for the README from the running demo.
// Run it with E2E_SCREENSHOTS=1. The files go to docs/screenshots.
test.skip(!process.env.E2E_SCREENSHOTS, "only runs when the screenshots are wanted");

const out = (name: string) => ({ path: `../docs/screenshots/${name}.png`, animations: "disabled" as const });

test("take the README screenshots", async ({ page }) => {
  test.setTimeout(180_000);
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/login");
  await expect(page.getByText(/^Demo accounts\./)).toBeVisible();
  await page.screenshot(out("login"));

  await signInAs(page, "Sophie Gruber");
  await page.getByText("Validation lifecycle").waitFor();
  await page.screenshot(out("dashboard"));

  await page.goto("/applications/1");
  await page.getByText("Release gate for version 3.3").waitFor();
  await page.screenshot(out("release-gate"));

  await page.goto("/applications/1?tab=requirements");
  await page.getByText("Requirements and risk assessment").waitFor();
  await page.screenshot(out("requirements-risk"));

  await page.goto("/applications/1?tab=trace");
  await page.getByText("Traceability matrix").waitFor();
  await page.screenshot(out("traceability"));

  await page.goto("/applications/1?tab=runs");
  await page.getByRole("row", { name: /Failed/ }).getByRole("link").first().click();
  await page.getByText("Expected result").first().waitFor();
  await page.screenshot(out("test-run"));

  await page.goto("/changes/1");
  await page.getByText("Impact assessment by department").waitFor();
  await page.screenshot({ ...out("change-control"), fullPage: true });

  await page.goto("/training");
  await page.getByText("Training matrix").waitFor();
  await page.screenshot(out("training"));

  await page.goto("/reports?r=traceability");
  await page.getByRole("button", { name: "Show SQL" }).click();
  await page.locator("pre.sql").waitFor();
  await page.screenshot(out("sql-reports"));

  await signInAsFromMenu(page, "Eva Mayr");
  await page.goto("/audit");
  await page.getByRole("button", { name: "Verify integrity" }).click();
  await page.getByText("The chain is intact.").waitFor();
  await page.screenshot(out("audit-trail"));

  await page.goto("/changes/1");
  await page.emulateMedia({ colorScheme: "dark" });
  await page.evaluate(() => { document.documentElement.dataset.theme = "dark"; });
  await page.goto("/");
  await page.evaluate(() => { document.documentElement.dataset.theme = "dark"; });
  await page.getByText("Validation lifecycle").waitFor();
  await page.screenshot(out("dashboard-dark"));
});

async function signInAsFromMenu(page: import("@playwright/test").Page, fullName: string) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await signInAs(page, fullName);
}
