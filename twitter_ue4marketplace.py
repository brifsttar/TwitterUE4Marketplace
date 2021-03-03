from time import sleep
import logging as log

import requests
import tweepy

from tokens import *

LOG_FORMAT = '%(asctime)-15s [%(levelname)-8s]: %(message)s'


def check_for_new_packages():
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)

    tweets = api.user_timeline(id=api.me().id)
    for tweet in tweets:
        if tweet.source:
            # Sometimes I manually retweet stuff, so I filter out those by checking tweet source
            # (bot tweets have none)
            continue
        latest_package = tweet.entities['urls'][0]['expanded_url']
        break
    else:
        raise Exception(f"Couldn't find any packages in timeline")

    new_packages = []
    free_packages = []
    payload = {'sortBy': 'effectiveDate', 'count': 100}
    r = requests.get('https://www.unrealengine.com/marketplace/api/assets', params=payload)
    j  = r.json()
    
    for e in j['data']['elements']:
        asset_url = f"https://www.unrealengine.com/marketplace/en-US/product/{e['urlSlug']}"
        new_packages.append(asset_url)
        if e['priceValue'] == 0:
            if (attr := e.get("customAttributes", None)) and 'BuyLink' in attr:
                # Some products are tagged as free, but they're really external products
                continue
            free_packages.append(asset_url)

    try:
        idx = new_packages.index(latest_package)
    except ValueError:
        api.destroy_status(tweet.id)
        raise Exception(f"{latest_package} not in marketplace anymore, deleting tweet")

    new_packages = new_packages[:idx]
    new_packages.reverse()
    for package in new_packages:
        log.info(package)
        msg = ""
        if package in free_packages:
            msg += "FREE new content! "
        msg += f"#unreal #ue4 #marketplace {package}"
        api.update_status(msg)


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
