import requests
import datetime
import re
from urllib.parse import urljoin
import time as pytime

MONTH_MAP_NSZ = {
    'január': '01', 'február': '02', 'március': '03', 'április': '04',
    'május': '05', 'június': '06', 'július': '07', 'augusztus': '08',
    'szeptember': '09', 'október': '10', 'november': '11', 'december': '12',
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
    'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
}


# Segédfüggvény a szövegek tisztításához
def clean_text(text):
    if text:
        return re.sub(r'\s+', ' ', text).strip()
    return None


def get_absolute_url(base_url, relative_url):
    if not relative_url or relative_url.startswith(('http://', 'https://', 'www.')):
        if relative_url.startswith('www.'):
            return 'https://' + relative_url
        return relative_url
    return urljoin(base_url, relative_url)


CINEMAS_DATA_CC = {
    "1124": {"name": "Alba", "city": "Székesfehérvár"},
    "1133": {"name": "Allee", "city": "Budapest"},
    "1132": {"name": "Aréna", "city": "Budapest"},
    "1131": {"name": "Balaton", "city": "Veszprém"},
    "1139": {"name": "Campona", "city": "Budapest"},
    "1127": {"name": "Cinema City Debrecen", "city": "Debrecen"},
    "1141": {"name": "Duna Pláza", "city": "Budapest"},
    "1125": {"name": "Cinema City Győr", "city": "Győr"},
    "1144": {"name": "Mammut I-II.", "city": "Budapest"},
    "1129": {"name": "Cinema City Miskolc", "city": "Miskolc"},
    "1143": {"name": "Cinema City Nyíregyháza", "city": "Nyíregyháza"},
    "1128": {"name": "Cinema City Pécs", "city": "Pécs"},
    "1134": {"name": "Savaria", "city": "Szombathely"},
    "1136": {"name": "Cinema City Sopron", "city": "Sopron"},
    "1126": {"name": "Cinema City Szeged", "city": "Szeged"},
    "1130": {"name": "Cinema City Szolnok", "city": "Szolnok"},
    "1137": {"name": "Westend", "city": "Budapest"},
    "1135": {"name": "Cinema City Zalaegerszeg", "city": "Zalaegerszeg"},
}


