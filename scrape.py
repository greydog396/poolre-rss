import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

BASE_URL = "https://www.poolre.co.uk/threat-publications/"
OUTPUT_FILE = "feed.xml"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PoolReRSS/1.0)"
}


def get_page(page):
    if page == 1:
        url = BASE_URL
    else:
        url = f"{BASE_URL}?query-3-page={page}"

    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    return BeautifulSoup(response.text, "html.parser")


def parse_date(date_text):
    """
    Convert Pool Re dates such as:
    '13 August, 2026'
    into an RFC-822 date suitable for RSS.
    """
    date_text = date_text.strip()

    dt = datetime.strptime(date_text, "%d %B, %Y")

    return dt.replace(tzinfo=timezone.utc)


def scrape_publications():
    publications = []

    # Pool Re currently has six pages.
    # Scraping all pages means older publications remain in the feed.
    for page_number in range(1, 7):

        print(f"Scraping page {page_number}...")

        soup = get_page(page_number)

        # Each publication is represented by a heading containing
        # a link to the individual publication.
        headings = soup.find_all(["h2", "h3"])

        for heading in headings:

            link = heading.find("a", href=True)

            if not link:
                continue

            title = link.get_text(" ", strip=True)
            url = link["href"]

            # Only keep Pool Re publication links.
            if "/terrorism-threat-publications/" not in url:
                continue

            # Make relative URLs absolute.
            if url.startswith("/"):
                url = "https://www.poolre.co.uk" + url

            # Find the date following the heading.
            date_text = None

            for element in heading.find_all_next(limit=5):

                text = element.get_text(" ", strip=True)

                if text and any(month in text for month in [
                    "January", "February", "March", "April",
                    "May", "June", "July", "August",
                    "September", "October", "November", "December"
                ]):
                    try:
                        parse_date(text)
                        date_text = text
                        break
                    except ValueError:
                        pass

            if not date_text:
                continue

            try:
                publication_date = parse_date(date_text)
            except ValueError:
                continue

            # Avoid duplicates.
            if any(item["url"] == url for item in publications):
                continue

            publications.append({
                "title": title,
                "url": url,
                "date": publication_date
            })

    # Newest first.
    publications.sort(
        key=lambda item: item["date"],
        reverse=True
    )

    return publications


def create_rss(publications):

    now = format_datetime(datetime.now(timezone.utc))

    items = []

    for publication in publications:

        title = escape(publication["title"])
        url = escape(publication["url"])

        pub_date = format_datetime(publication["date"])

        items.append(f"""
        <item>
            <title>{title}</title>
            <link>{url}</link>
            <guid isPermaLink="true">{url}</guid>
            <pubDate>{pub_date}</pubDate>
            <description>{title}</description>
        </item>
        """)

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Pool Re Threat Publications</title>
        <link>{BASE_URL}</link>
        <description>Latest threat publications from Pool Re</description>
        <language>en-gb</language>
        <lastBuildDate>{now}</lastBuildDate>
        <ttl>1440</ttl>
        {''.join(items)}
    </channel>
</rss>
"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write(rss)


def main():
    publications = scrape_publications()

    print(f"Found {len(publications)} publications.")

    if not publications:
        raise RuntimeError(
            "No publications were found. "
            "The Pool Re website structure may have changed."
        )

    create_rss(publications)

    print(f"RSS feed written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
