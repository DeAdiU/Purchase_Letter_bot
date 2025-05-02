# main.py
import os
import sys
import datetime
from jinja2 import Environment, Template
from weasyprint import HTML, CSS
from collections import defaultdict
import locale
import re # For cleaning price strings and parsing
import base64 # For embedding images
import traceback # For detailed error printing

# --- Import the screenshot module ---
# Assumes screenshot_module.py exists and uses undetected-chromedriver
      
SELENIUM_AVAILABLE = False # Assume False initially
def take_screenshots(items_list):
    # This dummy function will be used if the real one cannot be imported.
    # The specific warning message will be printed by the except block.
    for item in items_list:
        item['screenshot_base64'] = None
    return items_list

try:
    # Try importing the real function
    from screenshot_module import take_screenshots as real_take_screenshots
    # If import succeeds, overwrite the dummy function with the real one
    take_screenshots = real_take_screenshots
    SELENIUM_AVAILABLE = True
    print("INFO: Successfully imported screenshot_module.") # Add success message
except ImportError:
    # Keep the dummy function defined above
    print("WARNING: screenshot_module.py not found or undetected-chromedriver not installed.")
    print("         Screenshots will be skipped.")
    SELENIUM_AVAILABLE = False # Ensure it's False
except Exception as e:
    # Keep the dummy function defined above
    print(f"ERROR: Unexpected error importing screenshot_module: {e}")
    print("       Screenshots will be skipped.")
    traceback.print_exc(limit=1)
    SELENIUM_AVAILABLE = False # Ensure it's False


# --- Configuration ---
BASE_DIR = '.' # Use current directory for local execution
OUTPUT_DIR = os.path.join(BASE_DIR, 'output') # Output folder in the same directory
ENABLE_SCREENSHOTS = True # Set to False to disable screenshot generation

# --- Letter Configuration (Customize these) ---
REF_NO = "PICT/ROBOTICS/APR25/11" # Incremented Ref No example
LETTER_DATE = datetime.date.today().strftime("%d/%m/%Y") # Format DD/MM/YYYY
TO_RECIPIENT = """
The Director/Principal,
Pune Institute of Computer Technology,
Pune 411043.
"""
SUBJECT = "Online purchase of components for PICT ROBOTICS CLUB (with Screenshots)."
INTRO_TEXT = "This letter is related to the purchase of components which are to be purchased for the ABU Robocon 2025. Product screenshots are attached for reference where available."
CLOSING_TEXT = "We request you please direct the accounts department to buy the listed components online."
THANKING_TEXT = "Thanking you in anticipation,"
SIGNATORY_LEFT = "Titeer Deshpande\nTeam Captain"
HEADER_TEXT = """
Society For Computer Technology and Research's<br>
PUNE INSTITUTE OF COMPUTER TECHNOLOGY<br>
Pune - 411 043<br>
<strong style="font-size: 1.1em;">PICT ROBOTICS CLUB</strong><br>
Website: http://pictrobotics.com<br>
Email: robocon@pict.edu
"""
SIGNATORY_RIGHT = "Dr. S. V. Gaikwad\nTeacher Coordinator"

# --- Header/Footer Info ---
HEADER_IMG_LEFT_PATH = os.path.abspath(os.path.join(BASE_DIR, "pict1.jpg"))
HEADER_IMG_RIGHT_PATH = os.path.abspath(os.path.join(BASE_DIR, "pictrobotics_logo.jpg"))

# --- Helper Functions (parse_price, image_to_base64 - unchanged from previous working version) ---
def parse_price(price_str):
    """Removes currency symbols (₹, $) and commas, converts to float."""
    if isinstance(price_str, (int, float)): return float(price_str)
    if price_str is None: return 0.0
    # Remove currency symbols, commas, and potentially leading/trailing whitespace
    cleaned_price = re.sub(r'[₹$,]', '', str(price_str)).strip()
    try:
        return float(cleaned_price)
    except ValueError:
        print(f"DEBUG (parse_price): Failed to parse price '{price_str}', returning 0.0")
        return 0.0

