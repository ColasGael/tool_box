import os
import re

import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service


browser = webdriver.Chrome(service=Service("/home/colasg/Downloads/chromedriver-linux64/chromedriver"))

browser.get("https://myradiologyconnectportal.com/")

input("Please login and press enter to continue...")

image_urls = [
    "https://myradiologyconnectportal.com/" + image[:-8].replace("QuickView", "Image") + "/Large?Frame=1"
    for image in re.findall(r"/PACS.*frame=1", browser.page_source)
]

outdir = '/home/colasg/Downloads/images'
os.makedirs(outdir, exist_ok=True)

s = requests.session()

for cookie in browser.get_cookies():
    c = {cookie['name']: cookie['value']}
    s.cookies.update(c)

for i, img_url in enumerate(image_urls):
    r = s.get(img_url)
    img_path = os.path.join(outdir, f'20250108_mri_right-hip_{i}.jpg')
    if r.status_code == 200:
        with open(img_path, 'wb') as f:
            f.write(r.content)
        print(f"Downloaded image from {img_url} to {img_path}")
    else:
        print(f"Failed to download image from {img_url}")

