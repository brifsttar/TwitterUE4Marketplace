from html.parser import HTMLParser
from time import sleep
import urllib.request
import logging as log

import tweepy

from tokens import *

LOG_FORMAT = '%(asctime)-15s [%(levelname)-8s]: %(message)s'
unreal_url = "https://www.unrealengine.com"


class MarketplaceParser(HTMLParser):

    def __init__(self):
        HTMLParser.__init__(self)
        self.packages = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            if len(attrs) != 2:
                return
            class_, name = attrs[0]
            href_, link = attrs[1]
            if class_ != 'class':
                return
            if "ellipsis-text" not in name:
                return
            if href_ != 'href':
                return
            if not link.startswith("/marketplace/en-US/product/"):
                return
            self.packages.append(unreal_url + link)


def check_for_new_packages():
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)

    latest_tweet = api.user_timeline(id=api.me().id, count=1)[0]
    latest_package = latest_tweet.entities['urls'][0]['expanded_url']

    parser = MarketplaceParser()

    marketplace_url = "{unreal_url}/marketplace/en-US/new-content?count=100".format(unreal_url=unreal_url)
    r = urllib.request.urlopen(marketplace_url)

    parser.feed(r.read().decode())
    try:
    idx = parser.packages.index(latest_package)
    except ValueError:
        api.destroy_status(latest_tweet.id)
        raise Exception(f"{latest_package} not in marketplace, deleting tweet")
    new_packages = parser.packages[:idx]
    new_packages.reverse()
    for package in new_packages:
        log.info(package)
        api.update_status(package)


def main():
    log.basicConfig(filename="twitter_marketplace.log", format=LOG_FORMAT, level=log.INFO)
    # log.basicConfig(format=LOG_FORMAT, level=log.INFO)
    while True:
        try:
            check_for_new_packages()
        except Exception as e:
            log.error(e)
        sleep(60)


if __name__ == '__main__':
    main()

