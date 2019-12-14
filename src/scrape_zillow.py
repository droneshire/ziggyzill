#!/usr/bin/env python 

from lxml import html

import argparse
import getpass
import json
import os
import random
import time
from torrequest import TorRequest
import unicodecsv as csv

from properties import ZillowPropertyHtml, ZillowPropertyJson
from urls import ZILLOW_URL
from util import clean, read_files, save_to_file
from util import get_response, get_headers

TOR_CONF = '/tmp/.tor.conf'

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
        print('Pulling results from page 1/{}'.format(pages_to_query + 1))

        responses = [response.text]
        for page in pages:
            url = os.path.join(next_page_prefix, '{}_p'.format(page))
            response = get_response(self.tor, url, get_headers())
            if not response:
                print("Failed to fetch the next page.")
                break
            responses.append(response.text)

            print('Pulling results from page {}/{}'.format(page, pages_to_query + 1))
            with open('/tmp/foo{}.html'.format(page), 'w') as f:
                f.write(response.text.encode('utf8'))
    
            parser = html.fromstring(response.text)
            time.sleep(1.0 + random.random() * 10.0)
        return responses

    
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
    
    def write_data_to_csv(self, outdir):
        fieldnames = ['title', 'address', 'days_on_zillow', 'city', 'state', 'postal_code', 'price', 'info', 'broker', 'property_url']
        filename = os.path.join(outdir, 'properties-{}.csv'.format(self.description))
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
    parser.add_argument('--filenames', nargs='+', help='html file(s) of Zillow search results')
    parser.add_argument('--zip-code', help='zip code to search')
    parser.add_argument('--outdir', help='output dir', required=True)
    parser.add_argument('description', help='description')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    results_pages = []
    assert args.zip_code is not None or args.filenames is not None, 'invalid args'

    if os.path.isfile(TOR_CONF):
        with open(TOR_CONF) as infile:
            tpwd = infile.read().strip()
    else:
        tpwd = getpass.getpass(prompt='Tor password: ', stream=None)
        with open(TOR_CONF, 'w') as outfile:
            outfile.write(tpwd)
    tr = TorRequest(password=tpwd)
    tr.reset_identity()

    if args.zip_code:
        html_path = 'properties_{}__{}_{}.html'.format(
                    time.strftime("%Y%m%d-%H%M%S"), args.description, args.zip_code)
        zquery = ZillowHtmlDownloader(tr, args.zip_code)
        results_pages.extend(zquery.query_zillow())
        if not results_pages:
            assert args.filenames, 'Must specify a downloaded html file since we cannot query zillow!'
            results_pages.extend(read_files(args.filenames))
    elif args.filenames:
        print('Reading:\n{}'.format('\t\n'.join(args.filenames)))
        results_pages.extend(read_files(args.filenames))

    zsearch = ZillowScraper(args.description)
    for result in results_pages:
        try:
            print('Parsing result...')
            zsearch.parse_properties(result)
        except:
            print(result)
            raise
    zsearch.write_data_to_csv(args.outdir)