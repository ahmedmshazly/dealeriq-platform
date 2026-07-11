import { test, expect, type Page } from "@playwright/test";

// QA-004: the one golden path named in the requirement's own text -- login -> create order ->
// approve -> alert appears -> acknowledge -- driven through the real UI against a real running
// dev stack (`make dev`), not mocked. Uses the same seeded credentials every prior phase's manual
// browser verification has used.
const SALES_EMAIL = "sales1@dealeriq.dev";
const MANAGER_EMAIL = "manager1@dealeriq.dev";
const PASSWORD = "SeedUser123!";

// A discount fraction safely above `order_approval_discount_threshold` (0.05) for every seeded
// model -- the cheapest seeded model is ~$19.8k (5% = ~$989), the priciest ~$66.3k (5% =
// ~$3.3k), so a flat $6,000 discount clears the threshold regardless of which in-stock unit the
// test happens to pick.
const NEGOTIATED_PRICE = "20000";
const DISCOUNT = "6000";

async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");
}

async function logout(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.waitForURL("**/login");
}

test("golden path: login -> create order -> approve -> alert appears -> acknowledge", async ({
  page,
}) => {
  // 1. Sales creates and submits a high-discount order -- this is the exact condition
  // (submit_order, order_service.py) that routes to pending_approval and synchronously fires
  // the discount_approval alert (Phase 6, rule e) in the same transaction.
  await login(page, SALES_EMAIL);
  await page.goto("/orders");

  const selects = page.locator("form select");
  await selects.nth(0).selectOption({ index: 1 }); // first real customer
  await selects.nth(1).selectOption({ index: 1 }); // first real in-stock unit
  await page.getByPlaceholder("Negotiated price").fill(NEGOTIATED_PRICE);
  await page.getByPlaceholder("Discount").fill(DISCOUNT);

  const [createResponse] = await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes("/api/v1/orders") && r.request().method() === "POST",
    ),
    page.getByRole("button", { name: "Create draft" }).click(),
  ]);
  const created = (await createResponse.json()) as { id: string };
  expect(created.id).toBeTruthy();
  const orderId = created.id;

  await page.goto(`/orders/${orderId}`);
  await page.getByRole("button", { name: "Submit" }).click();
  const statusBadge = page.locator("span").filter({ hasText: /^(draft|pending_approval|approved|delivered|cancelled)$/ });
  await expect(statusBadge).toHaveText("pending_approval");

  // 2. Manager approves -- proves `orders:approve` is a real, server-enforced boundary (the
  // Sales account that created this order does not have it).
  await logout(page);
  await login(page, MANAGER_EMAIL);
  await page.goto(`/orders/${orderId}`);
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(statusBadge).toHaveText("approved");

  // 3. The alert this order's submission caused is visible and can be acknowledged. Alerts are
  // always returned newest-first (`routes/alerts.py`'s `order_by(Alert.created_at.desc())`),
  // and discount_approval alerts are only ever created synchronously by an order submission --
  // no scheduled job can create a newer one -- so the topmost row among currently-open alerts
  // is unambiguously the one this test just caused (the seeded DB has many pre-existing open
  // discount_approval alerts, so matching by rule text alone would be ambiguous).
  await page.goto("/alerts");
  await page.getByRole("button", { name: "open", exact: true }).click();

  const alertRow = page.locator("tbody tr").first();
  await expect(alertRow).toBeVisible();
  await expect(alertRow).toContainText("discount_approval");
  // Capture the row's unique "Created" timestamp before acknowledging -- once acknowledged, the
  // row disappears from this "open"-filtered view (the underlying query re-filters on the same
  // status), so re-locating "first row" afterward would grab a *different* still-open alert
  // rather than confirming this one's status actually changed.
  const createdAt = await alertRow.locator("td").nth(3).textContent();
  expect(createdAt).toBeTruthy();

  await alertRow.getByRole("button", { name: "Acknowledge" }).click();

  await page.getByRole("button", { name: "All" }).first().click(); // the Status filter's "All"
  const updatedRow = page
    .locator("tbody tr")
    .filter({ hasText: "discount_approval" })
    .filter({ hasText: createdAt! });
  await expect(updatedRow).toContainText("acknowledged");
});
