import { expect, test } from "@playwright/test";
import { sign, signInAs } from "./helpers";

test("a visitor can sign in with a demo account and sees the lifecycle board", async ({ page }) => {
  await signInAs(page, "Sophie Gruber");
  await expect(page.getByRole("heading", { name: /Good to see you, Sophie/ })).toBeVisible();
  await expect(page.getByText("Validation lifecycle")).toBeVisible();
  await expect(page.getByRole("link", { name: "DocuControl" })).toBeVisible();
});

test("the audit trail can be verified", async ({ page }) => {
  await signInAs(page, "Paul Keller");
  await page.getByRole("link", { name: "Audit trail" }).click();
  await page.getByRole("button", { name: "Verify integrity" }).click();
  await expect(page.getByText("The chain is intact.")).toBeVisible();
});

test("a tester runs a test, signs it, and QA reviews it", async ({ page }) => {
  await signInAs(page, "Lukas Hofer");
  await page.goto("/applications/1?tab=tests");
  const row = page.getByRole("row", { name: /Review reminders and notifications/ });
  await row.getByRole("button", { name: /Execute/ }).click();
  await expect(page.getByRole("heading", { name: /Review reminders and notifications/ })).toBeVisible();

  for (const step of [1, 2]) {
    const card = page.locator(".step-card").nth(step - 1);
    await card.getByRole("group", { name: `Result of step ${step}` }).getByRole("button", { name: "Passed" }).click();
    await card.getByRole("button", { name: "Save result" }).click();
    await expect(card.locator(".chip", { hasText: "Passed" })).toBeVisible();
  }
  await page.getByRole("button", { name: "Complete the run and sign" }).click();
  await sign(page, /^Sign$/);
  await expect(page.getByText("Run completed.")).toBeVisible();

  // a different person reviews it
  await page.getByRole("button", { name: "Sign out" }).click();
  await signInAs(page, "Eva Mayr");
  await page.goto("/applications/1?tab=runs");
  await page.getByRole("link", { name: /RUN-\d+/ }).first().click();
  await page.getByRole("button", { name: "Review and sign" }).click();
  await sign(page, /^Sign$/, "Reviewed against the protocol.");
  await expect(page.getByText("Run reviewed.")).toBeVisible();
});

test("a signature with the wrong password is refused", async ({ page }) => {
  await signInAs(page, "Eva Mayr");
  await page.goto("/applications/1?tab=runs");
  await page.getByRole("link", { name: /RUN-\d+/ }).first().click();
  const review = page.getByRole("button", { name: "Review and sign" });
  if (await review.count()) {
    await review.click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Password").fill("not-the-password");
    await dialog.getByRole("button", { name: /^Sign$/ }).click();
    await expect(dialog.getByRole("alert")).toContainText("password is not correct");
  }
});

test("the change request shows departments, signatures and the release gate", async ({ page }) => {
  await signInAs(page, "Sophie Gruber");
  await page.goto("/changes/1");
  await expect(page.getByRole("heading", { name: "Upgrade DocuControl to 3.3" })).toBeVisible();
  await expect(page.getByText("Impact assessment by department")).toBeVisible();
  await expect(page.getByText("Regulatory Affairs")).toBeVisible();
  await expect(page.getByText("Release gate")).toBeVisible();
});

test("SQL reports show the SQL of the view", async ({ page }) => {
  await signInAs(page, "Sophie Gruber");
  await page.goto("/reports");
  await page.getByRole("button", { name: "Show SQL" }).click();
  await expect(page.locator("pre.sql")).toContainText("CREATE VIEW");
});