def image_to_base64(image_path):
    """Converts an image file to a base64 data URI."""
    print(f"DEBUG (image_to_base64): Attempting to convert image: {image_path}")
    if not os.path.exists(image_path):
        print(f"  ERROR (image_to_base64): File does NOT exist at this path.")
        return None
    if not os.path.isfile(image_path):
        print(f"  ERROR (image_to_base64): Path exists but is not a file.")
        return None
    try:
        with open(image_path, "rb") as img_file:
            img_bytes = img_file.read()
            file_size = len(img_bytes)
            if not img_bytes:
                print(f"  ERROR (image_to_base64): File is empty.")
                return None

            mime_type = f"image/{os.path.splitext(image_path)[1][1:].lower()}"
            if mime_type == "image/jpg": mime_type = "image/jpeg" # Common correction
            if mime_type not in ["image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"]:
                 print(f"  WARNING (image_to_base64): Potentially unsupported image mime type: {mime_type}")

            base64_str = base64.b64encode(img_bytes).decode('utf-8')
            result = f"data:{mime_type};base64,{base64_str}"
            print(f"  SUCCESS (image_to_base64): Converted image to Base64.")
            return result
    except FileNotFoundError:
        print(f"  ERROR (image_to_base64): FileNotFoundError during open/read.")
        return None
    except Exception as e:
        print(f"  ERROR (image_to_base64): Failed to read or encode image: {e}")
        traceback.print_exc()
        return None

# --- Agent Functions (Adapted) ---

def agent_1_parse_input(raw_items_data):
    """Parses TSV-like input: Sr, Item, Cat, Price, Qty, Total, Notes, Vendor Alias, Vendor Platform, Purp, Status, Link"""
    structured_items = []
    lines = raw_items_data.strip().split('\n')
    print(f"\nAgent 1: Parsing {len(lines)} lines from input data...")
    # Define column indices (0-based) - CORRECTED
    COL_ITEM_NAME = 1
    COL_UNIT_PRICE = 3
    COL_QTY = 4
    COL_VENDOR = 8     # CORRECTED: Vendor Platform is the 9th column (index 8)
    COL_LINK = 11      # CORRECTED: Link is the 12th column (index 11)

    # Determine the maximum required column index + 1
    min_required_cols = max(COL_ITEM_NAME, COL_UNIT_PRICE, COL_QTY, COL_VENDOR, COL_LINK) + 1
    print(f"DEBUG (Agent 1): Minimum required columns based on indices: {min_required_cols}")

    for i, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith('#') or not line[0].isdigit():
             continue

        parts = line.split('\t')
        # Use the calculated min_required_cols for the check
        if len(parts) < min_required_cols:
            # Try splitting by multiple spaces ONLY if tab split failed significantly
            if len(parts) < 5: # Heuristic: if very few columns, maybe spaces were used
                 print(f"Warning (Agent 1): Line {i+1} has few parts ({len(parts)}) after tab split. Trying regex split: {line[:100]}...") # Print start of line
                 parts = re.split(r'\s{2,}', line)

            # Check again after potential regex split
            if len(parts) < min_required_cols:
                print(f"Warning (Agent 1): Skipping line {i+1} due to insufficient columns (need {min_required_cols}, got {len(parts)} after splits): {line[:100]}...")
                continue

        try:
            # Use the CORRECTED indices
            name = parts[COL_ITEM_NAME].strip()
            qty_str = parts[COL_QTY].strip()
            price_str = parts[COL_UNIT_PRICE].strip()
            # Ensure index exists before accessing
            vendor = parts[COL_VENDOR].strip() if len(parts) > COL_VENDOR and parts[COL_VENDOR] else "Unknown Vendor"
            link = parts[COL_LINK].strip() if len(parts) > COL_LINK and parts[COL_LINK] else None

            # Add a debug print here to see what's being extracted
            print(f"DEBUG (Agent 1): Line {i+1} Parsed -> Name: '{name}', Vendor: '{vendor}', Link: '{link}'")

            if not name:
                print(f"Warning (Agent 1): Skipping line {i+1} due to missing item name: {line[:100]}...")
                continue

            qty = int(qty_str)
            price = parse_price(price_str) # Uses updated parse_price

            if price >= 0: # Allow price 0
                 structured_items.append({
                    'id': i + 1, # Use line number as a temporary ID
                    'component': name,
                    'specification': name, # Use name as spec for now
                    'quantity': qty,
                    'cost_per_piece': price,
                    'vendor': vendor, # Correct vendor
                    'link': link      # Correct link
                 })
            else:
                 # Price parsing failure already logged by parse_price
                 print(f"Warning (Agent 1): Skipping line {i+1} due to invalid price ({price_str}): {line[:100]}...")

        except (ValueError, IndexError) as e:
            print(f"Warning (Agent 1): Skipping line {i+1} due to parsing error ({type(e).__name__}: {e}): {line[:100]}...")
            if isinstance(e, IndexError):
                 print(f"  >> Attempted to access index out of bounds. Parts length: {len(parts)}. Indices used: Name={COL_ITEM_NAME}, Qty={COL_QTY}, Price={COL_UNIT_PRICE}, Vendor={COL_VENDOR}, Link={COL_LINK}")
            elif isinstance(e, ValueError):
                 print(f"  >> Failed converting quantity '{qty_str}' to integer.")
        except Exception as e:
            print(f"Warning (Agent 1): Skipping line {i+1} due to unexpected error ({type(e).__name__}: {e}): {line[:100]}...")
            traceback.print_exc(limit=1) # Print limited traceback for unexpected errors

    print(f"Agent 1: Successfully parsed {len(structured_items)} items.")
    return structured_items


