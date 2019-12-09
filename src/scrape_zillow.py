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
        self.days_on_zillow = ''

ZILLOW_URL = 'https://www.zillow.com/'

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

        parser = html.fromstring(self.raw_html)
        self.description = description
        self.properties_list = []

        self.addresses = []
        # try json first as it generally has more consistent info
        properties = maybe_get_json_results(parser)
        # try parsing the xml directly afterwards
        properties.extend(maybe_get_xml_results(parser))
        for prop in properties:
            if prop.address not in self.addresses:
                print('Found {}'.format(prop.address))
                self.addresses.append(prop.address)
                self.properties_list.append(prop)
        
    
    def get_properties(self):
        return self.properties_list
    
    def write_data_to_csv(self):
        fieldnames = ['title', 'address', 'days_on_zillow', 'city', 'state', 'postal_code', 'price', 'info', 'broker', 'property_url']
        filename = 'properties-{}.csv'.format(self.description)
        print('Saving to {}'.format(filename))
        with open(filename, 'wb') as csvfile:
            print(fieldnames)
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
    parser.add_argument('filename', help='html file of Zillow search results')
    parser.add_argument('description', help='description')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    zsearch = ZillowSearchHtml(args.filename, args.description)
    properties = zsearch.get_properties()
    zsearch.write_data_to_csv()