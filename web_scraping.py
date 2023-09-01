######################################################
#                       Imports
######################################################

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import jellyfish

from flask import Flask, render_template, request
import time

import yagmail
import os


service = Service('path')  # path to chromedriver for local machine

######################################################
#                 web scraping functions
######################################################

def clean_price_rtv(text):
    return float(text.split(" zł")[0].replace(' ', ''))

def clean_price_media(text):
    return float(text.replace('\u202f', ''))

# function below extracts the minimum price from prices lower than maximum price stated in the GUI
# the similarity ratio of offers and searched product has to be bigger than minimum ratio
# we are taking into account two highest ratios to avoid rejecting similar item (e.g. just different color) with lower price

def get_min_price(ratio_list, price_list, threshold, ratio_min):
    if len(ratio_list) > 0 and len(price_list) > 0:
        help_index = [index for index, item in enumerate(price_list) if item <= threshold]
        if help_index != []:
            index = [index for index, item in enumerate(ratio_list) if item >= sorted(ratio_list)[-2] and item > ratio_min and index in help_index]
            min_price = min([price_list[i] for i in index])
            return min_price

def get_driver(url):
    options = webdriver.ChromeOptions()
    options.add_argument("disable-infobars")
    options.add_argument("start-maximized")
    options.add_argument("disable-dev-shm-usage")
    options.add_argument("no-sandbox")
    options.add_argument("--headless=new")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(service=service, options=options)
    driver.get(url)
    return driver


def rtv_get_results(text, url, threshold):
    driver = get_driver(url)
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, 'onetrust-accept-btn-handler'))).click()

    search_bar = driver.find_element(By.XPATH,
                            '/html/body/ems-root/eui-root/eui-dropdown-host/div[2]/ems-euro-mobile/ems-euro-mobile-shared-feature-header-wrapper/ems-euro-mobile-shared-feature-header/div/ems-header/div[2]/div/div/div[2]/ems-euro-mobile-shared-feature-search-container/div/div/ems-search-input/ems-text-input/label/div/div/div[1]/input')

    search_bar.click()
    search_bar.send_keys(text + Keys.RETURN)

    expected = (By.CLASS_NAME, 'box-medium__link')
    WebDriverWait(driver, 10).until(EC.presence_of_element_located(expected))
    offers = driver.find_elements(By.CLASS_NAME, "box-medium__link")
    prices = driver.find_elements(By.CLASS_NAME, "price__value")

    offer_list = []
    ratio_list = []
    link_list = []

    for offer in offers:
        offer_list.append(offer.text)
        link_list.append(offer.get_attribute('href'))
        ratio_list.append(jellyfish.jaro_winkler_similarity(text, offer.text))

    price_list = []

    for price in prices:
        if not "," in price.text and not price.text == "":
            price_list.append(clean_price_rtv(price.text))

    min_price = get_min_price(ratio_list, price_list, threshold, 0.5)

    driver.quit()

    if offer_list == []:
        return "No offers found"
    else:
        if min_price:
            price_index = price_list.index(min_price)
            return offer_list[price_index], min_price, link_list[price_index]
        else:
            return "Prices too high"


def media_get_results(text, url, threshold):
    driver = get_driver(url)
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, 'onetrust-accept-btn-handler'))).click()

    search_bar = driver.find_element(By.XPATH,
                            '/html/body/div[1]/div[2]/header[2]/div[2]/div/div/div[2]/div/form/div[1]/input')

    search_bar.click()
    search_bar.send_keys(text + Keys.RETURN)

    expected = (By.CLASS_NAME, 'box')
    WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located(expected))
    time.sleep(2)

    offers = driver.find_elements(By.CLASS_NAME, "box")
    links = driver.find_elements(By.CSS_SELECTOR, "h2.name.is-section>a")
    prices = driver.find_elements(By.CLASS_NAME, "whole")

    offer_list = []
    ratio_list = []
    link_list = []

    for offer in offers:
        offer_list.append(offer.text)
        ratio_list.append(jellyfish.jaro_winkler_similarity(text, offer.text))

    for link in links:
        link_list.append(link.get_attribute("href"))

    price_list = []

    for price in prices:
        if not "," in price.text and not price.text == "":
            price_list.append(clean_price_media(price.text))

    min_price = get_min_price(ratio_list, price_list, threshold, 0.5)

    driver.quit()

    if offer_list == []:
        return "No offers found"
    else:
        if min_price:
            price_index = price_list.index(min_price)
            return offer_list[price_index], min_price, link_list[price_index]
        else:
            return "Prices too high"

######################################################
#                 email sending functions
######################################################


def results_to_html_list(webpage, input):
    if type(input) != str:
        my_string = """<li><b>Web store: {0} </b><br>
        Offer: {1} <br>
        Price: {2} <br>
        Link: {3}</li>
        """.format(webpage, input[0], input[1], input[2])
        return my_string
    else:
        my_string = """<li><b>Web store: {0} </b><br>
        Offer: No results to show</li>""".format(webpage)
        return my_string


def send_email(sender, receiver, subject, results_list):

    email_list = []

    for result in results_list:
        email_list.append(results_to_html_list(result[0], result[1]))

    contents = """
    <p>Hi!<br>
    Below please find the results of your search:</p>
    <ul>
    {0}
    </ul>
    <p>KR,<br>
    Your Python code</p>
    """.format('<br>'.join(email_list))

    yag = yagmail.SMTP(user=sender, password=os.getenv('secret_key'))
    yag.send(to=receiver, subject=subject, contents=contents)


######################################################
#                    Flask app
######################################################

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('./index.html',
                           status=" hidden",
                           results_rtv=(str(), str(), str()),
                           results_media=(str(), str(), str()),)


@app.route('/', methods=['POST'])
def home_post():

    price = float(request.form['price-name'])
    email = str(request.form['email-name'])
    product = str(request.form['product-name'])

    results_rtv = rtv_get_results(product, "https://www.euro.com.pl/", price)
    results_media = media_get_results(product, "https://www.mediaexpert.pl/", price)

    if type(results_rtv) == str and type(results_media) == str:
        final_text = "No results to send via email."
    else:
        final_text = "The results were also sent to the provided email."
        results_list = [["RTV EURO AGD", results_rtv], ["Media Expert", results_media]]
        send_email('sender email', email, "RTV product finder results", results_list)

    if type(results_rtv) == str:
        results_rtv = (results_rtv, str(), str())

    if type(results_media) == str:
        results_media = (results_media, str(), str())

    return render_template('index.html',
                           status=" ",
                           price_max=price,
                           product=product,
                           email=email,
                           final_text=final_text,
                           results_rtv=results_rtv,
                           results_media=results_media)


app.run(host='0.0.0.0')