def agent_2_group_by_vendor(items):
    """Groups items by vendor."""
    print("\nAgent 2: Grouping items by vendor...")
    grouped = defaultdict(list)
    vendor_map = {} # To track normalization

    for item in items:
        vendor_original = item.get('vendor', 'Unknown Vendor').strip()
        # Handle potential None vendor from parsing issues
        if not vendor_original:
            vendor_original = "Unknown Vendor"

        vendor_lower = vendor_original.lower()
        vendor_key = vendor_original # Default to original case

        # --- Vendor Normalization Logic ---
        if 'robu.in' in vendor_lower:
            vendor_key = 'Robu.in'
        elif 'roboticsdna' in vendor_lower:
            vendor_key = 'RoboticsDNA'
        elif 'amazon' in vendor_lower:
            vendor_key = 'Amazon'
        elif 'rajiv' in vendor_lower: # Match "Rajiv Electronics"
            vendor_key = 'Rajiv Electronics'
        # Add more rules as needed
        # --- End Normalization ---

        if vendor_original != vendor_key and vendor_original not in vendor_map:
            print(f"  Normalizing '{vendor_original}' to '{vendor_key}'")
            vendor_map[vendor_original] = vendor_key

        grouped[vendor_key].append(item)

    # Filter out "Unknown Vendor" if it contains no items OR if desired (optional)
    if "Unknown Vendor" in grouped and not grouped["Unknown Vendor"]:
        print("DEBUG (Agent 2): Removing empty 'Unknown Vendor' group.")
        del grouped["Unknown Vendor"]
    elif "Unknown Vendor" in grouped:
         print(f"Warning (Agent 2): {len(grouped['Unknown Vendor'])} items found under 'Unknown Vendor'. Check input data's Vendor Platform column (index 8).")


    print(f"Agent 2: Grouped items by {len(grouped)} vendors: {list(grouped.keys())}")
    return dict(grouped)


