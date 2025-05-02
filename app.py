# app.py
import streamlit as st
import os
import sys
import datetime
from jinja2 import Environment, Template
from weasyprint import HTML, CSS
from collections import defaultdict
import locale
import re
import base64
import traceback
import time
import tempfile # For temporary file handling

# --- FIRST STREAMLIT COMMAND ---
# Moved set_page_config here, right after imports
st.set_page_config(layout="wide")
# --------------------------------

# --- Configuration ---
# Make paths relative to this script file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output') # Still useful for temp files maybe
# Create output dir if it doesn't exist (for local runs)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Letter Configuration (Defaults - Could be Streamlit inputs) ---
DEFAULT_REF_NO = "PICT/ROBOTICS/DATE/##"
DEFAULT_TO_RECIPIENT = """
The Director/Principal,
Pune Institute of Computer Technology,
Pune 411043.
"""
DEFAULT_SUBJECT = "Online purchase of components for PICT ROBOTICS CLUB."
DEFAULT_INTRO_TEXT = "This letter is related to the purchase of components which are to be purchased for the ABU Robocon 2025. Product screenshots are attached for reference where available (if enabled)."
DEFAULT_CLOSING_TEXT = "We request you please direct the accounts department to buy the listed components online."
DEFAULT_THANKING_TEXT = "Thanking you in anticipation,"
DEFAULT_SIGNATORY_LEFT = "Titeer Deshpande\nTeam Captain"
DEFAULT_HEADER_TEXT = """
Society For Computer Technology and Research's<br>
PUNE INSTITUTE OF COMPUTER TECHNOLOGY<br>
Pune - 411 043<br>
<strong style="font-size: 1.1em;">PICT ROBOTICS CLUB</strong><br>
Website: http://pictrobotics.com<br>
Email: robocon@pict.edu
"""
DEFAULT_SIGNATORY_RIGHT = "Dr. S. V. Gaikwad\nTeacher Coordinator"

# --- Header/Footer Info ---
# Use paths relative to the app.py file
HEADER_IMG_LEFT_PATH = os.path.join(BASE_DIR, "pict1.jpg")
HEADER_IMG_RIGHT_PATH = os.path.join(BASE_DIR, "pictrobotics_logo.jpg")

# --- Import Screenshot Module ---
# It's okay for st commands to run now, AFTER set_page_config
SELENIUM_AVAILABLE = False
SCREENSHOT_ERROR_MESSAGE = ""

def take_screenshots_dummy(items_list):
    st.warning("Screenshot module not available or disabled. Skipping screenshots.")
    for item in items_list:
        item['screenshot_base64'] = None
    return items_list

take_screenshots_func = take_screenshots_dummy # Default to dummy

try:
    from screenshot_module import take_screenshots as real_take_screenshots
    # Further check if Chrome/ChromeDriver are likely usable (basic check)
    # This is NOT foolproof, especially in containers
    try:
        # Attempt a quick driver setup to see if it fails immediately
        # Note: This adds overhead but gives better feedback
        st.write("Attempting preliminary WebDriver check...") # Debug feedback - NOW OKAY HERE
        from screenshot_module import setup_driver
        # Important: Make sure setup_driver itself doesn't call st.set_page_config
        # Also ensure it handles potential uc/selenium imports cleanly
        temp_driver = setup_driver()
        if temp_driver:
            temp_driver.quit()
            SELENIUM_AVAILABLE = True
            take_screenshots_func = real_take_screenshots
            st.success("Screenshot module imported and basic WebDriver check passed.") # NOW OKAY HERE
        else:
            # Capture potential error from setup_driver if it returns None without raising exception
            SCREENSHOT_ERROR_MESSAGE = "Screenshot module imported, but WebDriver failed initial setup (Chrome/ChromeDriver missing or incompatible?). Screenshots disabled."
            st.warning(SCREENSHOT_ERROR_MESSAGE) # NOW OKAY HERE
    except Exception as check_e:
        SCREENSHOT_ERROR_MESSAGE = f"Screenshot module imported, but WebDriver check failed: {check_e}. Screenshots disabled."
        st.warning(SCREENSHOT_ERROR_MESSAGE) # NOW OKAY HERE

except ImportError:
    SCREENSHOT_ERROR_MESSAGE = "screenshot_module.py not found or its dependencies (selenium/undetected-chromedriver) missing. Screenshots disabled."
    st.warning(SCREENSHOT_ERROR_MESSAGE) # NOW OKAY HERE
except Exception as e:
    SCREENSHOT_ERROR_MESSAGE = f"Unexpected error importing screenshot_module: {e}. Screenshots disabled."
    st.error(SCREENSHOT_ERROR_MESSAGE) # NOW OKAY HERE
    traceback.print_exc()


