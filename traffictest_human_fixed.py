# traffictest_human_fixed.py
"""
Güncellenmiş: sabit start URL, screenshot kapalı, tekrar sayısı (repeats).
UYARI: Yalnızca sahip olduğunuz veya izin verilen sitelerde kullanın.
"""

import os
import sys
import time
import json
import random
import logging
import argparse
import traceback
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException

# -------- CONFIG FIXED --------
START_URL = "https://share.google/TMi8EqcYT6JBBEEeX"  # sabit URL
REPEATS = 10  # default tekrar sayısı

# -------- CONFIG DEFAULTS --------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
]

DEFAULT_WAIT_MIN = 1.2
DEFAULT_WAIT_MAX = 4.0
DEFAULT_VISIT_LIMIT = 30
SCREENSHOT_DIR = "screenshots"
COOKIES_FILE = "cookies.json"
LOG_FILE = "traffictest_human_fixed.log"

# Turn screenshotting off as requested
SAVE_SCREENSHOTS = False

# -------- LOGGING --------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)

# -------- HELPERS --------
def human_sleep(min_s=DEFAULT_WAIT_MIN, max_s=DEFAULT_WAIT_MAX, jitter=0.5):
    s = random.uniform(min_s, max_s) + random.uniform(0, jitter)
    logging.info(f"Sleeping {s:.2f}s (human-like)")
    time.sleep(s)

def rand_user_agent():
    return random.choice(USER_AGENTS)

def save_screenshot(driver, tag=""):
    if not SAVE_SCREENSHOTS:
        return
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR)
    fn = os.path.join(SCREENSHOT_DIR, f"{int(time.time())}_{tag}.png")
    try:
        driver.save_screenshot(fn)
        logging.info(f"Saved screenshot: {fn}")
    except Exception as e:
        logging.warning(f"Screenshot failed: {e}")

def load_cookies(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return None
    return None

def save_cookies(driver, path):
    try:
        cookies = driver.get_cookies()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cookies, f)
        logging.info(f"Cookies saved to {path}")
    except Exception as e:
        logging.warning(f"Could not save cookies: {e}")

def clean_href(href):
    if not href:
        return None
    href = href.split("#")[0].rstrip("/")
    if href.lower().startswith("javascript:") or href.lower().startswith("mailto:") or href.lower().startswith("tel:"):
        return None
    return href

def human_move_and_hover(driver, element, steps=8):
    try:
        actions = ActionChains(driver)
        box = element.rect
        if not box or box.get("width",0) == 0:
            actions.move_to_element(element).perform()
            return
        cx = box["x"] + box["width"]/2
        cy = box["y"] + box["height"]/2
        current_x = random.randint(100, 400)
        current_y = random.randint(100, 400)
        for i in range(steps):
            t = (i+1)/steps
            x = int(current_x + (cx - current_x) * t + random.uniform(-5,5))
            y = int(current_y + (cy - current_y) * t + random.uniform(-5,5))
            try:
                actions.move_by_offset(xoffset=x - current_x, yoffset=y - current_y).perform()
            except Exception:
                try:
                    actions.move_to_element_with_offset(element, 1, 1).perform()
                except Exception:
                    pass
            current_x, current_y = x, y
            time.sleep(random.uniform(0.02, 0.06))
        try:
            actions.move_to_element(element).perform()
        except Exception:
            pass
    except Exception as e:
        logging.debug(f"human_move_and_hover exception: {e}")

def human_scroll(driver, total_pixels=600, step_min=80, step_max=220):
    scrolled = 0
    while scrolled < total_pixels:
        step = random.randint(step_min, step_max)
        driver.execute_script(f"window.scrollBy(0, {step});")
        scrolled += step
        time.sleep(random.uniform(0.15, 0.6))

def find_internal_links(driver, base_url):
    anchors = driver.find_elements(By.TAG_NAME, "a")
    hrefs = []
    for a in anchors:
        try:
            href = a.get_attribute("href")
            href = clean_href(href)
            if href and base_url in href:
                hrefs.append(href)
        except Exception:
            continue
    unique = list(dict.fromkeys(hrefs))
    return unique

# -------- DRIVER SETUP --------
def make_driver(headless=False, user_agent=None, firefox_binary_path=None):
    options = Options()
    options.headless = headless
    if firefox_binary_path:
        options.binary_location = firefox_binary_path
    if user_agent:
        options.set_preference("general.useragent.override", user_agent)
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference("useAutomationExtension", False)
    options.set_preference("media.peerconnection.enabled", False)
    service = Service(executable_path=GeckoDriverManager().install())
    driver = webdriver.Firefox(service=service, options=options)
    driver.set_page_load_timeout(40)
    return driver

