import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from calculate_discounted_price import calculate_discounted_price


def fetch_details(spuId, parse_min_price):
    detail_url = f"https://poizonshop.ru/api/catalog/product/{spuId}"
    detail_response = requests.get(detail_url)

    if detail_response.status_code == 200:
        detail_data = detail_response.json()

        sizes_prices = {}

        for sku in detail_data['skus']:
            try:
                size = float(sku['size']['ru'])
            except Exception:
                continue

            price = sku['priceV2']['price']
            if price != 0:
                sizes_prices[size] = calculate_discounted_price(float(price), 6)

        sorted_sizes_prices = dict(sorted(sizes_prices.items()))
        if sorted_sizes_prices:
            min_price = min(sorted_sizes_prices.values())
            if min_price == calculate_discounted_price(float(parse_min_price), 6):
                return sorted_sizes_prices
    return None


def fetch_page(page_num, name):
    base_url = f"https://poizonshop.ru/api/catalog/product?search={str(name)}&page={page_num}"
    response = requests.get(base_url)

    if response.status_code == 200:
        data = response.json()
        spuIds = []

        for item in data['items']:
            if item['name'] == str(name):
                spuIds.append(item['spuId'])
        return spuIds
    return []


def parse_price(name, parse_min_price):
    with ThreadPoolExecutor(max_workers=102) as executor:
        future_to_page = {executor.submit(fetch_page, i, name): i for i in range(1, 102)}

        for future in as_completed(future_to_page):
            spuIds = future.result()
            for spuId in spuIds:
                sizes_prices = fetch_details(spuId, parse_min_price)
                if sizes_prices:
                    return sizes_prices

    return None