# --- Helper Functions (parse_price, image_to_base64 - adapted slightly) ---
def parse_price(price_str):
    if isinstance(price_str, (int, float)): return float(price_str)
    if price_str is None: return 0.0
    cleaned_price = re.sub(r'[₹$,]', '', str(price_str)).strip()
    try:
        return float(cleaned_price)
    except ValueError:
        # st.warning(f"DEBUG (parse_price): Failed to parse price '{price_str}', returning 0.0")
        return 0.0 # Keep it quieter in Streamlit

def image_to_base64(image_path):
    # st.write(f"DEBUG (image_to_base64): Attempting to convert image: {image_path}")
    if not os.path.exists(image_path) or not os.path.isfile(image_path):
        st.error(f"  ERROR (image_to_base64): Image file NOT found or is not a file: {image_path}")
        return None
    try:
        with open(image_path, "rb") as img_file:
            img_bytes = img_file.read()
        if not img_bytes:
            st.error(f"  ERROR (image_to_base64): Image file is empty: {image_path}")
            return None
        mime_type = f"image/{os.path.splitext(image_path)[1][1:].lower()}"
        if mime_type == "image/jpg": mime_type = "image/jpeg"
        base64_str = base64.b64encode(img_bytes).decode('utf-8')
        result = f"data:{mime_type};base64,{base64_str}"
        # st.write(f"  SUCCESS (image_to_base64): Converted image {os.path.basename(image_path)} to Base64.")
        return result
    except Exception as e:
        st.error(f"  ERROR (image_to_base64): Failed to read/encode image {image_path}: {e}")
        traceback.print_exc()
        return None

# --- Agent Functions (Copied from main.py, adjusted print -> st.write/info/warning) ---

def agent_1_parse_input(raw_items_data):
    """Parses TSV-like input: Sr, Item, Cat, Price, Qty, Total, Notes, Vendor Alias, Vendor Platform, Purp, Status, Link"""
    structured_items = []
    lines = raw_items_data.strip().split('\n')
    st.info(f"Agent 1: Parsing {len(lines)} lines from input data...")
    COL_ITEM_NAME = 1
    COL_UNIT_PRICE = 3
    COL_QTY = 4
    COL_VENDOR = 8
    COL_LINK = 11
    min_required_cols = max(COL_ITEM_NAME, COL_UNIT_PRICE, COL_QTY, COL_VENDOR, COL_LINK) + 1
    # st.write(f"DEBUG (Agent 1): Minimum required columns: {min_required_cols}")

    parsed_count = 0
    skipped_count = 0
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith('#') or not line[0].isdigit():
            continue

        parts = line.split('\t')
        if len(parts) < min_required_cols:
            if len(parts) < 5: # Heuristic for space separation
                 parts_space = re.split(r'\s{2,}', line)
                 if len(parts_space) >= min_required_cols:
                     parts = parts_space
                     # st.write(f"DEBUG (Agent 1): Line {i+1} used space split.")
                 else:
                    st.warning(f"Agent 1: Skipping line {i+1} (need {min_required_cols} cols, got {len(parts)}): {line[:80]}...")
                    skipped_count += 1
                    continue
            else:
                 st.warning(f"Agent 1: Skipping line {i+1} (need {min_required_cols} cols, got {len(parts)}): {line[:80]}...")
                 skipped_count += 1
                 continue

        try:
            name = parts[COL_ITEM_NAME].strip()
            qty_str = parts[COL_QTY].strip()
            price_str = parts[COL_UNIT_PRICE].strip()
            vendor = parts[COL_VENDOR].strip() if len(parts) > COL_VENDOR and parts[COL_VENDOR] else "Unknown Vendor"
            link = parts[COL_LINK].strip() if len(parts) > COL_LINK and parts[COL_LINK] else None

            # st.write(f"DEBUG (Agent 1): Line {i+1} Parsed -> Name: '{name}', Vendor: '{vendor}', Link: '{link}'")

            if not name:
                st.warning(f"Agent 1: Skipping line {i+1} due to missing item name: {line[:80]}...")
                skipped_count += 1
                continue

            qty = int(qty_str)
            price = parse_price(price_str)

            if price >= 0:
                 structured_items.append({
                    'id': i + 1,
                    'component': name,
                    'specification': name,
                    'quantity': qty,
                    'cost_per_piece': price,
                    'vendor': vendor,
                    'link': link,
                    'screenshot_base64': None # Initialize here
                 })
                 parsed_count +=1
            else:
                 st.warning(f"Agent 1: Skipping line {i+1} due to invalid price ({price_str}): {line[:80]}...")
                 skipped_count += 1

        except (ValueError, IndexError) as e:
            st.warning(f"Agent 1: Skipping line {i+1} due to parsing error ({type(e).__name__}: {e}): {line[:80]}...")
            skipped_count += 1
        except Exception as e:
            st.warning(f"Agent 1: Skipping line {i+1} due to unexpected error ({type(e).__name__}: {e}): {line[:80]}...")
            traceback.print_exc()
            skipped_count += 1

    st.success(f"Agent 1: Successfully parsed {parsed_count} items.")
    if skipped_count > 0:
        st.warning(f"Agent 1: Skipped {skipped_count} lines due to formatting/parsing issues.")
    return structured_items

