#!/usr/bin/env python 

from lxml import html

import argparse
import json
import os
import random
import requests
import time
import unicodecsv as csv

ZILLOW_URL = 'https://www.zillow.com'

def get_response(url, headers, response_path=None):
    # Getting response from zillow.com.
    for i in range(5):
        print('URL: {}'.format(url))
        response = requests.get(url, headers=headers)
        if response_path:
            save_to_file(response_path, response.text)
        if response.status_code != 200:
            continue
        return response
    return None

def clean(text):
    if text:
        return ' '.join(' '.join(text).split())
    return None

def save_to_file(path, data):
    with open(path, 'w') as fp:
        fp.write(data.encode('utf8'))

class ZillowHtmlDownloader(object):
    """ Class that downloads zillow zip code searches for scraping """
    
    @staticmethod
    def get_headers():
        # Creating headers.
        headers = {'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'accept-encoding': 'gzip, deflate, sdch, br',
                'accept-language': 'en-GB,en;q=0.8,en-US;q=0.6,ml;q=0.4',
                'cache-control': 'max-age=0',
                'upgrade-insecure-requests': '1',
                'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.131 Safari/537.36'}
        return headers
    
    def __init__(self, zip_code):
        self.zip_code = zip_code
    
    def create_starting_url(self):
        # Creating Zillow URL based on the filter.
        url = os.path.join(ZILLOW_URL, 'homes/for_sale/', self.zip_code)
        url += '_rb/?fromHomePage=true&shouldFireSellPageImplicitClaimGA=false&fromHomePageTab=buy'
        return url

    def query_zillow(self):
        url = self.create_starting_url()
        response = get_response(url, ZillowHtmlDownloader.get_headers())
        if not response:
            print("Failed to fetch the page.")
            return None

        parser = html.fromstring(response.text)
        total_homes_results = int(parser.xpath('//div/div/div[@class="search-subtitle"]/span[@class="result-count"]//text()')[0].split()[0])
        PROPERTIES_PER_PAGE = 40
        # don't add 1 b/c we've already queried the first page
        pages_to_query = total_homes_results / PROPERTIES_PER_PAGE
        next_page = parser.xpath('//li[@class="zsg-pagination-next"]/a/@href')[0]
        next_page_url = os.path.dirname(next_page.rstrip('/'))
        next_page_prefix = ZILLOW_URL + next_page_url

        print('Found {} results'.format(total_homes_results))
        print('Pulling results from page 1/{}'.format(pages_to_query + 1))
        responses = [response.text]
        for page in range(2, 2 + pages_to_query):
            url = os.path.join(next_page_prefix, '{}_p'.format(page))
            response = get_response(url, self.get_headers())
            if not response:
                print("Failed to fetch the next page.")
                break
            responses.append(response.text)

            print('Pulling results from page {}/{}'.format(page, pages_to_query + 1))
            with open('/tmp/foo{}.html'.format(page), 'w') as f:
                f.write(response.text.encode('utf8'))
    
            parser = html.fromstring(response.text)
            time.sleep(random.random() * 2.0)
        return responses

    
    
class Property(object):

    def __init__(self):
        self.address = ''
        self.city = ''
        self.state = ''
        self.postal_code = ''
        self.price = ''
        self.info = ''
        self.broker = ''
        self.title = ''
        self.property_url = ''
        self.is_forsale = True
        self.bathrooms = ''
        self.bedrooms = ''
        self.property_info = ''
        self.area = ''
        self.days_on_zillow = ''


class PropertyHtml(Property):

    def __init__(self, html_elements, json_elements):
        super(PropertyHtml, self).__init__()
        raw_address = html_elements.xpath('.//h3[@class="list-card-addr"]//text()')
        raw_price = html_elements.xpath('.//div[@class="list-card-price"]//text()')
        raw_broker_name = html_elements.xpath('.//div[@class="list-card-truncate"]//text()')
        if html_elements.xpath('.//span[@class="zsg-icon-for-sale"]'):
            self.is_forsale = True
        maybe_days_on_zillow = html_elements.xpath('.//div[@class="list-card-top"]//div[@class="list-card-variable-text list-card-img-overlay"]//text()')[0]
        if 'days on Zillow' in maybe_days_on_zillow:
            self.days_on_zillow = int(maybe_days_on_zillow.split()[0])
        address_node = json_elements.get('address') 

        self.city = address_node.get('addressLocality')
        self.state = address_node.get('addressRegion')
        self.postal_code = address_node.get('postalCode')
        self.price = clean(raw_price)
        self.bedrooms = json_elements.get('numberOfRooms')
        self.info = '{} bds'.format(self.bedrooms)
        self.address = clean(raw_address)
        self.broker = clean(raw_broker_name)
        self.title = json_elements.get('statusText')
        self.property_url = ZILLOW_URL + json_elements.get('url')

