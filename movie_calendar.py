import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime
import re
import sys

def clean_date_text(text):
    """Removes st, nd, rd, th and extra whitespace."""
    if not text:
        return ""
    text = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', text)
    return text.strip()

def main():
    # 1. Fetch the Page
    url = "https://www.the-numbers.com/movies/release-schedule"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    print(f"Fetching {url}...")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"CRITICAL ERROR: Could not fetch page. {e}")
        sys.exit(1)

    # 2. Parse HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Try to find the specific release schedule table
    # It usually has ID 'page_filling_chart'
    div = soup.find("div", id="page_filling_chart")
    if div:
        table = div.find("table")
    else:
        # Fallback: Find the biggest table on the page
        print("Warning: 'page_filling_chart' not found. Searching for largest table...")
        tables = soup.find_all("table")
        if not tables:
            print("CRITICAL ERROR: No tables found on page.")
            sys.exit(1)
        table = max(tables, key=lambda t: len(t.find_all("tr")))

    rows = table.find_all("tr")
    print(f"Found table with {len(rows)} rows. Processing...")

    # 3. State Machine Variables
    calendar = Calendar()
    current_year = datetime.now().year
    current_month = datetime.now().month
    current_day = datetime.now().day
    
    # We track 'last_valid_date' to handle the empty cells
    last_valid_date = None 

    count_added = 0

    for i, row in enumerate(rows):
        cols = row.find_all("td")
        
        # SKIP empty rows or headers
        if not cols:
            # Check if it's a "Month Year" header inside a <td>? 
            # Sometimes headers are <td> with colspan
            continue

        # --- DETECT SECTION HEADERS (e.g. "February 2026") ---
        # These usually have 1 column or are bolded text spanning the row
        row_text = row.get_text(" ", strip=True)
        # Check if the row text matches "Month Year" pattern
        header_match = re.search(r'^([A-Z][a-z]+)\s+(\d{4})', row_text)
        if header_match and len(cols) < 3: # Headers usually have few columns
            try:
                dt_header = datetime.strptime(header_match.group(0), "%B %Y")
                current_year = dt_header.year
                current_month = dt_header.month
                current_day = None # Reset day
                # print(f"--- DETECTED MONTH: {dt_header.strftime('%B %Y')} ---")
                continue
            except ValueError:
                pass

        # --- PARSE MOVIE ROW ---
        # Typical structure: [Date] [Movie Title] [Distributor] ...
        # But 'Date' might be empty if it continues from previous row
        
        # Safety check: we need at least a movie title (col 1)
        if len(cols) < 2:
            continue

        col0_text = clean_date_text(cols[0].get_text())
        col1_text = cols[1].get_text(strip=True) # Movie Title

        # LOGIC:
        # 1. If Col0 has a Month (e.g. "February 15"), update Month/Day.
        # 2. If Col0 is just a number (e.g. "15"), update Day.
        # 3. If Col0 is empty, use previous Day.

        try:
            # Check for "Month Day" format (e.g. "February 15")
            if any(m in col0_text for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]):
                # Be careful of "February 2026" inside the column
                if "202" in col0_text and len(col0_text) < 15:
                     # It's a header disguised as a column
                    dt = datetime.strptime(col0_text, "%B %Y")
                    current_year = dt.year
                    current_month = dt.month
                    current_day = None
                    continue
                
                # Parse "February 15"
                dt = datetime.strptime(col0_text, "%B %d")
                current_month = dt.month
                current_day = dt.day
                last_valid_date = datetime(current_year, current_month, current_day)
            
            # Check for Day only (e.g. "15")
            elif col0_text.isdigit():
                current_day = int(col0_text)
                if current_month:
                    last_valid_date = datetime(current_year, current_month, current_day)
            
            # Check for Empty (Same as last)
            elif col0_text == "":
                # Keep last_valid_date
                pass

            # IF we have a valid date and a movie title, ADD EVENT
            if last_valid_date and col1_text:
                e = Event()
                e.name = f"🎬 {col1_text}"
                e.begin = last_valid_date.strftime("%Y-%m-%d")
                e.make_all_day()
                
                distributor = cols[2].get_text(strip=True) if len(cols) > 2 else "Unknown"
                e.description = f"Distributor: {distributor}\nSource: The Numbers"
                e.uid = f"{last_valid_date.strftime('%Y%m%d')}-{re.sub(r'[^a-zA-Z0-9]', '', col1_text)}@numbers"
                
                calendar.events.add(e)
                count_added += 1
                # print(f"Added: {col1_text} on {last_valid_date.strftime('%Y-%m-%d')}")

        except Exception as e:
            # print(f"Skipping row due to error: {e} | Text: {row_text}")
            continue

    # 4. Save
    with open("movies.ics", 'w', encoding='utf-8') as f:
        f.writelines(calendar.serialize())
    
    print(f"SUCCESS: Generated movies.ics with {count_added} events.")

if __name__ == "__main__":
    main()