def agent_4_enrich_data(grouped_items):
    """Calculates totals, adds fees, formats currency (forcing Rupee), and embeds images."""
    print("\nAgent 4: Enriching data, adding fees, formatting currency, embedding images...")

    # --- Currency Formatting Setup ---
    currency_symbol = '₹'
    locale_found = False
    try:
        locales_to_try = ['en_IN.UTF-8', 'en_IN', 'hi_IN.UTF-8', 'hi_IN']
        for loc in locales_to_try:
            try:
                locale.setlocale(locale.LC_ALL, loc)
                test_format = locale.currency(1000, grouping=True, symbol=currency_symbol)
                if ',' in test_format or '.' in test_format[:-3]:
                    locale_found = True
                    print(f"DEBUG (Agent 4): Using '{loc}' locale for currency formatting.")
                    break
            except locale.Error:
                continue
        if not locale_found:
            print("Warning (Agent 4): No suitable 'en_IN' or 'hi_IN' locale found/effective. Using manual format.")
            locale.setlocale(locale.LC_ALL, '') # Reset to default C locale potentially
    except Exception as e:
        print(f"Warning (Agent 4): Error setting/testing locale ({e}). Using manual Rupee format.")
        locale.setlocale(locale.LC_ALL, '') # Reset

    def format_currency(value):
        try:
            numeric_value = float(value)
            if locale_found:
                return locale.currency(numeric_value, grouping=True, symbol=currency_symbol)
            else:
                # Manual formatting for Indian Rupees (lakh/crore separators)
                s = f"{numeric_value:,.2f}" # Standard comma separation first
                parts = s.split('.')
                integer_part = parts[0].replace(',', '')
                decimal_part = parts[1] if len(parts) > 1 else "00"
                # Ensure decimal part has 2 digits
                decimal_part = decimal_part.ljust(2, '0')[:2]

                if len(integer_part) <= 3:
                    formatted_integer = integer_part
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
            print(f"DEBUG (format_currency): Failed for value '{value}', returning as is.")
            return f"{currency_symbol} {value}" # Fallback
    # --- End Currency Formatting Setup ---

    # --- Image Embedding ---
    print("-" * 20)
    print("DEBUG (Agent 4): Processing Header Images:")
    header_img_left_b64 = image_to_base64(HEADER_IMG_LEFT_PATH)
    header_img_right_b64 = image_to_base64(HEADER_IMG_RIGHT_PATH)
    print("-" * 20)
    # --- End Image Embedding ---

    enriched_data = {
        'vendors': [],
        'all_items_for_screenshots': [], # Store flat list of items for screenshot section
        'grand_total': 0.0,
        'ref_no': REF_NO,
        'letter_date': LETTER_DATE,
        'to_recipient': TO_RECIPIENT.strip().replace('\n', '<br>'),
        'subject': SUBJECT,
        'intro_text': INTRO_TEXT,
        'closing_text': CLOSING_TEXT,
        'thanking_text': THANKING_TEXT,
        'signatory_left': SIGNATORY_LEFT.strip().replace('\n', '<br>'),
        'signatory_right': SIGNATORY_RIGHT.strip().replace('\n', '<br>'),
        'header_img_left': header_img_left_b64,
        'header_img_right': header_img_right_b64,
        'header_text': HEADER_TEXT.strip()
    }
    grand_total = 0.0
    all_items_flat = [] # Collect all items for the screenshot section

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
            # Add to the flat list *after* processing, includes screenshot data if present
            all_items_flat.append(item)

            vendor_item_subtotal += line_total

        vendor_subtotal_final = vendor_item_subtotal
        vendor_name_lower = vendor_key.lower()
        fee_applied = False
        fee_amount = 0.0 # Initialize fee amount for logging

        # --- Apply Vendor-Specific Fees ---
        if 'roboticsdna' in vendor_name_lower:
            fee_percentage = 0.025 # 2.5%
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
                special_charges.append({'description': fee_description, 'amount': fee_amount, 'amount_f': format_currency(fee_amount)})
                vendor_subtotal_final += fee_amount
                fee_applied = True
            else:
                 fee_amount = 0.00 # Explicitly zero
                 fee_description = f"Delivery Charges (Order >= {format_currency(delivery_threshold)})"
                 special_charges.append({'description': fee_description, 'amount': fee_amount, 'amount_f': format_currency(fee_amount)})
                 fee_applied = True # Mark as applied even if zero for logging consistency

        elif 'amazon' in vendor_name_lower:
            fee_amount = 100.00
            fee_description = "Delivery Charges"
            special_charges.append({'description': fee_description, 'amount': fee_amount, 'amount_f': format_currency(fee_amount)})
            vendor_subtotal_final += fee_amount
            fee_applied = True
        # --- End Vendor Fees ---

        if fee_applied: # Log if any fee logic was triggered
            print(f"  Applied '{fee_description}' ({format_currency(fee_amount)}) to {vendor_key}")

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
    enriched_data['all_items_for_screenshots'] = all_items_flat # Assign the flat list

    print(f"Agent 4: Data enrichment complete. Grand Total: {enriched_data['grand_total_f']}")
    print(f"DEBUG (Agent 4): Total items collected for potential screenshots: {len(all_items_flat)}")
    return enriched_data


