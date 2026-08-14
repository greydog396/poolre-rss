import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

BASE_URL = "https://www.poolre.co.uk/threat-publications/"
SITE_URL = "https://www.poolre.co.uk"
OUTPUT_FILE = "feed.xml"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PoolReRSS/1.0)"
}


def get_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return BeautifulSoup(response.text, "html.parser")


def parse_date(date_text):
    date_text = date_text.strip()

    dt = datetime.strptime(
        date_text,
        "%d %B, %Y"
    )

    return dt.replace(tzinfo=timezone.utc)


def get_article_image(url):
    """
    Get the featured image from the individual Pool Re article.
    Pool Re exposes the featured image through og:image.
    """

    try:
        soup = get_page(url)

        # Primary method: Open Graph image
        og_image = soup.find(
            "meta",
            property="og:image"
        )

        if og_image and og_image.get("content"):
            image_url = og_image["content"].strip()

            if image_url.startswith("/"):
                image_url = SITE_URL + image_url

            return image_url

        # Fallback: Twitter image
        twitter_image = soup.find(
            "meta",
            attrs={"name": "twitter:image"}
        )

        if twitter_image and twitter_image.get("content"):
            image_url = twitter_image["content"].strip()

            if image_url.startswith("/"):
                image_url = SITE_URL + image_url

            return image_url

    except Exception as error:
        print(
            f"Could not get image for {url}: {error}"
        )

    return None


def scrape_publications():

    publications = []

    # Current Pool Re archive has multiple pages.
    # Check the first 10 so the scraper continues
    # working if more archive pages appear.
    for page_number in range(1, 11):

        if page_number == 1:
            url = BASE_URL
        else:
            url = (
                f"{BASE_URL}"
                f"?query-3-page={page_number}"
            )

        print(
            f"Scraping publication page {page_number}..."
        )

        try:
            soup = get_page(url)
        except Exception as error:
            print(
                f"Could not scrape page {page_number}: "
                f"{error}"
            )
            continue

        headings = soup.find_all(
            ["h2", "h3"]
        )

        for heading in headings:

            link = heading.find(
                "a",
                href=True
            )

            if not link:
                continue

            title = link.get_text(
                " ",
                strip=True
            )

            article_url = link["href"]

            if (
                "/terrorism-threat-publications/"
                not in article_url
            ):
                continue

            if article_url.startswith("/"):
                article_url = (
                    SITE_URL + article_url
                )

            # Find publication date
            date_text = None

            for element in heading.find_all_next(
                limit=8
            ):

                text = element.get_text(
                    " ",
                    strip=True
                )

                if not text:
                    continue

                if any(
                    month in text
                    for month in [
                        "January",
                        "February",
                        "March",
                        "April",
                        "May",
                        "June",
                        "July",
                        "August",
                        "September",
                        "October",
                        "November",
                        "December"
                    ]
                ):

                    try:
                        parse_date(text)
                        date_text = text
                        break

                    except ValueError:
                        pass

            if not date_text:
                continue

            try:
                publication_date = parse_date(
                    date_text
                )

            except ValueError:
                continue

            # Avoid duplicates
            if any(
                item["url"] == article_url
                for item in publications
            ):
                continue

            print(
                f"Found: {title}"
            )

            # Get featured image
            image_url = get_article_image(
                article_url
            )

            if image_url:
                print(
                    f"  Image: {image_url}"
                )
            else:
                print(
                    "  Image: none"
                )

            publications.append({
                "title": title,
                "url": article_url,
                "date": publication_date,
                "image": image_url
            })

    # Newest first
    publications.sort(
        key=lambda item: item["date"],
        reverse=True
    )

    return publications


def create_rss(publications):

    now = format_datetime(
        datetime.now(timezone.utc)
    )

    items = []

    for publication in publications:

        title = escape(
            publication["title"]
        )

        url = escape(
            publication["url"]
        )

        pub_date = format_datetime(
            publication["date"]
        )

        image = publication.get(
            "image"
        )

        image_xml = ""

        if image:

            image = escape(
                image,
                {'"': "&quot;"}
            )

            image_xml = f"""
            <enclosure
                url="{image}"
                length="0"
                type="image/jpeg"
            />

            <media:content
                url="{image}"
                medium="image"
                type="image/jpeg"
            />
            """

        items.append(
            f"""
        <item>
            <title>{title}</title>

            <link>{url}</link>

            <guid isPermaLink="true">
                {url}
            </guid>

            <pubDate>{pub_date}</pubDate>

            <description>
                {title}
            </description>

            {image_xml}

        </item>
        """
        )

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>

<rss
    version="2.0"
    xmlns:media="http://search.yahoo.com/mrss/"
>

    <channel>

        <title>
            Pool Re Threat Publications
        </title>

        <link>
            {BASE_URL}
        </link>

        <description>
            Latest threat publications from Pool Re
        </description>

        <language>
            en-gb
        </language>

        <lastBuildDate>
            {now}
        </lastBuildDate>

        <ttl>
            60
        </ttl>

        {''.join(items)}

    </channel>

</rss>
"""

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(rss)


def main():

    publications = scrape_publications()

    print(
        f"Found {len(publications)} publications."
    )

    if not publications:

        raise RuntimeError(
            "No publications were found. "
            "The Pool Re website structure "
            "may have changed."
        )

    create_rss(
        publications
    )

    print(
        f"RSS feed written to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
