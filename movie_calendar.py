import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime
import re

def is_date_text(text):
    """
    Returns True if text looks like 'February 15' or '15' or '15th'.
    Returns False if it looks like a Movie Title.
    """
    # Pattern 1: Starts with a digit (e.g., "15", "15th")
    if re.match(r'^\d+(st|nd|rd|th)?$', text):
        return True
    # Pattern 2: Starts with a Month Name (e.g., "February 15")
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    if any(text.startswith(m) for m in months):
        return True
    
    return False

def main():
    url = "https://www.the-numbers.com/movies/release-schedule"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching page: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    calendar = Calendar()

    # Find the main table
    div = soup.find("div", id="page_filling_chart")
    table = div.find("table") if div else soup.find("table")

    if not table:
        print("Could not find table.")
        return

    rows = table.find_all("tr")
    
    current_year = datetime.now().year
    current_month = None
    current_day = None # Keep track of the last seen day
    
    print(f"Scanning {len(rows)} rows...")

    for row in rows:
        cols = row.find_all("td")
        
        # --- CASE 1: Header Row (e.g., "February 2026") ---
        if len(cols) == 1 or (len(cols) > 0 and "20" in cols[0].text and len(cols[0].text.strip()) < 25):
            text = cols[0].text.strip()
            try:
                dt = datetime.strptime(text, "%B %Y")
                current_month = dt.month
                current_year = dt.year
                current_day = None # Reset day on new month
            except ValueError:
                pass
            continue

        # --- CASE 2: Movie Row ---
        if len(cols) >= 1:
            col0_text = cols[0].text.strip()
            
            # Determine if this row HAS a date, or INHERITS the date
            has_date = is_date_text(col0_text)
            
            if has_date:
                # Row Structure: [Date] [Movie] [Distributor]
                if len(cols) < 2: continue # Malformed row
                date_text = col0_text
                movie_title = cols[1].text.strip()
                distributor_idx = 2
            else:
                # Row Structure: [Movie] [Distributor] (Inherits date)
                if current_day is None: continue # Skip if we haven't seen a date yet
                date_text = str(current_day) # Reuse last date
                movie_title = col0_text
                distributor_idx = 1
                
            # --- Parse the Date ---
            try:
                clean_date = re.sub(r'(st|nd|rd|th)', '', date_text)
                
                # Update State if it's a new date
                if has_date:
                    if " " in clean_date: # "February 15"
                        dt = datetime.strptime(clean_date, "%B %d")
                        current_month = dt.month
                        current_day = dt.day
                    elif clean_date.isdigit(): # "15"
                        current_day = int(clean_date)
                
                # --- Create Event ---
                if current_year and current_month and current_day:
                    # Construct valid YYYY-MM-DD
                    event_date = datetime(current_year, current_month, current_day)
                    
                    e = Event()
                    e.name = f"🎬 {movie_title}"
                    e.begin = event_date.strftime("%Y-%m-%d")
                    e.make_all_day()
                    
                    # Add distributor info if available
                    distributor = cols[distributor_idx].text.strip() if len(cols) > distributor_idx else "Unknown"
                    e.description = f"Distributor: {distributor}\nSource: The Numbers"
                    
                    calendar.events.add(e)

            except Exception as e:
                # print(f"Skipping row: {movie_title} - {e}")
                continue

    # Save to file
    with open("movies.ics", 'w', encoding='utf-8') as f:
        f.writelines(calendar.serialize())
    
    print(f"Successfully saved {len(calendar.events)} movies to movies.ics")

if __name__ == "__main__":
    main()
