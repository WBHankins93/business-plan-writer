import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const baseUrl = process.env.ACCESSIBILITY_BASE_URL || "http://127.0.0.1:3100";
const screenshotDirectory = resolve(process.cwd(), "../tmp/site-review");

const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};

const checkHeadingOrder = async (page) => {
  const levels = await page.locator("h1, h2, h3, h4, h5, h6").evaluateAll((headings) =>
    headings.map((heading) => Number(heading.tagName.slice(1))),
  );
  assert(levels.filter((level) => level === 1).length === 1, "The landing page must have exactly one h1.");
  levels.forEach((level, index) => {
    if (index > 0) assert(level <= levels[index - 1] + 1, `Heading level jumps from h${levels[index - 1]} to h${level}.`);
  });
};

const checkTouchTargets = async (page) => {
  const undersized = await page.locator("a[href], button, input, textarea, select").evaluateAll((elements) =>
    elements.flatMap((element) => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      if (style.visibility === "hidden" || style.display === "none" || rect.width === 0 || rect.height === 0) return [];
      return rect.width < 44 || rect.height < 44
        ? [{ name: element.getAttribute("aria-label") || element.textContent?.trim() || element.tagName, width: rect.width, height: rect.height }]
        : [];
    }),
  );
  assert(undersized.length === 0, `Interactive targets smaller than 44px: ${JSON.stringify(undersized)}`);
};

const checkNoHorizontalOverflow = async (page, label) => {
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }));
  assert(dimensions.content <= dimensions.viewport, `${label} has horizontal overflow: ${JSON.stringify(dimensions)}`);
};

const checkAnalytics = async (page) => {
  await page.evaluate(() => {
    window.dataLayer = [];
    document.addEventListener("click", (event) => event.preventDefault(), { capture: true });
  });

  const accountLink = page.locator(".heroActions .primaryAction");
  assert((await accountLink.getAttribute("href")) === "/intake", "Primary CTA does not lead to the intake route.");
  await accountLink.click();
  const accountEvents = await page.evaluate(() => window.dataLayer?.map((item) => item.event));
  assert(accountEvents?.includes("cta_click"), "Primary CTA did not emit cta_click.");
  assert(accountEvents?.includes("account_start"), "Primary CTA did not emit account_start.");

  await page.evaluate(() => { window.dataLayer = []; });
  await page.locator('.heroActions a[download]').click();
  const sampleEvents = await page.evaluate(() => window.dataLayer?.map((item) => item.event));
  assert(sampleEvents?.includes("sample_download"), "Sample link did not emit sample_download.");
};

await mkdir(screenshotDirectory, { recursive: true });
const browser = await chromium.launch({ headless: true });

try {
  const desktopContext = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const desktop = await desktopContext.newPage();
  await desktop.goto(baseUrl, { waitUntil: "networkidle" });
  assert((await desktop.locator("main").count()) === 1, "Landing page is missing its main landmark.");
  assert((await desktop.locator("nav").count()) >= 2, "Expected primary and footer navigation landmarks.");
  await checkHeadingOrder(desktop);
  await checkTouchTargets(desktop);
  await checkNoHorizontalOverflow(desktop, "Desktop layout");

  const axeResults = await new AxeBuilder({ page: desktop })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  assert(axeResults.violations.length === 0, `Axe found violations:\n${JSON.stringify(axeResults.violations, null, 2)}`);

  await desktop.keyboard.press("Tab");
  assert((await desktop.locator(":focus").textContent())?.trim() === "Skip to content", "Skip link is not the first keyboard focus target.");
  const focusOutline = await desktop.locator(":focus").evaluate((element) => getComputedStyle(element).outlineStyle);
  assert(focusOutline !== "none", "Focused skip link has no visible outline.");

  await checkAnalytics(desktop);
  await desktop.screenshot({ path: resolve(screenshotDirectory, "landing-desktop.png"), fullPage: true });

  const mobileContext = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  const mobile = await mobileContext.newPage();
  await mobile.goto(baseUrl, { waitUntil: "networkidle" });
  await checkTouchTargets(mobile);
  await checkNoHorizontalOverflow(mobile, "Mobile layout");
  await mobile.screenshot({ path: resolve(screenshotDirectory, "landing-mobile.png"), fullPage: true });

  const zoomContext = await browser.newContext({ viewport: { width: 640, height: 900 }, deviceScaleFactor: 1 });
  const zoomEquivalent = await zoomContext.newPage();
  await zoomEquivalent.goto(baseUrl, { waitUntil: "networkidle" });
  await checkNoHorizontalOverflow(zoomEquivalent, "200% zoom equivalent");

  for (const path of ["/intake", "/samples/bywater-grounds-sample-plan.pdf", "/samples/bywater-grounds-sample-plan.docx"]) {
    const response = await desktop.request.get(`${baseUrl}${path}`);
    assert(response.ok(), `${path} returned HTTP ${response.status()}.`);
  }

  console.log(JSON.stringify({
    axeViolations: axeResults.violations.length,
    checkedViewports: ["1440x1000", "390x844", "640x900 (200% zoom equivalent)"],
    analyticsEvents: ["cta_click", "account_start", "sample_download"],
    artifactsChecked: 3,
  }, null, 2));
} finally {
  await browser.close();
}