def scrape_cinema_city():
    print("Cinema City API scraper fut...")
    all_events_data = []
    API_BASE_URL = "https://www.cinemacity.hu/hu/data-api-service/v1/quickbook/10102/film-events/in-cinema/"
    today = datetime.date.today()
    date_range = [today + datetime.timedelta(days=i) for i in range(7)]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'hu-HU,hu;q=0.9,en-US;q=0.8,en;q=0.7'
    }

    for cinema_id, cinema_info in CINEMAS_DATA_CC.items():
        for date_obj in date_range:
            date_str = date_obj.strftime('%Y-%m-%d')
            api_url = f"{API_BASE_URL}{cinema_id}/at-date/{date_str}?attr=&lang=hu_HU"
            print(f"Cinema City: Kérés küldése: {api_url}")

            try:
                response = requests.get(api_url, headers=headers, timeout=15)
                response.raise_for_status()
                data = response.json()
                # print(f"Cinema City: Adat sikeresen fogadva {cinema_info['name']} ({date_str}) számára.")

                if not data or 'body' not in data or not data['body']:
                    # print(f"Cinema City: Üres 'body' vagy hiányzó 'body' a válaszban: {api_url}")
                    continue

                films_data = data['body'].get('films', [])
                events_data = data['body'].get('events', [])

                if not films_data and not events_data:
                    continue

                films_dict = {film['id']: film for film in films_data}

                for event_item in events_data:
                    film_id = event_item.get('filmId')
                    film_details = films_dict.get(film_id)

                    if not film_details:
                        # print(f"Cinema City: Nem található film részlet a filmId '{film_id}'-hez. Esemény ID: {event_item.get('id')}")
                        continue

                    title = clean_text(film_details.get('name'))
                    event_datetime_str = event_item.get('eventDateTime')

                    parsed_date = "N/A"
                    parsed_time = "N/A"
                    if event_datetime_str:
                        try:
                            dt_obj = datetime.datetime.fromisoformat(event_datetime_str)
                            parsed_date = dt_obj.strftime('%Y-%m-%d')
                            parsed_time = dt_obj.strftime('%H:%M')
                        except ValueError:
                            parsed_date = event_item.get('businessDay', "N/A")

                    booking_link_obj = event_item.get('compositeBookingLink', {}).get('bookingUrl', {})
                    booking_link = booking_link_obj.get('url')
                    if booking_link and booking_link_obj.get('params'):
                        param_str = "&".join([f"{k}={v}" for k, v in booking_link_obj['params'].items()])
                        if param_str:
                            booking_link += "?" + param_str

                    if not booking_link:
                        booking_link = event_item.get('bookingLink')

                    attributes = film_details.get('attributeIds', [])
                    description = f"{title} film. Jellemzők: {', '.join(attributes)}. Vetítés a {cinema_info['name']} moziban." \
                        if attributes else f"{title} film a {cinema_info['name']} moziban."

                    poster_url = film_details.get('posterLink')

                    event_entry = {
                        "source_event_id": str(event_item.get('id')),
                        "title": title,
                        "type": "Mozi",
                        "venue": cinema_info['name'],
                        "city": cinema_info['city'],
                        "date": parsed_date,
                        "time": parsed_time,
                        "price": None,
                        "description": description,
                        "booking_url": booking_link,
                        "poster_url": poster_url,
                        "source": "Cinema City"
                    }
                    all_events_data.append(event_entry)

                pytime.sleep(0.3)  # Kis szünet növelve

            except requests.exceptions.Timeout:
                print(f"Hiba a Cinema City API hívása közben: Időtúllépés ({api_url})")
            except requests.exceptions.RequestException as e:
                print(f"Hiba a Cinema City API hívása közben: {e} ({api_url})")
            except ValueError as e:
                print(f"Hiba a Cinema City JSON válaszának feldolgozása közben: {e} ({api_url})")
            except Exception as e:
                print(f"Általános hiba a Cinema City API scraping során ({cinema_info['name']}, {date_str}): {e}")
                import traceback
                traceback.print_exc()

    if not all_events_data:
        print("Cinema City: Nem sikerült eseményeket kinyerni az API-ból.")
    else:
        print(f"Cinema City: Összesen {len(all_events_data)} esemény gyűjtve az API-ból.")
    return all_events_data


