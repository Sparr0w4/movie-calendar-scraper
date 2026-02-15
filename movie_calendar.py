import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime
import re
import os

def main():
    # 1. Setup & "Disguise"
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
    
    print(f"Scanning {len(rows)} rows...")

    for row in rows:
        cols = row.find_all("td")
        
        # HEADERS (e.g., "February 2026")
        if len(cols) == 1 or (len(cols) > 0 and "20" in cols[0].text and len(cols[0].text.strip()) < 25):
            text = cols[0].text.strip()
            try:
                dt = datetime.strptime(text, "%B %Y")
                current_month = dt.month
                current_year = dt.year
            except ValueError:
                pass
            continue

        # MOVIES
        if len(cols) >= 2:
            date_text = cols[0].text.strip()
            movie_title = cols[1].text.strip()

            if not date_text or not movie_title:
                continue

            try:
                # Clean date (remove st, nd, rd, th)
                clean_date = re.sub(r'(st|nd|rd|th)', '', date_text)
                
                # Parse date
                event_date = None
                if " " in clean_date: # Format: "February 15"
                    dt = datetime.strptime(clean_date, "%B %d")
                    event_date = dt.replace(year=current_year)
                    # Update context
                    current_month = dt.month
                elif clean_date.isdigit() and current_month: # Format: "15"
                    event_date = datetime(current_year, current_month, int(clean_date))
                
                if event_date:
                    e = Event()
                    e.name = f"🎬 {movie_title}"
                    e.begin = event_date.strftime("%Y-%m-%d")
                    e.make_all_day()
                    # Add distributor info if available
                    distributor = cols[2].text.strip() if len(cols) > 2 else "Unknown"
                    e.description = f"Distributor: {distributor}\nSource: The Numbers"
                    calendar.events.add(e)

            except Exception:
                continue

    # Save to file
    with open("movies.ics", 'w', encoding='utf-8') as f:
        f.writelines(calendar.serialize())
    
    print(f"Successfully saved {len(calendar.events)} movies to movies.ics")

if __name__ == "__main__":
    main()