def agent_5_generate_content(data, template_string):
    """Populates the template string with data."""
    print("\nAgent 5: Generating HTML content...")
    has_any_screenshots = False
    if 'all_items_for_screenshots' in data:
        # Use the same logic as the template to check for screenshots
        screenshots_list = [item for item in data['all_items_for_screenshots'] if item.get('screenshot_base64')]
        has_any_screenshots = bool(screenshots_list)
    print(f"DEBUG (Agent 5): Any screenshots available for rendering? {has_any_screenshots}")

    # Use Jinja Environment for better control (e.g., autoescape, extensions) if needed later
    # trim_blocks and lstrip_blocks help clean up whitespace in the template source
    env = Environment(trim_blocks=True, lstrip_blocks=True)
    template = env.from_string(template_string)
    try:
        html_content = template.render(data)
        print(f"Agent 5: HTML content generated successfully (length: {len(html_content)}).")

        # Debug: Check if screenshot data URI is present if expected
        if has_any_screenshots:
            found_ss_tag = False
            for item in screenshots_list: # Check only items that should have screenshots
                 # Check for the start of the base64 string in the HTML
                 if item['screenshot_base64'][:30] in html_content:
                     print(f"DEBUG (Agent 5): Found start of screenshot Base64 for item '{item.get('component', 'N/A')}' in generated HTML.")
                     found_ss_tag = True
                     # Don't break, check all expected ones if needed for thorough debug
                 else:
                      print(f"WARNING (Agent 5): Did NOT find start of screenshot Base64 for item '{item.get('component', 'N/A')}' in generated HTML.")
            if not found_ss_tag and screenshots_list: # If list wasn't empty but none found
                 print("WARNING (Agent 5): Screenshots were expected, but their Base64 data was NOT found in the generated HTML. Check template logic for the screenshot section.")

        return html_content
    except Exception as e:
        print(f"ERROR in Agent 5 (HTML Generation): {e}")
        traceback.print_exc()
        return None


def agent_6_generate_pdf(html_content, pdf_filename):
    """Converts HTML content to PDF."""
    print("\nAgent 6: Generating PDF...")
    print(f"  Output PDF path: {pdf_filename}")

    try:
        # --- CSS Definition --- (Includes screenshot styles)
        css = CSS(string='''
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
        ''')
        # --- End CSS Definition ---

        # Provide the base URL for resolving relative paths if any were used (though not needed for base64)
        html = HTML(string=html_content, base_url=os.path.abspath(BASE_DIR))
        html.write_pdf(pdf_filename, stylesheets=[css])
        print(f"Agent 6: PDF successfully generated: {pdf_filename}")
        return pdf_filename
    except Exception as e:
        print(f"ERROR in Agent 6 (PDF Generation): {e}")
        if "Pango" in str(e) or "font" in str(e).lower():
            print("\n*** Font Issue Detected ***")
            print("Ensure 'Times New Roman' is installed (e.g., 'ttf-mscorefonts-installer' on Debian/Ubuntu, 'ttf-ms-fonts' on Arch AUR) and font cache updated ('sudo fc-cache -fv').")
        if "failed to load image" in str(e).lower():
             print("\n*** WeasyPrint Image Loading Error Detected ***")
             print("This could be the header images OR the product screenshots.")
             print("Check Base64 strings (headers and screenshots) and MIME types (e.g., image/jpeg, image/png).")
        traceback.print_exc()
        return None