def scrape_nemzeti_szinhaz():
    print("Nemzeti Színház scraper fut...")
    events = []
    BASE_URL = "https://nemzetiszinhaz.hu"
    PROGRAM_URL = f"{BASE_URL}/musor"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        print(f"Nemzeti Színház: Kérés küldése ide: {PROGRAM_URL}")
        page = requests.get(PROGRAM_URL, headers=headers, timeout=15)
        page.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(page.content, "html.parser")

        date_blocks = soup.find_all('div', class_='date-item')

        if not date_blocks:
            print("Nemzeti Színház: Nem találhatóak 'date-item' blokkok.")
            return events

        # print(f"Nemzeti Színház: {len(date_blocks)} 'date-item' blokk található.")

        for date_block in date_blocks:
            year_tag = date_block.find('span', class_='year')
            day_month_tag = date_block.find('span', class_='day')

            current_year_str = clean_text(year_tag.text.replace('.', '')) if year_tag else str(
                datetime.date.today().year)
            day_month_str = clean_text(day_month_tag.text) if day_month_tag else None

            if not day_month_str:
                continue

            month_name_hun = None
            day_num_str = None

            day_month_parts = re.findall(r"([a-záéíóöőúüű]+|\d+)", day_month_str.lower())
            for part in day_month_parts:
                if part in MONTH_MAP_NSZ:
                    month_name_hun = part
                elif part.isdigit():
                    day_num_str = part

            if not month_name_hun or not day_num_str:
                continue

            month_num_str = MONTH_MAP_NSZ.get(month_name_hun)
            if not month_num_str:
                continue

            parsed_date_str = f"{current_year_str}-{month_num_str}-{day_num_str.zfill(2)}"

            play_lines = date_block.find_all('article', class_='play-line')
            if not play_lines:
                continue

            for play_element in play_lines:
                title_tag = play_element.find('div', class_='title')
                title_a_tag = title_tag.find('a') if title_tag else None
                title = clean_text(title_a_tag.text) if title_a_tag else None

                if not title:
                    continue

                hour_tag = play_element.find('em', class_='hour')
                min_tag = play_element.find('em', class_='min')
                parsed_time_str = "N/A"
                if hour_tag and min_tag:
                    hour = clean_text(hour_tag.text)
                    minute = clean_text(min_tag.text)
                    if hour and minute and hour.isdigit() and minute.isdigit():
                        parsed_time_str = f"{hour.zfill(2)}:{minute.zfill(2)}"

                venue_tag = play_element.find('span', class_='stage')
                venue = clean_text(venue_tag.text) if venue_tag else "Nemzeti Színház"

                subtitle_tag = play_element.find('h3', class_='subtitle')
                description = clean_text(subtitle_tag.text) if subtitle_tag else f"{title} a Nemzeti Színházban."

                buy_tickets_div = play_element.find('div', class_='buy-tickets-btn')
                link_tag = buy_tickets_div.find('a', href=True) if buy_tickets_div else None
                booking_url = get_absolute_url(BASE_URL, link_tag['href']) if link_tag else PROGRAM_URL

                price = None
                poster_url_tag = play_element.find('img', class_='play-line-img')  # Tipp a poszter képhez
                poster_url = get_absolute_url(BASE_URL,
                                              poster_url_tag['src']) if poster_url_tag and poster_url_tag.has_attr(
                    'src') else None

                unique_id_str = title + parsed_date_str + parsed_time_str + venue
                source_event_id = f"nsz_{re.sub(r'[^a-z0-9]', '', unique_id_str.lower())[:45]}_{int(pytime.time() * 1000000)}"

                events.append({
                    "source_event_id": source_event_id,
                    "title": title,
                    "type": "Színház",
                    "venue": venue,
                    "city": "Budapest",
                    "date": parsed_date_str,
                    "time": parsed_time_str,
                    "price": price,
                    "description": description,
                    "booking_url": booking_url,
                    "poster_url": poster_url,
                    "source": "Nemzeti Színház"
                })

    except requests.exceptions.Timeout:
        print(f"Hiba a Nemzeti Színház oldal letöltése közben: Időtúllépés ({PROGRAM_URL})")
    except requests.exceptions.RequestException as e:
        print(f"Hiba a Nemzeti Színház oldal letöltése közben: {e}")
    except Exception as e:
        print(
            f"Általános hiba a Nemzeti Színház scraping során: {e} (Sor: {e.__traceback__.tb_lineno if e.__traceback__ else 'N/A'})")

    if not events:
        print("Nemzeti Színház: Nem sikerült eseményeket kinyerni.")
    else:
        print(f"Nemzeti Színház: Összesen {len(events)} esemény gyűjtve.")
    return events


def scrape_egyeb_placeholder():
    print("Egyéb forrás scraper fut (placeholder)...")
    return []


if __name__ == '__main__':
    print("Scraperek teszt futtatása...")

    print("\n--- Cinema City Teszt (API) ---")
    cc_events = scrape_cinema_city()
    if cc_events:
        print(f"Cinema City (API): {len(cc_events)} esemény")
        for i, event in enumerate(cc_events[:3]):  # Csak az első néhányat írja ki
            print(
                f"  Film {i + 1}: {event.get('title')} @ {event.get('venue')} ({event.get('city')}) - {event.get('date')} {event.get('time')}, Poszter: {event.get('poster_url')}, URL: {event.get('booking_url')}")
    else:
        print("Cinema City (API): Nem tértek vissza események.")

    print("\n--- Nemzeti Színház Teszt ---")
    nsz_events = scrape_nemzeti_szinhaz()
    if nsz_events:
        print(f"Nemzeti Színház: {len(nsz_events)} esemény")
        for i, event in enumerate(nsz_events[:2]):
            print(
                f"  Előadás {i + 1}: {event.get('title')} - {event.get('date')} {event.get('time')}, Helyszín: {event.get('venue')}, Poszter: {event.get('poster_url')}, URL: {event.get('booking_url')}")
    else:
        print("Nemzeti Színház: Nem tértek vissza események.")
