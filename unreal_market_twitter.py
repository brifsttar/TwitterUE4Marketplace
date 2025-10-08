import logging as log
from collections import deque
import pickle
from json.decoder import JSONDecodeError
import re

from discord_webhook import DiscordWebhook
from curl_cffi import requests

from tokens import *


def send_discord(product):
    url = WEBHOOK_URL_ALL
    asset_url = f"https://www.fab.com/listings/{product['uid']}"
    asset_name = product['title']
    try:
        asset_category = product['category']['path']
        asset_category = "/".join([x.capitalize() for x in re.split('-|/', asset_category)])
    except (IndexError, KeyError):
        asset_category = "???"
    msg = []

    is_free = product['isFree'] or product['startingPrice']['price'] == 0.

    if is_free:
        url = WEBHOOK_URL_FREE
    msg.append(f"{asset_name} ({asset_category})")

    if 'music' in asset_category.lower():
        return
    # Hide default link card?
    no_card = False
    # "Music" category
    no_card |= 'music' in asset_category.lower()

    # Use of "<url>" to hide default card
    msg.append(f"<{asset_url}>")

    msg_txt = "\n".join(msg)
    log.info(f"Sending {msg_txt} to Discord")
    webhook = DiscordWebhook(url=url, content=msg_txt)
    if not no_card:
        image_url = product['thumbnails'][0]['mediaUrl']
        img = requests.get(image_url, impersonate="chrome101")
        webhook.add_file(file=img.content, filename="featured.png")
    webhook.execute()


def send_all(product):
    send_discord(product)


class UnrealMarketBot:

    LATEST_PRODUCT_FILE = 'latest.pickle'
    FREE_PRODUCT_FILE = 'free.pickle'
    DEQUEUE_LEN = 20
    PRODUCT_REQ_COUNT = 100

    def __init__(self):
        # Circular buffer with the latest known products, used to check Marketplace API and discover new releases
        self.latests = None
        self.freebies = []

    def _pickled(func):
        """Decorator to load/dump pickle data around a function call"""
        def inner(self):
            try:
                with open(self.LATEST_PRODUCT_FILE, 'rb') as f:
                    self.latests = pickle.load(f)
            except FileNotFoundError:
                log.warning(f"{self.LATEST_PRODUCT_FILE} not found, initializing empty list")
                self.latests = deque(maxlen=self.DEQUEUE_LEN)
            func(self)
            with open(self.LATEST_PRODUCT_FILE, 'wb') as f:
                pickle.dump(self.latests, f, pickle.HIGHEST_PROTOCOL)
        return inner

    @_pickled
    def check_for_new_products(self):
        log.debug("Checking for new products")

        # Requesting the Marketplace API for latest products
        payload = {
            'channels': 'unreal-engine',
            'is_ai_generated': 0,
            'sort_by': '-firstPublishedAt',
            'currency': 'USD',
        }
        r = requests.get('https://www.fab.com/i/listings/search', params=payload, impersonate="chrome101")
        if r.status_code != 200:
            log.error(f"Failed to fetch Marketplace, error {r.status_code}")
            return
        try:
            j = r.json()
        except JSONDecodeError as e:
            log.info(r.content)
            log.info(r.status_code)
            log.info(r.headers)
            log.exception(e)
            return

        products_new = j['results']

        if len(products_new) == 0:
            raise Exception(f"Failed to fetch new products")

        if len(self.latests) == 0:
            # Initializing on first run
            [self.latests.appendleft(x) for x in reversed(products_new)]

        # Finding the last known product in the list of new products
        idx = 0
        while idx < self.DEQUEUE_LEN:
            try:
                latest = self.latests[idx]
                for i, item in enumerate(products_new):
                    if latest['uid'] == item['uid']:
                        idx = i
                        break
                else:
                    idx += 1
                    log.info(f"{latest} not in marketplace anymore, skipping")
            except IndexError:
                log.error(
                    f"Of all {self.DEQUEUE_LEN} latest known products, "
                    f"none could be found in the {self.PRODUCT_REQ_COUNT} most recent products on the Marketplace"
                )
                self.latests.clear()
                return
            else:
                break

        products_new = products_new[:idx]
        products_new.reverse()
        for product in products_new:
            send_all(product)
            self.latests.appendleft(product)

    def check_free_limited_time(self):
        log.debug("Checking for new free for limited time products")
        try:
            with open(self.FREE_PRODUCT_FILE, 'rb') as f:
                self.freebies = pickle.load(f)
        except FileNotFoundError:
            log.warning(f"{self.FREE_PRODUCT_FILE} not found, initializing empty list")

        r = requests.get('https://www.fab.com/i/blades/free_content_blade', impersonate="chrome101")
        if r.status_code != 200:
            log.error(f"Failed to fetch Marketplace, error {r.status_code}")
            return
        try:
            j = r.json()
        except JSONDecodeError as e:
            log.info(r.content)
            log.info(r.status_code)
            log.info(r.headers)
            log.exception(e)
            return

        products = j['tiles']
        for product in products:
            if product['uid'] in self.freebies:
                continue
            listing = product['listing']
            msg = f"# **⏱️ {j['title']}**\n## {listing['title']}\nhttps://www.fab.com/listings/{product['uid']}"
            log.info(f"Sending {msg.encode('ascii', 'ignore')} to Discord")
            webhook = DiscordWebhook(url=WEBHOOK_URL_FREE, content=msg)
            image_url = listing['thumbnails'][0]['mediaUrl']
            img = requests.get(image_url, impersonate="chrome101")
            webhook.add_file(file=img.content, filename="featured.png")
            webhook.execute()

        self.freebies = [p['uid'] for p in products]
        with open(self.FREE_PRODUCT_FILE, 'wb') as f:
            pickle.dump(self.freebies, f, pickle.HIGHEST_PROTOCOL)


def main():
    log.basicConfig(
        filename="unreal_market.log",
        format='%(asctime)-15s [%(levelname)-8s]: %(message)s',
        level=log.INFO
    )
    try:
        u = UnrealMarketBot()
        u.check_for_new_products()
        u.check_free_limited_time()
    except Exception as e:
        log.exception(e)


if __name__ == '__main__':
    main()