# -------- SINGLE RUN (one cycle through site) --------
def single_run(click_selector=None, headless=False, visit_limit=DEFAULT_VISIT_LIMIT, cookies_enabled=True):
    ua = rand_user_agent()
    logging.info(f"single_run: UA={ua} headless={headless} visit_limit={visit_limit}")
    driver = None
    try:
        driver = make_driver(headless=headless, user_agent=ua)
        base_origin = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(START_URL))

        # load cookies if exist
        if cookies_enabled:
            cookies = load_cookies(COOKIES_FILE)
            if cookies:
                try:
                    driver.get(base_origin)
                    for ck in cookies:
                        ck_clean = {k:v for k,v in ck.items() if k in ("name","value","path","domain","secure","expiry","httpOnly")}
                        try:
                            driver.add_cookie(ck_clean)
                        except Exception:
                            pass
                    logging.info("Loaded cookies into browser (if compatible).")
                except Exception:
                    logging.debug("Could not load cookies before navigation.")

        # Visit start page
        try:
            logging.info(f"GET {START_URL}")
            driver.get(START_URL)
            human_sleep(1.0, 2.5)
            # screenshots disabled by config
            save_screenshot(driver, "start_page")
        except Exception as e:
            logging.error(f"Cannot open start_url: {e}")
            save_screenshot(driver, "start_error")
            return

        # small interactions
        try:
            human_scroll(driver, total_pixels=random.randint(200,900))
            human_sleep(0.5,1.8)
        except Exception:
            pass

        # BFS-like limited crawl
        visited = set()
        to_visit = [START_URL]
        while to_visit and len(visited) < visit_limit:
            cur = to_visit.pop(0)
            if cur in visited:
                continue
            try:
                logging.info(f"Visiting {cur} ({len(visited)+1}/{visit_limit})")
                driver.get(cur)
                human_sleep(1.2, 3.5)
                save_screenshot(driver, "page")
                human_scroll(driver, total_pixels=random.randint(200,800))
                human_sleep(0.6, 1.6)

                links = find_internal_links(driver, base_origin)
                if links and random.random() < 0.4:
                    target_url = random.choice(links)
                    logging.info(f"Following random internal link to {target_url}")
                    try:
                        elem = driver.find_element(By.XPATH, f"//a[@href='{target_url}']")
                        human_move_and_hover(driver, elem, steps=random.randint(6,15))
                        human_sleep(0.2,0.6)
                        elem.click()
                        human_sleep(1.0, 2.4)
                        if random.random() < 0.6:
                            driver.back()
                            human_sleep(0.5, 1.6)
                    except Exception:
                        if target_url not in visited and target_url not in to_visit:
                            to_visit.append(target_url)

                visited.add(cur)
                new_links = find_internal_links(driver, base_origin)
                for l in new_links:
                    if l not in visited and l not in to_visit and len(to_visit) < visit_limit:
                        to_visit.append(l)
            except WebDriverException as e:
                logging.warning(f"WebDriverException on {cur}: {e}")
                save_screenshot(driver, "webdriver_exc")
                time.sleep(1 + random.random()*2)
            except Exception:
                logging.error("Unhandled exception: " + traceback.format_exc())
                save_screenshot(driver, "unhandled_exc")

        # final click if provided
        if click_selector:
            try:
                logging.info(f"Attempting final click selector: {click_selector}")
                if click_selector.startswith("text="):
                    text = click_selector.split("=",1)[1]
                    el = driver.find_element(By.XPATH, f"//*[contains(normalize-space(), '{text}')]")
                elif click_selector.startswith("css="):
                    sel = click_selector.split("=",1)[1]
                    el = driver.find_element(By.CSS_SELECTOR, sel)
                else:
                    el = driver.find_element(By.CSS_SELECTOR, click_selector)

                human_move_and_hover(driver, el, steps=random.randint(8,18))
                human_sleep(0.2, 0.6)
                el.click()
                human_sleep(1.5, 3.0)
                save_screenshot(driver, "final_click")
            except Exception as e:
                logging.warning(f"Final click failed: {e}")
                save_screenshot(driver, "final_click_failed")

        if cookies_enabled:
            try:
                save_cookies(driver, COOKIES_FILE)
            except Exception:
                pass

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        logging.info("single_run finished.")

# -------- ENTRY & REPEATS --------
def parse_args():
    p = argparse.ArgumentParser(description="Human-like Selenium test (fixed start URL). Use only on sites you own/have permission.")
    p.add_argument("--click-selector", "-c", help='Selector to click at the end. Use forms: "text=Giriş" or "css=a.btn"')
    p.add_argument("--headless", action="store_true", help="Run browser headless")
    p.add_argument("--limit", type=int, default=DEFAULT_VISIT_LIMIT, help="Max pages to visit per run")
    p.add_argument("--no-cookies", action="store_true", help="Do not load/save cookies")
    p.add_argument("--repeats", type=int, default=REPEATS, help="How many times to repeat the single_run cycle")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    repeats = max(1, args.repeats)
    logging.info(f"Starting full run: START_URL={START_URL} repeats={repeats}")
    for i in range(repeats):
        logging.info(f"=== Run {i+1}/{repeats} ===")
        single_run(click_selector=args.click_selector, headless=args.headless, visit_limit=args.limit, cookies_enabled=not args.no_cookies)
        # polite wait between repeats
        time.sleep(random.uniform(3, 10))
    logging.info("All repeats finished.")