def run_workflow(raw_items_data, template_html, base_filename="Purchase_Letter"):
    """Runs the full agentic workflow, including optional screenshots."""
    print("\n--- Starting Purchase Letter Workflow ---")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Agent 1: Parse
    items = agent_1_parse_input(raw_items_data)
    if not items:
        print("Workflow aborted: No valid items parsed.")
        return None, None

    # --- Screenshot Step (Conditional) ---
    if ENABLE_SCREENSHOTS and SELENIUM_AVAILABLE:
            print("INFO (Workflow): Attempting to take screenshots...")
            items = take_screenshots(items) # Calls the real or dummy function
    elif ENABLE_SCREENSHOTS and not SELENIUM_AVAILABLE:
             # Message already printed during import failure
        print("INFO (Workflow): Skipping screenshots (dependencies previously reported missing).")
             # Ensure the key exists if needed later, though dummy function should handle this
        for item in items: item.setdefault('screenshot_base64', None)
    else:
        print("INFO (Workflow): Screenshot generation disabled.")
        for item in items: item.setdefault('screenshot_base64', None)
    # --- End Screenshot Step ---

    # Agent 2: Group
    grouped_items = agent_2_group_by_vendor(items)
    if not grouped_items:
        if items:
             print("Workflow aborted: No known vendors found after grouping. Check vendor names in input (Column 9 / Index 8).")
        else:
             print("Workflow aborted: No items to group.")
        return None, None

    # Agent 4: Enrich (Handles items potentially with screenshots)
    enriched_data = agent_4_enrich_data(grouped_items)
    if not enriched_data:
        print("Workflow aborted: Data enrichment failed.")
        return None, None

    # Agent 5: Generate HTML
    html_content = agent_5_generate_content(enriched_data, template_html)
    if not html_content:
        print("Workflow aborted: HTML content generation failed.")
        return None, None

    # --- Save HTML File ---
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # Add '_screenshots' to filename if they were attempted
    screenshot_suffix = "_screenshots" if ENABLE_SCREENSHOTS and SELENIUM_AVAILABLE else ""
    html_filename = os.path.join(OUTPUT_DIR, f"{base_filename}{screenshot_suffix}_{timestamp}.html")
    pdf_filename = os.path.join(OUTPUT_DIR, f"{base_filename}{screenshot_suffix}_{timestamp}.pdf")
    html_saved = False
    try:
        with open(html_filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"\nSuccessfully saved HTML file: {html_filename}")
        html_saved = True
    except Exception as e:
        print(f"\nERROR saving HTML file '{html_filename}': {e}")
    # --- End Save HTML File ---

    # Agent 6: Generate PDF
    pdf_file = agent_6_generate_pdf(html_content, pdf_filename)

    print("\n--- Workflow Execution Summary ---")
    status_parts = []
    if html_saved: status_parts.append("HTML saved")
    else: status_parts.append("HTML save FAILED")
    if pdf_file: status_parts.append("PDF generated")
    else: status_parts.append("PDF generation FAILED")
    if ENABLE_SCREENSHOTS and SELENIUM_AVAILABLE: status_parts.append("Screenshots attempted")
    elif ENABLE_SCREENSHOTS: status_parts.append("Screenshots skipped (deps missing)")
    else: status_parts.append("Screenshots disabled")

    print(f"Status: {' | '.join(status_parts)}")

    return html_filename if html_saved else None, pdf_file

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
  if ENABLE_SCREENSHOTS and SELENIUM_AVAILABLE:
            print("INFO (Workflow): Attempting to take screenshots...")
            items = take_screenshots(items) # Calls the real or dummy function
        elif ENABLE_SCREENSHOTS and not SELENIUM_AVAILABLE:
             # Message already printed during import failure
             print("INFO (Workflow): Skipping screenshots (dependencies previously reported missing).")
             # Ensure the key exists if needed later, though dummy function should handle this
             for item in items: item.setdefault('screenshot_base64', None)
        else:
            print("INFO (Workflow): Screenshot generation disabled.")
            for item in items: item.setdefault('screenshot_base64', None)          <td class="header-text-cell"><div class="header-text">{{ header_text | safe }}</div></td>
            <td class="header-logo-right">{% if header_img_right %}<img src="{{ header_img_right }}" alt="Right Logo">{% else %}<!-- Right logo missing -->{% endif %}</td>
        </tr>
    </table>
    <hr>

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
    {% if all_items_for_screenshots | selectattr('screenshot_base64') | list %}
    <div class="screenshot-section">
        <div class="screenshot-title">Product Screenshots</div>
        {# Iterate through ALL items collected in Agent 4 #}
        {% for item in all_items_for_screenshots %}
            {# Only display if a screenshot was successfully captured #}
            {% if item.screenshot_base64 %}
            <div class="screenshot-item">
                <div class="screenshot-item-name">Item: {{ item.component }} (Vendor: {{ item.vendor }})</div>
                <img src="{{ item.screenshot_base64 }}" alt="Screenshot for {{ item.component }}">
            </div>
            {% endif %}
        {% endfor %}
    </div>
    {% endif %}
    <!-- Footer managed by CSS @page -->
</body>
</html>
"""
print("HTML Template updated with corrected screenshot section check.")

# --- Input Data (Ensure TAB separated, Link is 12th column / index 11) ---
item_list_input_tsv = """#Sr\tComponent\tCategory\tUnit Price\tQty\tTotal Price\tNotes\tVendor Alias\tVendor Platform\tPurpose\tStatus\tLink
30\tHeat Sink\tMisc\t₹7.00\t25\t₹175.00\t\tRajiv\tRajiv Electronics\tMisc\tRecieved\thttps://rajivelectronics.com/product/to-220-15mm-black-aluminium-heat-sink-with-pin/
31\tToggle Switch\tMisc\t₹72.00\t15\t₹1,080.00\t\tRajiv\tRajiv Electronics\tMisc\tRecieved\thttps://rajivelectronics.com/product/aditya-metal-toggle-switch-15a-spdt-on-on-t-152/
32\t58GW-3157 24V 10RPM DC Worm Gear Motor\tMechanical\t₹2,250.00\t2\t₹4,500.00\tZbotic Alt\t\tRoboticsDNA\tPivot Motor\tRecieved\thttps://roboticsdna.in/product/58gw-3157-24v-10rpm-single-shaft-dc-worm-gear-motor/
33\t45GX-775 24V 500RPM IG 45 DC MOTOR\tMechanical\t₹2,749.00\t1\t₹2,749.00\t\t\tRoboticsDNA\tOmni Loco Motor\tRecieved\thttps://roboticsdna.in/product/45gx-775-24v-500rpm-45mm-dia-planetary-gear-motor/
34\tSHF8 Horizontal Shaft Support\tMechanical\t₹74.00\t4\t₹296.00\t\tRobu.in\tRobu.in\tFrame\tListed\thttps://robu.in/product/horizontal-shaft-support-shf8-for-3d-printers/
35\t1M 8 MM Smooth Rod\tMechanical\t₹347.00\t1\t₹347.00\t\tRobu.in\tRobu.in\tFrame\tListed\thttps://robu.in/product/1000-mm-long-chrome-plated-smooth-rod-diameter-8-mm/
36\tHXT 4mm to Banana Connector\tElectronics\t₹167.00\t1\t₹167.00\t\tRobu.in\tRobu.in\tWiring\tListed\thttps://robu.in/product/hxt-4mm-to-banana-plug-charge-lead-adapter/
37\tNylon T-Connector Male to Banana Connector Charge Adapter Cable\tElectronics\t₹125.00\t2\t₹250.00\t\tRobu.in\tRobu.in\tWiring\tListed\thttps://robu.in/product/charge-lead-banana-plugs-t-connector/
38\tRaspberry Pi 4 Model B (4GB)\tElectronics\t₹5,500.00\t1\t₹5,500.00\tLocal/Amazon\t\tAmazon\tCompute\tListed\thttps://www.amazon.in/Raspberry-Pi-Model-4GB-RAM/dp/B07V5JTMV9/
39\tUSB Webcam HD 1080p\tElectronics\t₹1,200.00\t1\t₹1,200.00\tGeneric\t\tAmazon\tVision\tListed\thttps://www.amazon.in/Logitech-C270-HD-Webcam-Black/dp/B003PAOAWG/
40\tMissing Link Item\tTest\t₹10.00\t1\t₹10.00\tTest\t\tTestVendor\tTest\tListed\t
41\tInvalid Link Item\tTest\t₹20.00\t1\t₹20.00\tTest\t\tTestVendor\tTest\tListed\tinvalid-url
"""
print("Input data format using Link column (index 11) - STRICT TABS.")


# --- Execute Workflow ---
if __name__ == "__main__":
    print("\n" + "="*50)
    print("Python script starting...")
    print(f"Current Working Directory: {os.getcwd()}")
    print(f"Output Directory: {os.path.abspath(OUTPUT_DIR)}")
    print(f"Screenshots Enabled: {ENABLE_SCREENSHOTS}")
    print(f"Selenium/UC Available: {SELENIUM_AVAILABLE}")
    print(f"Checking for input images:")
    print(f"  Left Image Path: {HEADER_IMG_LEFT_PATH} (Exists: {os.path.exists(HEADER_IMG_LEFT_PATH)})")
    print(f"  Right Image Path: {HEADER_IMG_RIGHT_PATH} (Exists: {os.path.exists(HEADER_IMG_RIGHT_PATH)})")
    print("="*50 + "\n")

    if not os.path.exists(HEADER_IMG_LEFT_PATH) or not os.path.exists(HEADER_IMG_RIGHT_PATH):
         print("\n*** ERROR: One or both header image files not found. Please ensure 'pict1.jpg' and 'pictrobotics_logo.jpg' are in the same directory as main.py ***\n")
         # sys.exit(1) # Optional: Exit if header images are critical

    # --- Run the workflow ---
    generated_html_path, generated_pdf_path = run_workflow(
        item_list_input_tsv,
        purchase_letter_template_html
    )
    # --- End Run ---


    # --- Confirmation ---
    print("\n" + "="*50)
    print("--- Final Status ---")
    if generated_html_path and os.path.exists(generated_html_path):
        print(f"Success! HTML generated at: {generated_html_path}")
        print(f"  >> Please open this HTML file in a web browser to verify content and images.")
    else:
        print("HTML generation failed or file not found.")

    if generated_pdf_path and os.path.exists(generated_pdf_path):
        print(f"Success! PDF generated at: {generated_pdf_path}")
        print(f"  >> Check this PDF file for the letter content and appended screenshots (if enabled/successful).")
    else:
        print("PDF generation failed or file not found.")

    if generated_html_path or generated_pdf_path:
        print(f"\nFind the generated files in the '{OUTPUT_DIR}' subfolder.")
        print(f"Full path: {os.path.abspath(OUTPUT_DIR)}")
    else:
        print("\nNo files were generated successfully. Check the output logs above for errors.")
    print("="*50)