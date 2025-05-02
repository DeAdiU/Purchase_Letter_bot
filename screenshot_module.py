# screenshot_module.py
import os
import time
import base64
from io import BytesIO
# from selenium import webdriver # Keep selenium for exceptions if needed
from selenium.common.exceptions import WebDriverException, TimeoutException
# Import undetected_chromedriver
import undetected_chromedriver as uc

# --- Configuration --- (Keep your existing config)
SCREENSHOT_WIDTH = 1024
SCREENSHOT_HEIGHT = 768
PAGE_LOAD_WAIT_SECONDS = 7 # Increase wait time slightly, might help sometimes
# CHROMEDRIVER_PATH = None # undetected-chromedriver usually manages this

def setup_driver():
    """Sets up the Selenium WebDriver using undetected-chromedriver."""
    print("INFO (Screenshot): Setting up WebDriver using undetected-chromedriver...")
    options = uc.ChromeOptions()
    # Common options (some might be handled by uc automatically, but can be kept)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--window-size={SCREENSHOT_WIDTH},{SCREENSHOT_HEIGHT}")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--log-level=3")
    # options.add_argument('--headless') # TRY WITHOUT HEADLESS FIRST! It significantly increases success rate.
                                        # If you absolutely need headless, add it back later, but expect lower success.

    # Add a realistic User-Agent (optional, uc might do this, but can't hurt)
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36') # Example UA

    driver = None
    try:
        print("INFO (Screenshot): Initializing undetected_chromedriver...")
        # --- Use undetected_chromedriver ---
        # It often manages the driver download/path automatically.
        # You can specify version_main if needed, e.g., version_main=108
        driver = uc.Chrome(options=options, use_subprocess=True)
        # ------------------------------------

        print("INFO (Screenshot): WebDriver setup successful.")
        driver.set_page_load_timeout(45) # Increase page load timeout
        return driver
    except WebDriverException as e:
        print(f"ERROR (Screenshot): Failed to initialize WebDriver: {e}")
        if "cannot find chrome binary" in str(e).lower():
             print("  >> Ensure Google Chrome or Chromium browser is installed.")
        elif "timed out" in str(e).lower():
             print("  >> WebDriver timed out during initialization. Check network or ChromeDriver compatibility.")
        else:
             print("  >> Check ChromeDriver version compatibility with your installed Chrome browser if not using automatic management.")
        # Close driver if partially initialized
        if driver:
            driver.quit()
        return None
    except Exception as e:
        print(f"ERROR (Screenshot): An unexpected error occurred during WebDriver setup: {e}")
        if driver:
            driver.quit()
        return None

# --- take_screenshots function remains the same ---
# (Make sure it uses the driver returned by the modified setup_driver)
def take_screenshots(items_list):
    """
    Takes screenshots for items with valid URLs.
    (Function body is unchanged, relies on the driver from setup_driver)
    """
    print(f"\nINFO (Screenshot): Starting screenshot process for {len(items_list)} items...")
    driver = setup_driver() # Calls the modified setup function
    if not driver:
        print("ERROR (Screenshot): WebDriver not available. Skipping screenshot generation.")
        return items_list

    screenshots_taken = 0
    items_with_screenshots = []

    try:
        for i, item in enumerate(items_list):
            url = item.get('link')
            item_name = item.get('component', f'Item {item.get("id", i+1)}')

            if not url or not url.startswith(('http://', 'https://')):
                print(f"DEBUG (Screenshot): Skipping item '{item_name}' - No valid URL provided.")
                item['screenshot_base64'] = None
                items_with_screenshots.append(item)
                continue

            print(f"INFO (Screenshot): [{i+1}/{len(items_list)}] Processing '{item_name}' - URL: {url[:80]}...")

            try:
                driver.get(url)
                print(f"  DEBUG (Screenshot): Waiting {PAGE_LOAD_WAIT_SECONDS}s for page load/challenges...")
                time.sleep(PAGE_LOAD_WAIT_SECONDS) # Keep a wait here for dynamic content/checks

                # Add an extra check for Cloudflare indicators after the wait
                page_title = driver.title.lower()
                page_source = driver.page_source.lower()
                if "just a moment" in page_title or "checking your browser" in page_title or "verify you are human" in page_source or "cloudflare" in page_source:
                    print(f"  WARNING (Screenshot): Cloudflare challenge likely still present for '{item_name}'. Screenshot might be of the challenge page.")
                    # Optionally wait longer here? Might not help.
                    # time.sleep(10) # Example extra wait

                png_bytes = driver.get_screenshot_as_png()
                if not png_bytes:
                     print(f"  WARNING (Screenshot): Screenshot bytes are empty for '{item_name}'. Skipping.")
                     item['screenshot_base64'] = None
                     items_with_screenshots.append(item)
                     continue

                base64_str = base64.b64encode(png_bytes).decode('utf-8')
                item['screenshot_base64'] = f"data:image/png;base64,{base64_str}"
                print(f"  SUCCESS (Screenshot): Screenshot captured for '{item_name}' (Base64 length: {len(item['screenshot_base64'])}).")
                screenshots_taken += 1

            except TimeoutException:
                print(f"  ERROR (Screenshot): Page load timed out for '{item_name}' ({url}). Skipping screenshot.")
                item['screenshot_base64'] = None
            except WebDriverException as e:
                print(f"  ERROR (Screenshot): WebDriver error for '{item_name}' ({url}): {e}. Skipping screenshot.")
                item['screenshot_base64'] = None
            except Exception as e:
                print(f"  ERROR (Screenshot): Unexpected error taking screenshot for '{item_name}' ({url}): {e}. Skipping screenshot.")
                item['screenshot_base64'] = None

            items_with_screenshots.append(item)

    finally:
        if driver:
            print("INFO (Screenshot): Shutting down WebDriver...")
            driver.quit()

    print(f"INFO (Screenshot): Screenshot process finished. Captured {screenshots_taken} screenshots.")
    return items_with_screenshots