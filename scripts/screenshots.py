"""Take the README screenshots automatically, in a phone-sized headless browser.

Usage (with the API and the web dev server running, and demo data seeded):
    .venv/Scripts/pip install playwright
    .venv/Scripts/python -m scripts.screenshots

Uses an installed Edge (or Chrome with BROWSER_CHANNEL=chrome), so no browser download is needed.
Logs in by minting a token for the demo user directly - no password involved.
"""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright
from sqlalchemy import select

from fitflow.db.models import User
from fitflow.db.session import SessionLocal
from fitflow.services.auth import create_token
from scripts.seed_demo import DEMO_EMAIL

APP_URL = os.getenv("APP_URL", "http://localhost:5173")
OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
PAGES = [("today", "/"), ("meal", "/meal"), ("workouts", "/workouts"), ("progress", "/progress"),
         ("profile", "/profile")]
# Sent to the AI coach for the chat screenshot: household units ("a large portion") resolved via the national database.
CHAT_MESSAGE = "אכלתי מנה גדולה של שקשוקה ו-2 פרוסות לחם מלא"


def main() -> None:
    with SessionLocal() as db:
        user_id = db.scalar(select(User.id).where(User.email == DEMO_EMAIL))
    if user_id is None:
        raise SystemExit("No demo user - run: python -m scripts.seed_demo")
    token = create_token(user_id)
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel=os.getenv("BROWSER_CHANNEL", "msedge"))

        def phone(color_scheme: str = "light", logged_in: bool = True):
            # reduced_motion: skip entrance animations so every screenshot shows the final state.
            context = browser.new_context(
                viewport={"width": 390, "height": 844}, device_scale_factor=2,
                color_scheme=color_scheme, reduced_motion="reduce", locale="he-IL",
            )
            if logged_in:
                context.add_init_script(f"localStorage.setItem('fitflow.token', {json.dumps(token)})")
            return context.new_page()

        def shoot(page, path: str, name: str) -> None:
            page.goto(APP_URL + path)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1800)  # let charts finish drawing
            page.screenshot(path=OUT / f"{name}.png")
            print("saved", name)

        page = phone()
        for name, path in PAGES:
            shoot(page, path, name)
        shoot(phone("dark"), "/", "today-dark")

        # Onboarding, step 2 (goal + target weight with the estimated date)
        page = phone(logged_in=False)
        page.goto(APP_URL)
        page.get_by_placeholder("השם שלך").fill("עופרי")
        page.get_by_role("button", name="המשך").click()
        page.wait_for_timeout(1200)  # the date preview is debounced
        page.screenshot(path=OUT / "onboarding.png")
        print("saved onboarding")

        # The AI coach (needs an LLM key in .env): send a message and wait for the confirmation card.
        page = phone()
        page.goto(APP_URL + "/log")
        page.get_by_placeholder("מה אכלת או עשית היום?").fill(CHAT_MESSAGE)
        try:
            with page.expect_response(lambda r: r.url.endswith("/chat"), timeout=120_000):
                page.get_by_role("button", name="שליחה").click()
            page.reload()  # show the conversation as a returning user sees it
            page.get_by_text("ממתינים לאישור").wait_for(timeout=10_000)
            page.wait_for_timeout(800)
            page.screenshot(path=OUT / "chat.png")
            print("saved chat")
        except Exception:
            print("chat: no answer from the AI (no key or quota?) - kept the old chat.png")

        browser.close()


if __name__ == "__main__":
    main()