def agent_2_group_by_vendor(items):
    """Groups items by vendor."""
    st.info("Agent 2: Grouping items by vendor...")
    grouped = defaultdict(list)
    vendor_map = {}

    for item in items:
        vendor_original = item.get('vendor', 'Unknown Vendor').strip()
        if not vendor_original: vendor_original = "Unknown Vendor"
        vendor_lower = vendor_original.lower()
        vendor_key = vendor_original

        # Vendor Normalization
        if 'robu.in' in vendor_lower: vendor_key = 'Robu.in'
        elif 'roboticsdna' in vendor_lower: vendor_key = 'RoboticsDNA'
        elif 'amazon' in vendor_lower: vendor_key = 'Amazon'
        elif 'rajiv' in vendor_lower: vendor_key = 'Rajiv Electronics'

        # if vendor_original != vendor_key and vendor_original not in vendor_map:
        #     st.write(f"  Normalizing '{vendor_original}' to '{vendor_key}'")
        #     vendor_map[vendor_original] = vendor_key

        grouped[vendor_key].append(item)

    if "Unknown Vendor" in grouped and not grouped["Unknown Vendor"]:
        del grouped["Unknown Vendor"]
    elif "Unknown Vendor" in grouped:
         st.warning(f"Agent 2: {len(grouped['Unknown Vendor'])} items found under 'Unknown Vendor'. Check input data's Vendor Platform column (index 8).")

    st.success(f"Agent 2: Grouped items by {len(grouped)} vendors: {list(grouped.keys())}")
    return dict(grouped)