class PropertyJson(Property):

    def __init__(self, json_input):
        super(PropertyJson, self).__init__()
        self.address = json_input.get('addressWithZip')
        self.property_info = json_input.get('hdpData', {}).get('homeInfo')
        self.city = self.property_info.get('city')
        self.state = self.property_info.get('state')
        self.postal_code = self.property_info.get('zipcode')
        self.days_on_zillow = self.property_info.get('daysOnZillow')
        self.price = json_input.get('price')
        self.bedrooms = json_input.get('beds')
        self.bathrooms = json_input.get('baths')
        self.area = json_input.get('area')
        self.info = '{} bds, {} ba ,{} sqft'.format(self.bedrooms, self.bathrooms, self.area)
        self.broker = json_input.get('brokerName')
        self.property_url = json_input.get('detailUrl')
        self.title = json_input.get('statusText')
        

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
        properties.append(PropertyHtml(xml_result, json_result))
    return properties

def maybe_get_json_results(parser):
    raw_json = parser.xpath('//script[@data-zrr-shared-data-key="mobileSearchPageStore"]//text()')
    cleaned_data = clean(raw_json).replace('<!--', "").replace("-->", "")
    json_data = json.loads(cleaned_data)
    search_results = json_data.get('searchResults').get('listResults', [])
    properties = []
    for result in search_results:
        properties.append(PropertyJson(result))
    return properties


class ZillowScraper(object):
    """ Class for scraping Zillow search html """    

    def __init__(self, description):
        self.description = description
        self.properties_list = []
        self.addresses = []
    
    def parse_properties(self, raw_html):
        parser = html.fromstring(raw_html)
        # try json first as it generally has more consistent info
        properties = maybe_get_json_results(parser)
        # try parsing the xml directly afterwards
        properties.extend(maybe_get_xml_results(parser))
        for prop in properties:
            if prop.address not in self.addresses:
                print('Found {}'.format(prop.address))
                self.addresses.append(prop.address)
                self.properties_list.append(prop)
        return self.properties_list
    
    def write_data_to_csv(self):
        fieldnames = ['title', 'address', 'days_on_zillow', 'city', 'state', 'postal_code', 'price', 'info', 'broker', 'property_url']
        filename = 'properties-{}.csv'.format(self.description)
        print('Saving to {}'.format(filename))
        with open(filename, 'wb') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=sorted(fieldnames))
            writer.writeheader()
            print('Saving {} properties'.format(len(self.properties_list)))
            for p in self.properties_list:
                data = {}
                for field in fieldnames:
                    data[field] = p.__dict__[field]
                writer.writerow(data)
    
def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html-filename', help='html file of Zillow search results')
    parser.add_argument('--zip-code', help='zip code to search')
    parser.add_argument('description', help='description')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    results_pages = []
    assert args.zip_code is not None or args.html_filename is not None, 'invalid args'

    if args.zip_code:
        html_path = 'properties-{}-{}.html'.format(args.description, args.zip_code)
        zquery = ZillowHtmlDownloader(args.zip_code)
        results_pages.extend(zquery.query_zillow())
        if not results_pages:
            assert args.html_filename, 'Must specify a downloaded html file since we cannot query zillow!'
            results_pages.extend([args.html_filename])
    elif args.html_filename:
        with open(args.html_filename) as htmlfile:
            raw_html = htmlfile.read()  
        results_pages.extend([raw_html])

    zsearch = ZillowScraper(args.description)
    for result in results_pages:
        try:
            print('Parsing result...')
            zsearch.parse_properties(result)
        except:
            print(result)
            raise
    zsearch.write_data_to_csv()