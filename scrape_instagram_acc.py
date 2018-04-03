import datetime as dt
import json
import os
import pandas as pd
import re
import requests
import StringIO
import time
import urllib

from selenium import webdriver
from bs4 import BeautifulSoup
from selenium.webdriver.common.action_chains import ActionChains

def convert_metrics (string):
    value = float(re.sub('[^0-9\.]', '', string))
    if 'k' in string: value = value * 1000
    if 'm' in string: value = value * 1000000
    return int(value)

def scrape_instagram_photo_ids(insta_handle):
    browser = webdriver.Chrome()
    browser.get("https://www.instagram.com/{}/".format(insta_handle))
    soup = BeautifulSoup(browser.page_source, "html.parser")

    #path to posts changes, may break in the future
    postsT = soup.html.body.span.section.main.article.header.section.ul.find_all('li', recursive=False)[0].span.find_all('span', recursive=False)[0].getText()
    posts =  convert_metrics(postsT)
    print '{} posts'.format(posts)

    photo_ids = []

    # scrapes image urls from a dynamically loaded page based on scroll location
    if posts > 12:
        for i in range (0, ((posts-12)//12)+1):
            browser.execute_script('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(0.5)

            soup = BeautifulSoup(browser.page_source, 'html.parser')
            for link in soup.html.body.span.section.main.article.findAll('a'):
                if link.get('href')[:3] == '/p/':
                    photo_ids.append(link.get('href').split("/")[2])

            browser.execute_script('window.scrollTo(0, 0)')
            time.sleep(0.5)
    else:
        soup = BeautifulSoup(browser.page_source, 'html.parser')
        for link in soup.html.body.span.section.main.article.findAll('a'):
            if link.get('href')[:3] == '/p/':
                photo_ids.append(link.get('href').split("/")[2])

    photo_ids = list(set(photo_ids)) #removes possible duplicate photo ids
    time.sleep(1)
    browser.quit()
    print 'returned {} photo ids'.format(len(photo_ids))
    return photo_ids

def gather_photo_data(photo_ids_list):

    datalist = []
    for photo_id in photo_ids_list:
        html_text = requests.get("http://www.instagram.com/p/" + photo_id).text
        soup = BeautifulSoup(html_text, "html.parser")
        window_sharedData = soup.find_all(string = re.compile("window._sharedData"))[0].decode("utf-8")

        #path to post data changes, may break in the future
        data = json.loads(re.sub('window._sharedData = ', '', window_sharedData[:-1]))['entry_data']['PostPage'][0]['graphql']['shortcode_media']

        print photo_id
        date_posted = str(dt.datetime.fromtimestamp(data['taken_at_timestamp']))

        if (len(data['edge_media_to_caption']['edges']) != 0):
            caption = data['edge_media_to_caption']['edges'][0]['node']['text']
        else:
            caption = ''

        likes = data['edge_media_preview_like']['count']
        comments = data['edge_media_to_comment']['count']
        display_url = data['display_url']
        is_video = data['is_video']

        datalist.append([photo_id, date_posted, caption, likes, comments, display_url, is_video])

    df = pd.DataFrame(datalist, columns = ['photo_id', 'date_posted', 'caption', 'comments', 'likes', 'photo_src', 'is_video'])
    df.sort_values('date_posted', ascending = False, inplace = True) #ordering lost when making the photo_ids into a set
    df.reset_index(inplace = True, drop = True)
    return df

def download_and_store_data(insta_handle, photo_df):
    if not os.path.exists('inst_account/{}'.format(insta_handle)):
        os.makedirs('inst_account/{}'.format(insta_handle))

    photo_df.to_csv('inst_account/{}/photo_metrics.csv'.format(insta_handle), index = False, encoding = 'utf-8')

    for index, row in photo_df.iterrows():
        try:
            print 'downloading {} at url {}'.format(row['photo_id'], row['photo_src'])
            urllib.urlretrieve(row['photo_src'], "inst_account/{}/{}.jpg".format(insta_handle, row['photo_id']))
        except:
            print 'failed to download image'

def main():
    insta_handle = raw_input("Enter the handle of a public Instagram account:\n").lower()
    photo_ids_list = scrape_instagram_photo_ids(insta_handle)
    photo_metrics = gather_photo_data(photo_ids_list)
    download_and_store_data(insta_handle, photo_metrics)

if __name__ == '__main__':
    main()