def agent_4_enrich_data(grouped_items, letter_config, header_img_b64):
    """Calculates totals, adds fees, formats currency, embeds images."""
    st.info("Agent 4: Enriching data, adding fees, formatting...")

    currency_symbol = '₹'
    locale_found = False
    # Simplified locale check for streamlit environment
    try:
        locale.setlocale(locale.LC_ALL, 'en_IN.UTF-8')
        locale.currency(1000, grouping=True, symbol=currency_symbol)
        locale_found = True
        # st.write("DEBUG (Agent 4): Using 'en_IN.UTF-8' locale.")
    except (locale.Error, Exception):
        try:
            locale.setlocale(locale.LC_ALL, '') # Try system default
            locale.currency(1000, grouping=True, symbol=currency_symbol)
            locale_found = True
            # st.write("DEBUG (Agent 4): Using system default locale.")
        except (locale.Error, Exception):
            # st.warning("Agent 4: Locales failed. Using manual Rupee format.")
            locale.setlocale(locale.LC_ALL, 'C') # Fallback to C locale

    def format_currency(value):
        # (Same manual formatting logic as before)
        try:
            numeric_value = float(value)
            if locale_found:
                 # Use locale.format_string - more reliable than locale.currency sometimes
                 try:
                     # Adjust format string as needed
                     formatted = locale.format_string("%.2f", numeric_value, grouping=True)
                     return f"{currency_symbol} {formatted}"
                 except Exception:
                     # Fallback if format_string fails unexpectedly
                     return locale.currency(numeric_value, grouping=True, symbol=currency_symbol)

            else: # Manual formatting
                s = f"{numeric_value:,.2f}"
                parts = s.split('.')
                integer_part = parts[0].replace(',', '')
                decimal_part = parts[1] if len(parts) > 1 else "00"
                decimal_part = decimal_part.ljust(2, '0')[:2]
                if len(integer_part) <= 3: formatted_integer = integer_part
                else:
                    last_three = integer_part[-3:]
                    rest = integer_part[:-3]
                    formatted_rest = ""
                    while len(rest) > 2:
                        formatted_rest = "," + rest[-2:] + formatted_rest
                        rest = rest[:-2]
                    formatted_integer = rest + formatted_rest + "," + last_three
                return f"{currency_symbol} {formatted_integer}.{decimal_part}"
        except (ValueError, TypeError):
            return f"{currency_symbol} {value}" # Fallback

    # --- Image Embedding ---
    header_img_left_b64 = header_img_b64['left']
    header_img_right_b64 = header_img_b64['right']
    # --- End Image Embedding ---

    enriched_data = {
        'vendors': [],
        'all_items_for_screenshots': [],
        'grand_total': 0.0,
        'ref_no': letter_config['ref_no'],
        'letter_date': letter_config['letter_date'],
        'to_recipient': letter_config['to_recipient'].strip().replace('\n', '<br>'),
        'subject': letter_config['subject'],
        'intro_text': letter_config['intro_text'],
        'closing_text': letter_config['closing_text'],
        'thanking_text': letter_config['thanking_text'],
        'signatory_left': letter_config['signatory_left'].strip().replace('\n', '<br>'),
        'signatory_right': letter_config['signatory_right'].strip().replace('\n', '<br>'),
        'header_img_left': header_img_left_b64,
        'header_img_right': header_img_right_b64,
        'header_text': letter_config['header_text'].strip()
    }
    grand_total = 0.0
    all_items_flat = []

    for vendor_key, items in grouped_items.items():
        vendor_item_subtotal = 0.0
        processed_items = []
        special_charges = []

        for item in items:
            cost_per_piece = float(item.get('cost_per_piece', 0.0))
            quantity = int(item.get('quantity', 0))
            line_total = quantity * cost_per_piece

            item['cost_per_piece_f'] = format_currency(cost_per_piece)
            item['cost_total'] = line_total
            item['cost_total_f'] = format_currency(line_total)

            processed_items.append(item)
            all_items_flat.append(item) # Collect all items
            vendor_item_subtotal += line_total

        vendor_subtotal_final = vendor_item_subtotal
        vendor_name_lower = vendor_key.lower()
        fee_applied = False
        fee_amount = 0.0
        fee_description = ""

        # Apply Vendor-Specific Fees
        if 'roboticsdna' in vendor_name_lower:
            fee_percentage = 0.025
            fee_amount = vendor_item_subtotal * fee_percentage
            fee_description = f"Platform Fees ({fee_percentage:.1%})"
            special_charges.append({'description': fee_description, 'amount': fee_amount, 'amount_f': format_currency(fee_amount)})
            vendor_subtotal_final += fee_amount
            fee_applied = True
        elif 'robu.in' in vendor_name_lower:
            delivery_threshold = 2000.00
            if vendor_item_subtotal < delivery_threshold:
                fee_amount = 49.00
                fee_description = f"Delivery Charges (Order < {format_currency(delivery_threshold)})"
            else:
                fee_amount = 0.00
                fee_description = f"Delivery Charges (Order >= {format_currency(delivery_threshold)})"
            special_charges.append({'description': fee_description, 'amount': fee_amount, 'amount_f': format_currency(fee_amount)})
            vendor_subtotal_final += fee_amount
            fee_applied = True
        elif 'amazon' in vendor_name_lower:
            fee_amount = 100.00 # Example fixed fee
            fee_description = "Delivery Charges"
            special_charges.append({'description': fee_description, 'amount': fee_amount, 'amount_f': format_currency(fee_amount)})
            vendor_subtotal_final += fee_amount
            fee_applied = True

        # if fee_applied:
        #    st.write(f"  Applied '{fee_description}' ({format_currency(fee_amount)}) to {vendor_key}")

        enriched_data['vendors'].append({
            'name': vendor_key,
            'items': processed_items,
            'special_charges': special_charges,
            'subtotal': vendor_subtotal_final,
            'subtotal_f': format_currency(vendor_subtotal_final)
        })
        grand_total += vendor_subtotal_final

    enriched_data['grand_total'] = grand_total
    enriched_data['grand_total_f'] = format_currency(grand_total)
    enriched_data['all_items_for_screenshots'] = all_items_flat

    st.success(f"Agent 4: Data enrichment complete. Grand Total: {enriched_data['grand_total_f']}")
    # st.write(f"DEBUG (Agent 4): Total items collected for potential screenshots: {len(all_items_flat)}")
    return enriched_data

