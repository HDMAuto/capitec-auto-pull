"""Playwright automation for the Capitec merchant portal.

One job: given a branch's credentials, drive the browser to export a single
day's transactions as CSV and return the downloaded file path. Knows nothing
about config format or the folder contract.

All selectors below were verified against the live site.
"""
from __future__ import annotations
from pathlib import Path
from contextlib import contextmanager
from playwright.sync_api import sync_playwright, Page

LOGIN_URL = "https://merchant.capitecbank.co.za/app/login"
DEFAULT_TIMEOUT_MS = 30_000
DOWNLOAD_TIMEOUT_MS = 60_000

# --- login ---
SEL_USERNAME = "input[name='username']"
SEL_PASSWORD = "input[name='password']"
SEL_LOGIN_BTN = "button[type='submit']"


@contextmanager
def browser_page(headless: bool = False):
    """Yield a fresh Playwright page with downloads enabled, then clean up."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)
        try:
            yield page
        finally:
            context.close()
            browser.close()


def login(page: Page, username: str, password: str) -> None:
    """Log into the merchant portal. Raises on timeout if auth doesn't complete."""
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    page.fill(SEL_USERNAME, username)
    page.fill(SEL_PASSWORD, password)
    page.click(SEL_LOGIN_BTN)
    page.wait_for_url(lambda url: "/login" not in url, timeout=DEFAULT_TIMEOUT_MS)
    page.wait_for_load_state("networkidle")


def _set_single_day(page: Page, dd: str, mm: str, yyyy: str) -> None:
    """Open the Custom-date range picker and set start = end = the given day."""
    page.get_by_text("Today", exact=True).first.click()        # open range menu
    page.get_by_text("Custom date", exact=True).first.click()
    page.get_by_placeholder("DD").nth(0).fill(dd)              # start date
    page.get_by_placeholder("MM").nth(0).fill(mm)
    page.get_by_placeholder("YYYY").nth(0).fill(yyyy)
    page.get_by_placeholder("DD").nth(1).fill(dd)              # end date
    page.get_by_placeholder("MM").nth(1).fill(mm)
    page.get_by_placeholder("YYYY").nth(1).fill(yyyy)
    page.get_by_role("button", name="Save selected date range").click()
    page.wait_for_load_state("networkidle")


def export_csv_for_date(page: Page, download_dir: Path, report_date: str) -> Path:
    """Assumes already logged in. Filter Transactions to report_date (one day),
    export as CSV, and save the download into download_dir.

    report_date is 'YYYY-MM-DD'. Returns the saved file path.
    """
    yyyy, mm, dd = report_date.split("-")

    page.get_by_text("Transactions", exact=True).first.click()
    page.wait_for_load_state("networkidle")

    _set_single_day(page, dd, mm, yyyy)
    page.wait_for_timeout(1000)

    page.get_by_role("button", name="Export transactions").click()
    page.get_by_text("CSV", exact=True).click()
    with page.expect_download(timeout=DOWNLOAD_TIMEOUT_MS) as dl_info:
        page.get_by_role("button", name="Export", exact=True).click()
    download = dl_info.value

    dest = Path(download_dir) / download.suggested_filename
    download.save_as(dest)
    return dest
