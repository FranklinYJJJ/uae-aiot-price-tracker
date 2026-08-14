#!/usr/bin/env python3
"""
Xiaomi AIoT UAE - Amazon.ae Price Scraper
Scrapes current prices for tracked products and updates index.html
"""

import json
import re
import time
import random
import os
from datetime import datetime, timezone, timedelta

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.check_call(['pip', 'install', 'requests', 'beautifulsoup4', '-q'])
    import requests
    from bs4 import BeautifulSoup

# ── Config ──────────────────────────────────────────────────────────────────
UAE_TZ = timezone(timedelta(hours=4))
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
}
HTML_PATH = os.path.join(os.path.dirname(__file__), '..', 'index.html')


def extract_asins_from_html(html_content):
    """Extract ASIN list from existing index.html"""
    match = re.search(r'const ALL_PRODUCTS = (\[.*?\]);\s*\n', html_content, re.DOTALL)
    if not match:
        raise ValueError("Could not find ALL_PRODUCTS in index.html")
    return json.loads(match.group(1))


def scrape_product(asin, session):
    """Scrape a single product from Amazon.ae"""
    url = f'https://www.amazon.ae/dp/{asin}'
    try:
        resp = session.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 503:
            print(f'  ⚠️  {asin}: Bot detection (503), skipping')
            return None
        if resp.status_code != 200:
            print(f'  ⚠️  {asin}: HTTP {resp.status_code}')
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')
        result = {}

        # Price - try multiple selectors
        price_el = soup.select_one('span.a-price span.a-offscreen')
        if not price_el:
            price_el = soup.select_one('#priceblock_ourprice')
        if not price_el:
            price_el = soup.select_one('#priceblock_dealprice')
        if not price_el:
            price_el = soup.select_one('span.priceToPay span.a-offscreen')
        if price_el:
            price_text = price_el.get_text(strip=True)
            price_num = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
            if price_num:
                result['lowest_price'] = float(price_num.group())

        # Seller
        seller_el = soup.select_one('#merchant-info') or soup.select_one('#sellerProfileTriggerId')
        if seller_el:
            result['seller'] = seller_el.get_text(strip=True)[:50]
        if not result.get('seller'):
            # Try tabularbuybox
            seller_el2 = soup.select_one('#tabular-buybox-truncate-1 span.tabular-buybox-text')
            if seller_el2:
                result['seller'] = seller_el2.get_text(strip=True)[:50]

        # Rating
        rating_el = soup.select_one('#acrPopover span.a-size-base')
        if rating_el:
            try:
                result['rating'] = float(rating_el.get_text(strip=True))
            except ValueError:
                pass

        # Review count
        review_el = soup.select_one('#acrCustomerReviewText')
        if review_el:
            review_text = review_el.get_text(strip=True).replace(',', '')
            review_num = re.search(r'\d+', review_text)
            if review_num:
                result['review_count'] = int(review_num.group())

        return result if result.get('lowest_price') else None

    except Exception as e:
        print(f'  ❌  {asin}: {e}')
        return None


def update_html(html_content, products):
    """Replace ALL_PRODUCTS in index.html with updated data"""
    new_json = json.dumps(products, ensure_ascii=False, indent=0)
    pattern = r'const ALL_PRODUCTS = \[.*?\];\s*\n'
    replacement = f'const ALL_PRODUCTS = {new_json};\n'
    return re.sub(pattern, replacement, html_content, flags=re.DOTALL)


def main():
    print(f'🦞 Xiaomi AIoT UAE Price Scraper')
    print(f'   {datetime.now(UAE_TZ).strftime("%Y-%m-%d %H:%M UAE time")}')
    print(f'   Reading {HTML_PATH}')

    with open(HTML_PATH, 'r', encoding='utf-8') as f:
        html_content = f.read()

    products = extract_asins_from_html(html_content)
    print(f'   Found {len(products)} products to scrape\n')

    session = requests.Session()
    updated = 0
    failed = 0

    for i, product in enumerate(products):
        asin = product['asin']
        name = product.get('product_name', asin)[:50]
        print(f'[{i+1}/{len(products)}] {name}...')

        result = scrape_product(asin, session)
        if result:
            if result.get('lowest_price'):
                product['lowest_price'] = result['lowest_price']
            if result.get('seller'):
                product['seller'] = result['seller']
            if result.get('rating'):
                product['rating'] = result['rating']
            if result.get('review_count') is not None:
                product['review_count'] = result['review_count']
            product['last_updated'] = datetime.now(UAE_TZ).strftime('%Y-%m-%d %H:%M')
            updated += 1
            price = result.get('lowest_price', '?')
            print(f'  ✅ AED {price}')
        else:
            failed += 1
            print(f'  ❌ Failed')

        # Random delay to avoid bot detection
        time.sleep(random.uniform(2, 5))

    # Update timestamp
    now_str = datetime.now(UAE_TZ).strftime('%Y-%m-%d %H:%M')
    html_content = update_html(html_content, products)

    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f'\n📊 Summary:')
    print(f'   ✅ Updated: {updated}')
    print(f'   ❌ Failed:  {failed}')
    print(f'   📄 Saved to {HTML_PATH}')
    print(f'   🕐 {now_str} UAE time')


if __name__ == '__main__':
    main()
