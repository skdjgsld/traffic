# run_fixed_visitor.py
"""
Basit, izinli test amaçlı: tüm gezintiler SABİT START_URL'e gider.
KULLANIM (varsayılan): python run_fixed_visitor.py
Opsiyonel: python run_fixed_visitor.py --repeats 5 --headless

UYARI: Bu scripti SADECE SİZİN SAHİP OLDUĞUNUZ veya İZİN VERİLEN hedeflerde kullanın.
"""

import time
import random
import logging
import argparse
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ------- AYARLAR (değiştirmeye gerek yok) -------
START_URL = "https://share.google/TMi8EqcYT6JBBEEeX"  # sabit hedef link
DEFAULT_REPEATS = 10
DEFAULT_MAX_PAGES = 6   # oturum başına yapılacak "etkileşim sayısı" - mantıksal limit

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
]

VIEWPORTS = [(1280,800), (1366,768), (1440,900), (1536,864), (1024,1366)]
LOCALES = ["tr-TR", "tr", "en-US"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ------- HELPER FONKSİYONLAR -------
def ease_in_out(t):
    import math
    return 0.5 - 0.5 * math.cos(math.pi * t)

def human_move(mouse, start, end, steps=50, pause=(0.003, 0.012)):
    sx, sy = start; ex, ey = end
    for i in range(1, steps+1):
        t = i/steps
        e = ease_in_out(t)
        x = sx + (ex - sx) * e + random.uniform(-2.0, 2.0)
        y = sy + (ey - sy) * e + random.uniform(-2.0, 2.0)
        try:
            mouse.move(x, y)
        except Exception:
            pass
        time.sleep(random.uniform(*pause))

def human_scroll(page, total=600):
    scrolled = 0
    while scrolled < total:
        step = random.randint(60, 220)
        try:
            page.mouse.wheel(0, step)
        except Exception:
            try:
                page.evaluate(f"window.scrollBy(0, {step});")
            except Exception:
                pass
        scrolled += step
        time.sleep(random.uniform(0.12, 0.4))

def close_cookie_banners(page):
    # Basit denemeler: yaygın buton ve metinleri tıklamaya çalış
    possible_selectors = [
        "button[id*='cookie']", "button[class*='cookie']", "button[aria-label*='cookie']",
        "button:has-text('Kabul')", "button:has-text('KABUL')", "button:has-text('Accept')",
        "button:has-text('Tamam')", "button:has-text('Anladım')"
    ]
    for sel in possible_selectors:
        try:
            el = page.query_selector(sel)
            if el:
                try:
                    el.click(timeout=1500)
                    logging.info("Cookie banner kapatıldı (selector): %s", sel)
                    return True
                except Exception:
                    pass
        except Exception:
            pass
    # metin bazlı fallback
    texts = ["kabul", "tamam", "anladım", "accept", "agree"]
    for t in texts:
        try:
            el = page.query_selector(f"text={t}")
            if el:
                try:
                    el.click(timeout=1500)
                    logging.info("Cookie banner kapatıldı (text): %s", t)
                    return True
                except Exception:
                    pass
        except Exception:
            pass
    return False

def random_interactions_on_page(page, iterations=4):
    # rastgele scroll, hover, click (ancak NAVIGATE yerine her zaman START_URL'e dönecek)
    try:
        human_scroll(page, total=random.randint(200, 1000))
    except Exception:
        pass

    # rastgele hover ve "soft click" (eğer klik navigasyon yaparsa, hemen START_URL'e geri dön)
    clickable_selectors = ["button", "a", "input[type=submit]", "input[type=button]"]
    all_candidates = []
    for sel in clickable_selectors:
        try:
            nodes = page.query_selector_all(sel)
            if nodes:
                all_candidates.extend(nodes)
        except Exception:
            pass

    random.shuffle(all_candidates)
    attempts = min(len(all_candidates), iterations)
    for i in range(attempts):
        el = all_candidates[i]
        try:
            box = el.bounding_box()
            if not box:
                continue
            cx = box["x"] + box["width"]/2
            cy = box["y"] + box["height"]/2
            human_move(page.mouse, (random.randint(80,300), random.randint(80,300)), (cx, cy), steps=random.randint(30,90))
            # soft click via evaluate to reduce unexpected navigation behavior
            try:
                page.evaluate("(el)=>{ el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true})); el.dispatchEvent(new MouseEvent('mouseup',{bubbles:true})); }", el)
                # if element has click handler, try click()
                try:
                    el.click(timeout=800)
                except Exception:
                    pass
            except Exception:
                try:
                    el.click(timeout=800)
                except Exception:
                    pass
            # küçük bekleme
            time.sleep(random.uniform(0.6, 1.8))
            # ensure we are on START_URL (the user requested all links go to that fixed link)
            if page.url != START_URL:
                try:
                    page.goto(START_URL, wait_until="domcontentloaded", timeout=20000)
                except Exception:
                    pass
                time.sleep(random.uniform(0.5, 1.2))
        except Exception:
            continue

# ------- OTURUM (tek ziyaret döngüsü) -------
def run_session(playwright, headless=False, max_pages=DEFAULT_MAX_PAGES):
    browser = playwright.firefox.launch(headless=headless)
    ua = random.choice(USER_AGENTS)
    vp = random.choice(VIEWPORTS)
    locale = random.choice(LOCALES)
    context = browser.new_context(viewport={"width": vp[0], "height": vp[1]}, user_agent=ua, locale=locale)
    page = context.new_page()

    try:
        logging.info("Navigating to START_URL: %s", START_URL)
        try:
            page.goto(START_URL, wait_until="domcontentloaded", timeout=30000)
        except PWTimeout:
            logging.warning("Timeout loading START_URL; continuing.")
        time.sleep(random.uniform(0.7, 2.0))

        # cookie banner varsa kapatmaya çalış
        try:
            close_cookie_banners(page)
        except Exception:
            pass

        # birkaç kez site içi etkileşim (her seferinde START_URL korunur)
        interactions = random.randint(2, max_pages)
        for _ in range(interactions):
            random_interactions_on_page(page, iterations=random.randint(1,4))
            # ufak bekleme
            time.sleep(random.uniform(0.8, 2.2))

        logging.info("Session finished (ensuring we end at START_URL).")
        if page.url != START_URL:
            try:
                page.goto(START_URL, wait_until="domcontentloaded", timeout=20000)
            except Exception:
                pass
        # save final small info
        logging.info("Final page url: %s", page.url)

    except Exception as e:
        logging.warning("Session error: %s", e)

    finally:
        try:
            context.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass

# ------- ENTRY POINT -------
def main():
    parser = argparse.ArgumentParser(description="Run fixed-visitor sessions to START_URL.")
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS, help="How many sessions to run (default 10)")
    parser.add_argument("--headless", action="store_true", help="Run headless")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES, help="Max interactions per session")
    args = parser.parse_args()

    logging.info("Starting fixed visitor. START_URL=%s repeats=%d headless=%s", START_URL, args.repeats, args.headless)
    with sync_playwright() as p:
        for i in range(args.repeats):
            logging.info("=== Session %d/%d ===", i+1, args.repeats)
            run_session(p, headless=args.headless, max_pages=args.max_pages)
            # nazik bekleme
            time.sleep(random.uniform(3, 12))
    logging.info("All sessions done.")

if __name__ == "__main__":
    main()
