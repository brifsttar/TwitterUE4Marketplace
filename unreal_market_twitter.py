import logging as log
from collections import deque
import pickle

import tls_client
import tweepy
import requests
from discord_webhook import DiscordWebhook

from tokens import *


def send_twitter(product):
    if 26732 in product['tags']:
        # Filter out "CreatedWithAI" for Twitter
        return

    asset_url = f"https://www.unrealengine.com/marketplace/en-US/product/{product['urlSlug']}"
    asset_name = product['title']
    try:
        asset_category = product['categories'][0]['name']
    except (IndexError, KeyError):
        asset_category = "???"
    msg = []

    if product['priceValue'] == 0:
        # Some products are tagged as free, but they're really external products
        is_ext_prod = (attr := product.get("customAttributes", None)) and 'BuyLink' in attr
        if not is_ext_prod:
            msg.append("FREE new content!")
    msg.append(f"{asset_name} ({asset_category})")
    msg.append("#UnrealEngine #UE5")
    msg.append(asset_url)
    msg_txt = "\n".join(msg)

    client = tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )

    log.info(f"Sending {msg_txt} to Twitter")
    try:
        client.create_tweet(text=msg_txt)
    except tweepy.errors.HTTPException as e:
        log.error(e)
        log.error(e.response.headers)
        log.error(e.response.content.decode())


def send_discord(product):
    asset_url = f"https://www.unrealengine.com/marketplace/en-US/product/{product['urlSlug']}"
    asset_name = product['title']
    try:
        asset_category = product['categories'][0]['name']
    except (IndexError, KeyError):
        asset_category = "???"
    msg = []

    if product['priceValue'] == 0:
        # Some products are tagged as free, but they're really external products
        is_ext_prod = (attr := product.get("customAttributes", None)) and 'BuyLink' in attr
        if not is_ext_prod:
            msg.append("FREE new content!")
    msg.append(f"{asset_name} ({asset_category})")
    msg.append(asset_url)

    msg_txt = "\n".join(msg)
    log.info(f"Sending {msg} to Discord")
    webhook = DiscordWebhook(url=WEBHOOK_URL, content=msg_txt)
    if 26732 not in product['tags']:
        image_url = product['featured']
        img = requests.get(image_url, stream=True)
        webhook.add_file(file=img.raw, filename="featured.png")
    webhook.execute()


def send_all(product):
    send_discord(product)
    send_twitter(product)


class UnrealMarketBot:

    LATEST_PRODUCT_FILE = 'latest.pickle'
    DEQUEUE_LEN = 20
    PRODUCT_REQ_COUNT = 100

    def __int__(self):
        # Circular buffer with the latest known products, used to check Marketplace API and discover new releases
        self.latests = None

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
            'sortBy': 'effectiveDate',
            'count': self.PRODUCT_REQ_COUNT,
            # NoAI tag
            # Not using it at the moment because it's not widely used yet
            # 'tag[]': '26645'
        }
        session = tls_client.Session(client_identifier="chrome112", random_tls_extension_order=True)
        r = session.get('https://www.unrealengine.com/marketplace/api/assets', params=payload)
        j = r.json()

        products_new = j['data']['elements']

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
                    if latest['id'] == item['id']:
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


def main():
    log.basicConfig(
        filename="unreal_market.log",
        format='%(asctime)-15s [%(levelname)-8s]: %(message)s',
        level=log.INFO
    )
    try:
        u = UnrealMarketBot()
        u.check_for_new_products()
    except Exception as e:
        log.error(e)


if __name__ == '__main__':
    main()
