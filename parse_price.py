import requests
from concurrent.futures import ThreadPoolExecutor, as_completed


def fetch_details(spuId):
    detail_url = f"https://poizonshop.ru/api/catalog/product/{spuId}"
    detail_response = requests.get(detail_url)

    if detail_response.status_code == 200:
        detail_data = detail_response.json()

        sizes_prices = {}

        for sku in detail_data['skus']:
            size = float(sku['size']['ru'])
            price = sku['priceV2']['price']
            if price != 0:
                sizes_prices[size] = price

        sorted_sizes_prices = dict(sorted(sizes_prices.items()))
        return sorted_sizes_prices
    else:
        return None


def fetch_page(page_num, name):
    base_url = f"https://poizonshop.ru/api/catalog/product?search={str(name)}&page={page_num}"
    response = requests.get(base_url)

    if response.status_code == 200:
        data = response.json()

        for item in data['items']:
            if item['name'] == str(name):
                return item['spuId']
    return None


def parse_price(name):
    with ThreadPoolExecutor(max_workers=102) as executor:
        future_to_page = {executor.submit(fetch_page, i, name): i for i in range(1, 10)}

        for future in as_completed(future_to_page):
            spuId = future.result()
            if spuId:
                sizes_prices = fetch_details(spuId)
                if sizes_prices:
                    return sizes_prices

    return False
