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

    latest_tweet = api.user_timeline(id=api.me().id, count=1)[0]
    latest_package = latest_tweet.entities['urls'][0]['expanded_url']

    new_packages = [] 
    payload = {'sortBy': 'effectiveDate', 'count': 100}
    r = requests.get('https://www.unrealengine.com/marketplace/api/assets', params=payload)
    j  = r.json()
    for e in j['data']['elements']:
        new_packages.append(f"https://www.unrealengine.com/marketplace/en-US/product/{e['urlSlug']}")

    try:
        idx = new_packages.index(latest_package)
    except ValueError:
        api.destroy_status(latest_tweet.id)
        raise Exception(f"{latest_package} not in marketplace, deleting tweet")

    new_packages = new_packages[:idx]
    new_packages.reverse()
    for package in new_packages:
        log.info(package)
        api.update_status(f"#unreal #ue4 #marketplace {package}")


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
