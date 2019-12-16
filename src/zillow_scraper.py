#!/usr/bin/env python 

import datetime
import gspread
import json
import os
import random
import time
import unicodecsv as csv
from lxml import html
from oauth2client.service_account import ServiceAccountCredentials
from tqdm import tqdm

from properties import ZillowPropertyHtml, ZillowPropertyJson
from urls import ZILLOW_URL
from util import clean
from util import get_response, get_headers

CREDENTIALS = os.path.expanduser('~/.creds.json')

def maybe_get_xml_results(parser):
    xml_results = parser.xpath('//article[@class="list-card list-card-short list-card_not-saved"]')
    string_results = parser.xpath('//li/script[@type="application/ld+json"]//text()')
    json_results = []
    for result in string_results:
        json_result = json.loads(result)
        if json_result['@type'] == 'SingleFamilyResidence':
            json_results.append(json_result)

    search_results = zip(xml_results, json_results)
    properties = []
    for xml_result, json_result in search_results:
        properties.append(ZillowPropertyHtml(xml_result, json_result))
    return properties

def maybe_get_json_results(parser):
    raw_json = parser.xpath('//script[@data-zrr-shared-data-key="mobileSearchPageStore"]//text()')
    cleaned_data = clean(raw_json).replace('<!--', "").replace("-->", "")
    json_data = json.loads(cleaned_data)
    search_results = json_data.get('searchResults').get('listResults', [])
    properties = []
    for result in search_results:
        properties.append(ZillowPropertyJson(result))
    return properties
    
class ZillowHtmlDownloader(object):
    """ Class that downloads zillow zip code searches for scraping """
    
    def __init__(self, tor, zip_code):
        self.zip_code = zip_code
        self.tor = tor

    def create_starting_url(self):
        # Creating Zillow URL based on the filter.
        url = os.path.join(ZILLOW_URL, 'homes/for_sale/', self.zip_code)
        url += '_rb/?fromHomePage=true&shouldFireSellPageImplicitClaimGA=false&fromHomePageTab=buy'
        return url

    def query_zillow(self):
        url = self.create_starting_url()
        response = get_response(self.tor, url, get_headers())
        if not response:
            print("Failed to fetch the page.")
            return None

        parser = html.fromstring(response.text)
        print('Reading root page results')
        total_homes_results = int(parser.xpath('//div/div/div[@class="search-subtitle"]/span[@class="result-count"]//text()')[0].split()[0])
        PROPERTIES_PER_PAGE = 40
        # don't add 1 b/c we've already queried the first page
        pages_to_query = total_homes_results / PROPERTIES_PER_PAGE
        next_page = parser.xpath('//li[@class="zsg-pagination-next"]/a/@href')[0]
        next_page_url = os.path.dirname(next_page.rstrip('/'))
        next_page_prefix = ZILLOW_URL + next_page_url

        # create some randomness in page browsing
        pages = [page for page in range(2, 2 + pages_to_query)]
        random.shuffle(pages)
        print('Found {} results'.format(total_homes_results))

        responses = [response.text]
        for page in tqdm(pages):
            url = os.path.join(next_page_prefix, '{}_p'.format(page))
            response = get_response(self.tor, url, get_headers())
            if not response:
                print("Failed to fetch the next page.")
                break
            responses.append(response.text)

            with open('/tmp/foo{}.html'.format(page), 'w') as f:
                f.write(response.text.encode('utf8'))
    
            parser = html.fromstring(response.text)
            time.sleep(1.0 + random.random() * 10.0)
        return responses

class ZillowScraper(object):
    """ Class for scraping Zillow search html """    
    GSHEETS_SCOPE = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/spreadsheets',"https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/drive"]

    def __init__(self, description):
        self.description = description
        self.properties_list = []
        self.addresses = []
        self.fieldnames = sorted(['title', 'address', 'days_on_zillow', 'city', 'state', 'postal_code', 'price', 'info', 'broker', 'property_url'])
    
    def parse_properties(self, raw_html):
        parser = html.fromstring(raw_html)
        # try json first as it generally has more consistent info
        properties = maybe_get_json_results(parser)
        # try parsing the xml directly afterwards
        properties.extend(maybe_get_xml_results(parser))
        for prop in properties:
            if prop.address in self.addresses:
                continue
            print('Found {}'.format(prop.address))
            self.addresses.append(prop.address)
            self.properties_list.append(prop)
        return self.properties_list
    
    def write_data_to_csv(self):
        """ Virtual method, implement in base class """
        raise NotImplementedError
INFO = """\
Here are your Zillow results for {}

Results are provided by Engineered Cash Flow LLC
Please support us by following us:
    Facebook: www.facebook.com/engineeredcashflow
    Instagram: www.instagram.com/engineeredcashflow
    Website: www.engineeredcashflow.com

Disclaimer:

All investments, including real estate, are highly speculative in nature and 
involve substantial risk of loss. We encourage our investors to invest very
carefully. We also encourage investors to get personal advice from your 
professional investment advisor and to make independent investigations before
acting on information that we publish. Much of our information is derived 
directly from information published by companies or submitted to governmental 
agencies on which we believe are reliable but are without our independent verification. 
Therefore, we cannot assure you that the information is accurate or complete. 
We do not in any way whatsoever warrant or guarantee the success of any action 
you take in reliance on our statements or recommendations.
"""

class ZillowScraperGsheets(ZillowScraper):
    
    def __init__(self, share_email, zip_code):
        super(ZillowScraperGsheets, self).__init__(zip_code)
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS, self.GSHEETS_SCOPE)
        self.client = gspread.authorize(creds)
        self.share_email = share_email
        self.zip_code = zip_code

    def write_data_to_csv(self):
        sheetname = 'zillow_data_{}_{}'.format(datetime.datetime.now().strftime('%m_%d_%Y__%H_%M_%S'), self.description)
        sheet = self.client.create(sheetname)
        rows = len(self.properties_list) + 1
        cols = len(self.fieldnames)
        worksheet = sheet.get_worksheet(0)
        worksheet.update_title('Info')
        for line in INFO.format(self.zip_code).splitlines():
            worksheet.append_row([line])
        worksheet = sheet.add_worksheet(title=self.description, rows=str(rows), cols=str(cols))
        worksheet.clear()
        worksheet.append_row(['Provided to you by Engineered Cash Flow LLC, www.engineeredcashflow.com'])
        worksheet.append_row(self.fieldnames)
        for p in tqdm(self.properties_list):
            data = []
            for field in self.fieldnames:
                data.append(p.__dict__[field])
            worksheet.append_row(data)
        sheet.share(self.share_email, perm_type='anyone', role='reader')

class ZillowScraperCsv(ZillowScraper):

    def __init__(self, zip_code, outdir):
        super(ZillowScraperCsv, self).__init__(zip_code)
        self.outdir = outdir

    def write_data_to_csv(self):
        fieldnames = ['title', 'address', 'days_on_zillow', 'city', 'state', 'postal_code', 'price', 'info', 'broker', 'property_url']
        name = 'zillow_data_{}_{}.csv'.format(datetime.datetime.now().strftime('%m_%d_%Y__%H_%M_%S'), self.description)
        filename = os.path.join(self.outdir, name)
        print('Saving to {}'.format(filename))
        with open(filename, 'wb') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
            writer.writeheader()
            print('Saving {} properties'.format(len(self.properties_list)))
            for p in self.properties_list:
                data = {}
                for field in self.fieldnames:
                    data[field] = p.__dict__[field]
                writer.writerow(data)
    