def agent_5_generate_content(data, template_string):
    """Populates the template string with data."""
    st.info("Agent 5: Generating HTML content...")
    # Check for screenshots (using the flat list)
    has_any_screenshots = any(item.get('screenshot_base64') for item in data.get('all_items_for_screenshots', []))
    # st.write(f"DEBUG (Agent 5): Any screenshots available for rendering? {has_any_screenshots}")

    env = Environment(trim_blocks=True, lstrip_blocks=True)
    template = env.from_string(template_string)
    try:
        html_content = template.render(data)
        st.success(f"Agent 5: HTML content generated successfully (length: {len(html_content)}).")
        # Debug check (optional, can be noisy)
        # if has_any_screenshots:
        #     found_ss_tag = False
        #     for item in data['all_items_for_screenshots']:
        #          if item.get('screenshot_base64') and item['screenshot_base64'][:30] in html_content:
        #              st.write(f"DEBUG (Agent 5): Found screenshot tag for item '{item.get('component', 'N/A')}' in HTML.")
        #              found_ss_tag = True
        #     if not found_ss_tag:
        #          st.warning("WARNING (Agent 5): Screenshots were expected, but data NOT found in HTML. Check template logic.")
        return html_content
    except Exception as e:
        st.error(f"ERROR in Agent 5 (HTML Generation): {e}")
        traceback.print_exc()
        return None

def agent_6_generate_pdf(html_content):
    """Converts HTML content to PDF bytes."""
    st.info("Agent 6: Generating PDF...")
    pdf_bytes = None
    try:
        # --- IMPORTANT: Make sure your full CSS is included here ---
        css_string = '''
            @page {
                size: A4; margin: 1.8cm 1.5cm 2cm 1.5cm; /* T R B L */
                @bottom-right { content: "Page " counter(page) " of " counter(pages); font-size: 10pt; color: #555; font-family: "Times New Roman", Times, serif; padding-top: 5mm; }
            }
            body { font-family: "Times New Roman", Times, serif; font-size: 11pt; line-height: 1.4; }
            table { border-collapse: collapse; width: 100%; margin-bottom: 15px; border: 1px solid #666; }
            th, td { border: 1px solid #ccc; padding: 5px 8px; vertical-align: top; text-align: left; font-size: 10.5pt; word-wrap: break-word; } /* Added word-wrap */
            th { background-color: #e8e8e8; text-align: center; font-weight: bold; }
            .vendor-section { margin-top: 20px; page-break-inside: avoid; }
            .vendor-title { font-size: 1.1em; font-weight: bold; margin-bottom: 8px; padding-left: 5px; }
            .subtotal-row td, .grand-total-row td { font-weight: bold; background-color: #f5f5f5; }
            .right-align { text-align: right; } .center-align { text-align: center; }
            .header-table { width: 100%; border: none; margin-bottom: 15px; table-layout: fixed; }
            .header-table td { border: none; vertical-align: middle; text-align: center; padding: 0; }
            .header-logo-left { width: 150px; text-align: left; }
            .header-logo-right { width: 150px; text-align: right;}
            .header-text-cell { padding: 0 10px; }
            .header-table img { max-height: 65px; width: auto; display: block; border: none; vertical-align: middle; }
            .header-text { font-family: "Times New Roman", Times, serif; font-size: 10pt; line-height: 1.3; }
            hr { border: 0; border-top: 1px solid #888; margin: 15px 0; }
            .signature-block { margin-top: 35px; overflow: auto; /* Clearfix */ }
            .signature-left { float: left; width: 48%; text-align: left; line-height: 1.4; }
            .signature-right { float: right; width: 48%; text-align: right; line-height: 1.4; }
            .address { line-height: 1.4; margin-bottom: 15px; }
            .subject { margin-top: 20px; margin-bottom: 10px; font-weight: bold; }
            .intro, .closing, .thanking { margin-bottom: 12px; }
            .thanking { margin-top: 20px; }

            /* --- Screenshot Styles --- */
            .screenshot-section { page-break-before: always; margin-top: 1cm; }
            .screenshot-title { font-size: 14pt; font-weight: bold; text-align: center; margin-bottom: 15px; }
            .screenshot-item { page-break-inside: avoid; margin-bottom: 20px; text-align: center; border-top: 1px dashed #ccc; padding-top: 15px; }
            .screenshot-item-name { font-size: 10pt; font-weight: bold; margin-bottom: 8px; }
            .screenshot-item img {
                max-width: 95%; /* Use most of the page width */
                max-height: 20cm; /* Limit height to prevent excessive stretching */
                height: auto;     /* Maintain aspect ratio */
                border: 1px solid #aaa;
                margin: 0 auto;   /* Center the image block */
                display: block;
            }
            /* --- End Screenshot Styles --- */
            '''
        css = CSS(string=css_string)
        # Use BASE_DIR which is the script's directory, important for finding images referenced relatively if any
        # Although we use base64, setting base_url is good practice
        html = HTML(string=html_content, base_url=BASE_DIR)

        # Generate PDF in memory
        pdf_bytes = html.write_pdf(stylesheets=[css])
        st.success("Agent 6: PDF successfully generated in memory.")
        return pdf_bytes
    except Exception as e:
        st.error(f"ERROR in Agent 6 (PDF Generation): {e}")
        if "Pango" in str(e) or "font" in str(e).lower():
            st.error("Font Issue Detected: Ensure required fonts (e.g., Times New Roman via packages.txt or system install) are available.")
        if "failed to load image" in str(e).lower():
             st.error("WeasyPrint Image Loading Error: Check Base64 encoding for header images or screenshots.")
        traceback.print_exc()
        return None

