#!/usr/bin/env python 

from lxml import html

import requests
import unicodecsv as csv
import argparse
import json
import os

def clean(text):
    if text:
        return ' '.join(' '.join(text).split())
    return None
        
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

class PropertyHtml(Property):

    def __init__(self, property_html):
        super(PropertyHtml, self).__init__()
        raw_address = property_html.xpath(".//span[@itemprop='address']//span[@itemprop='streetAddress']//text()")
        raw_city = property_html.xpath(".//span[@itemprop='address']//span[@itemprop='addressLocality']//text()")
        raw_state = property_html.xpath(".//span[@itemprop='address']//span[@itemprop='addressRegion']//text()")
        raw_postal_code = property_html.xpath(".//span[@itemprop='address']//span[@itemprop='postalCode']//text()")
        raw_price = property_html.xpath(".//span[@class='zsg-photo-card-price']//text()")
        raw_info = property_html.xpath(".//span[@class='zsg-photo-card-info']//text()")
        raw_broker_name = property_html.xpath(".//span[@class='zsg-photo-card-broker-name']//text()")
        url = property_html.xpath(".//a[contains(@class,'overlay-link')]/@href")
        raw_title = property_html.xpath(".//h4//text()")

        self.address = clean(raw_address)
        self.city = clean(raw_city)
        self.state = clean(raw_state)
        self.postal_code = clean(raw_postal_code)
        self.price = clean(raw_price)
        self.info = clean(raw_info).replace(u"\xb7", ',')
        self.broker = clean(raw_broker_name)
        self.title = clean(raw_title)
        self.property_url = "https://www.zillow.com" + url[0] if url else None
        self.is_forsale = property_html.xpath('.//span[@class="zsg-icon-for-sale"]')

class PropertyJson(Property):

    def __init__(self, json_input):
        super(PropertyJson, self).__init__()
        self.address = json_input.get('addressWithZip')
        self.property_info = json_input.get('hdpData', {}).get('homeInfo')
        self.city = self.property_info.get('city')
        self.state = self.property_info.get('state')
        self.postal_code = self.property_info.get('zipcode')
        self.price = json_input.get('price')
        self.bedrooms = json_input.get('beds')
        self.bathrooms = json_input.get('baths')
        self.area = json_input.get('area')
        self.info = '{} bds, {} ba ,{} sqft'.format(self.bedrooms, self.bathrooms, self.area)
        self.broker = json_input.get('brokerName')
        self.property_url = json_input.get('detailUrl')
        self.title = json_input.get('statusText')


class ZillowSearchHtml(object):
    """ Class for managing Zillow search html """    
    def __init__(self, html_input, description):
        if os.path.isfile(html_input):
            with open(html_input) as htmlfile:
                self.raw_html = htmlfile.read()
        elif isinstance(html_input, str):
            self.raw_html = html_input
        else:
            raise ValueError

        self.description = description
        self.properties_list = []
        parser = html.fromstring(self.raw_html)
        search_results = parser.xpath("//div[@id='search-results']//article")
        use_json = not search_results
        if use_json:
            raw_json = parser.xpath('//script[@data-zrr-shared-data-key="mobileSearchPageStore"]//text()')
            cleaned_data = clean(raw_json).replace('<!--', "").replace("-->", "")
            json_data = json.loads(cleaned_data)
            search_results = json_data.get('searchResults').get('listResults', [])

        for result in search_results:
            pclass = PropertyJson if use_json else PropertyHtml
            p = pclass(result)
            if p.is_forsale:
                self.properties_list.append(p)
    
    def get_properties(self):
        return self.properties_list
    
    def write_data_to_csv(self):
        fieldnames = ['title', 'address', 'city', 'state', 'postal_code', 'price', 'info', 'broker', 'property_url']
        filename = 'properties-{}.csv'.format(self.description)
        print('Saving to {}'.format(filename))
        with open(filename, 'wb') as csvfile:
            print(fieldnames)
            writer = csv.DictWriter(csvfile, fieldnames=sorted(fieldnames))
            writer.writeheader()
            for p in self.properties_list:
                data = {}
                for field in fieldnames:
                    data[field] = p.__dict__[field]
                writer.writerow(data)
    
def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('filename', help='html file of Zillow search results')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    zsearch = ZillowSearchHtml(args.filename, '19145')
    properties = zsearch.get_properties()
    for prop in properties:
        print('Found {}'.format(prop.address))
    zsearch.write_data_to_csv()