# --- HTML Template Definition (Using corrected screenshot check) ---
purchase_letter_template_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Purchase Letter {{ ref_no }}</title>
    <!-- Styles are primarily applied via the CSS object in Agent 6 -->
</head>
<body>
    <!-- Header -->
    <table class="header-table">
     <tr>
            <td class="header-logo-left">{% if header_img_left %}<img src="{{ header_img_left }}" alt="Left Logo">{% else %}<!-- Left logo missing -->{% endif %}</td>
            <td class="header-text-cell"><div class="header-text">{{ header_text | safe }}</div></td>
            <td class="header-logo-right">{% if header_img_right %}<img src="{{ header_img_right }}" alt="Right Logo">{% else %}<!-- Right logo missing -->{% endif %}</td>
      </tr>
    </table><hr>
    <!-- Metadata -->
    <div style="overflow: auto; margin-bottom: 15px;"><div style="float: left;">Ref. No.: {{ ref_no }}</div><div style="float: right;">Date: {{ letter_date }}</div></div><br style="clear: both;">
    <!-- Recipient Address --><div class="address">To,<br>{{ to_recipient | safe }}</div>
    <!-- Subject --><div class="subject"><u>Subject: {{ subject }}</u></div>
    <!-- Body --><div class="intro">Respected Sir,</div><div class="intro">{{ intro_text }}</div><div class="intro">Following are the requirements which are needed to be purchased online.</div>

    <!-- Item Tables per Vendor -->
    {% for vendor in vendors %}
    <div class="vendor-section">
        <div class="vendor-title">{{ vendor.name }}</div>
        <table>
            <thead><tr><th>Sr. No.</th><th>Component / Specification</th><th class="center-align">Quantity</th><th class="right-align">Cost per piece</th><th class="right-align">Total Cost</th></tr></thead>
            <tbody>
                {# Regular Items #}
                {% for item in vendor['items'] %}
                <tr>
                    <td class="center-align">{{ loop.index }}</td> {# Use vendor loop index for Sr No within vendor table #}
                    <td>{{ item.component }}</td>
                    <td class="center-align">{{ item.quantity }}</td>
                    <td class="right-align">{{ item.cost_per_piece_f }}</td>
                    <td class="right-align">{{ item.cost_total_f }}</td>
                </tr>
                {% else %}{% if not vendor['special_charges'] %}<tr><td colspan="5" class="center-align">No items listed for this vendor.</td></tr>{% endif %}{% endfor %}

                {# Special Charges - Displayed after regular items #}
                {% for charge in vendor['special_charges'] %}
                <tr>
                    <td colspan="4" style="padding-left: 20px; font-style: italic;">{{ charge.description }}</td>
                    <td class="right-align">{{ charge.amount_f }}</td>
                </tr>
                {% endfor %}

                {# Subtotal Row - Always show if there are items or charges #}
                {% if vendor['items'] or vendor['special_charges'] %}
                <tr class="subtotal-row">
                    <td colspan="4" class="right-align">SUBTOTAL ({{ vendor.name }})</td>
                    <td class="right-align">{{ vendor.subtotal_f }}</td>
                </tr>
                {% endif %}
            </tbody>
        </table>
    </div>
    {% else %}<p>No vendors or items listed.</p>{% endfor %}

    <!-- Grand Total --><hr style="border-top: 1.5px solid #555;">
    <table><tbody><tr class="grand-total-row"><td colspan="4" class="right-align">GRAND TOTAL</td><td class="right-align">{{ grand_total_f }}</td></tr></tbody></table><hr>

    <!-- Closing Text --><div class="closing">{{ closing_text }}</div><div class="thanking">{{ thanking_text }}<br>Team PICT ROBOTICS</div>
    <!-- Signatures --><div class="signature-block"><div class="signature-left">{{ signatory_left | safe }}</div><div class="signature-right">{{ signatory_right | safe }}</div></div>

    <!-- Screenshot Section (Appended at the end) -->
    {# Use selectattr filter to check if any item has a truthy 'screenshot_base64' attribute #}
    {% set screenshot_items = all_items_for_screenshots | selectattr('screenshot_base64') | list %}
    {% if screenshot_items %}
    <div class="screenshot-section">
        <div class="screenshot-title">Product Screenshots</div>
        {# Iterate through the filtered list #}
        {% for item in screenshot_items %}
            <div class="screenshot-item">
                <div class="screenshot-item-name">Item: {{ item.component }} (Vendor: {{ item.vendor }})</div>
                <img src="{{ item.screenshot_base64 }}" alt="Screenshot for {{ item.component }}">
            </div>
        {% endfor %}
    </div>
    {% endif %}
    <!-- Footer managed by CSS @page -->
</body>
</html>
"""

# --- Streamlit UI ---
# st.set_page_config(layout="wide") # <<< REMOVED FROM HERE
st.title("PICT Robotics - Purchase Letter Generator") # This is now okay

st.sidebar.header("Letter Details")
# Use dynamic date and allow modification
today_date_str = datetime.date.today().strftime("%d/%m/%Y")
ref_no_input = st.sidebar.text_input("Reference No.", DEFAULT_REF_NO.replace("DATE", datetime.date.today().strftime("%b%d").upper()))
letter_date_input = st.sidebar.text_input("Letter Date (DD/MM/YYYY)", today_date_str)
# Add more sidebar inputs for other config if needed (To, Subject, Signatories etc.)
# Example: subject_input = st.sidebar.text_input("Subject", DEFAULT_SUBJECT)
# Example: to_recipient_input = st.sidebar.text_area("To Recipient", DEFAULT_TO_RECIPIENT, height=100)

st.sidebar.header("Options")
# Default to False as it's problematic on Cloud
enable_screenshots_input = st.sidebar.checkbox("Attempt Screenshots (Requires local Chrome/Driver, Unlikely on Cloud)", value=False)

st.header("Paste Item List (Tab-Separated)")
st.caption("Columns: #Sr | Component | Category | Unit Price | Qty | Total Price | Notes | Vendor Alias | Vendor Platform | Purpose | Status | Link")
# Example data for the text area
example_tsv = """#Sr\tComponent\tCategory\tUnit Price\tQty\tTotal Price\tNotes\tVendor Alias\tVendor Platform\tPurpose\tStatus\tLink
30\tHeat Sink\tMisc\t₹7.00\t25\t₹175.00\t\tRajiv\tRajiv Electronics\tMisc\tRecieved\thttps://rajivelectronics.com/product/to-220-15mm-black-aluminium-heat-sink-with-pin/
31\tToggle Switch\tMisc\t₹72.00\t15\t₹1,080.00\t\tRajiv\tRajiv Electronics\tMisc\tRecieved\thttps://rajivelectronics.com/product/aditya-metal-toggle-switch-15a-spdt-on-on-t-152/
32\t58GW-3157 24V 10RPM DC Worm Gear Motor\tMechanical\t₹2,250.00\t2\t₹4,500.00\tZbotic Alt\t\tRoboticsDNA\tPivot Motor\tRecieved\thttps://roboticsdna.in/product/58gw-3157-24v-10rpm-single-shaft-dc-worm-gear-motor/
34\tSHF8 Horizontal Shaft Support\tMechanical\t₹74.00\t4\t₹296.00\t\tRobu.in\tRobu.in\tFrame\tListed\thttps://robu.in/product/horizontal-shaft-support-shf8-for-3d-printers/
38\tRaspberry Pi 4 Model B (4GB)\tElectronics\t₹5,500.00\t1\t₹5,500.00\tLocal/Amazon\t\tAmazon\tCompute\tListed\thttps://www.amazon.in/Raspberry-Pi-Model-4GB-RAM/dp/B07V5JTMV9/
40\tMissing Link Item\tTest\t₹10.00\t1\t₹10.00\tTest\t\tTestVendor\tTest\tListed\t
41\tInvalid Link Item\tTest\t₹20.00\t1\t₹20.00\tTest\t\tTestVendor\tTest\tListed\tinvalid-url"""
raw_items_data = st.text_area("Paste your tab-separated data here:", value=example_tsv, height=250)

# Placeholder for PDF download button
pdf_download_placeholder = st.empty()

if st.button("Generate Purchase Letter PDF"):
    if not raw_items_data.strip():
        st.error("Input data cannot be empty.")
    else:
        # Show spinner during processing
        with st.spinner("Processing data and generating PDF... This might take a while if screenshots are enabled."):
            try:
                # 1. Load Header Images
                st.info("Loading header images...")
                header_images_b64 = {
                    'left': image_to_base64(HEADER_IMG_LEFT_PATH),
                    'right': image_to_base64(HEADER_IMG_RIGHT_PATH)
                }
                if not header_images_b64['left'] or not header_images_b64['right']:
                     st.error("Failed to load one or both header images. Check paths and file integrity in the app's directory.")
                     st.stop() # Stop execution if headers failed

                # 2. Parse Input
                items = agent_1_parse_input(raw_items_data)
                if not items:
                    st.error("Workflow aborted: No valid items parsed from the input.")
                    st.stop()

                # 3. Screenshots (Conditional)
                if enable_screenshots_input:
                    if SELENIUM_AVAILABLE:
                        st.info("Attempting to take screenshots...")
                        items = take_screenshots_func(items) # Calls the real function
                    else:
                        st.warning("Screenshot option selected, but setup failed or is unavailable in this environment. Skipping screenshots.")
                        st.warning(f"Reason: {SCREENSHOT_ERROR_MESSAGE}")
                        items = take_screenshots_dummy(items) # Ensure key exists
                else:
                    st.info("Screenshot generation disabled by user choice.")
                    items = take_screenshots_dummy(items) # Ensure key exists

                # 4. Group Items
                grouped_items = agent_2_group_by_vendor(items)
                if not grouped_items:
                    st.error("Workflow aborted: No vendors found after grouping. Check 'Vendor Platform' column in input.")
                    st.stop()

                # 5. Enrich Data
                # Gather letter config from inputs or defaults
                # Use sidebar inputs if they were defined, otherwise use defaults
                letter_config = {
                    'ref_no': ref_no_input,
                    'letter_date': letter_date_input,
                    'to_recipient': DEFAULT_TO_RECIPIENT, # Replace with to_recipient_input if added
                    'subject': DEFAULT_SUBJECT,           # Replace with subject_input if added
                    'intro_text': DEFAULT_INTRO_TEXT,
                    'closing_text': DEFAULT_CLOSING_TEXT,
                    'thanking_text': DEFAULT_THANKING_TEXT,
                    'signatory_left': DEFAULT_SIGNATORY_LEFT,
                    'signatory_right': DEFAULT_SIGNATORY_RIGHT,
                    'header_text': DEFAULT_HEADER_TEXT,
                }
                enriched_data = agent_4_enrich_data(grouped_items, letter_config, header_images_b64)
                if not enriched_data:
                    st.error("Workflow aborted: Data enrichment failed.")
                    st.stop()

                # 6. Generate HTML
                html_content = agent_5_generate_content(enriched_data, purchase_letter_template_html)
                if not html_content:
                    st.error("Workflow aborted: HTML content generation failed.")
                    st.stop()

                # --- Optional: Save HTML for debugging ---
                # try:
                #     # Use tempfile for better cross-platform temp dirs
                #     with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tmp_html:
                #          tmp_html.write(html_content)
                #          st.info(f"Debug HTML saved temporarily to: {tmp_html.name}")
                # except Exception as e_html:
                #     st.warning(f"Could not save debug HTML: {e_html}")
                # ---

                # 7. Generate PDF Bytes
                pdf_bytes = agent_6_generate_pdf(html_content)

                # 8. Provide Download
                if pdf_bytes:
                    st.success("🎉 PDF Generated Successfully!")
                    # Generate a filename
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    pdf_filename = f"Purchase_Letter_{timestamp}.pdf"

                    # Display download button IN THE PLACEHOLDER
                    # Use the placeholder to ensure button appears in the main area below the text input
                    pdf_download_placeholder.download_button(
                        label="⬇️ Download PDF",
                        data=pdf_bytes,
                        file_name=pdf_filename,
                        mime="application/pdf",
                    )
                else:
                    st.error("PDF generation failed. Check logs above.")
                    pdf_download_placeholder.empty() # Clear placeholder if failed

            except Exception as e:
                st.error(f"An unexpected error occurred during the workflow: {e}")
                traceback.print_exc()
                pdf_download_placeholder.empty() # Clear placeholder on error

# --- Footer/Info ---
st.markdown("---")
st.markdown("Created for PICT Robotics Club")
# Display screenshot status message in sidebar based on current state
if enable_screenshots_input and not SELENIUM_AVAILABLE:
     st.sidebar.error(f"Screenshot Error: {SCREENSHOT_ERROR_MESSAGE}")
elif SCREENSHOT_ERROR_MESSAGE: # Display if there was an error, even if screenshots are off now
     st.sidebar.warning(f"Screenshot Status: {SCREENSHOT_ERROR_MESSAGE}")
