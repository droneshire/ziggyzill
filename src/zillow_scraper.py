#!/usr/bin/env python

import datetime
import gspread
import gspread_formatting as gsf
import json
import os
import random
import re
import time
import unicodecsv

from lxml import html
from oauth2client.service_account import ServiceAccountCredentials
from tqdm import tqdm

from src.properties import ZillowPropertyHtml, ZillowPropertyJson
from src.urls import ZILLOW_URL
from src.util import get_tor_client, read_files, clean, get_response, get_headers
from src.util import EMAIL_REGEX

CREDENTIALS = os.path.expanduser('~/.creds.json')


def scrape_zillow_zipcode(zipcode, email):
    match = re.match(EMAIL_REGEX, email)
    if not match:
        return
    zsearch = ZillowScraperGsheets(zipcode, email)
    zsearch.scrape(filenames=None)


def maybe_get_xml_results(parser):
    xml_results = parser.xpath(
        '//article[@class="list-card list-card-short list-card_not-saved"]')
    string_results = parser.xpath(
        '//li/script[@type="application/ld+json"]//text()')
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
    raw_json = parser.xpath(
        '//script[@data-zrr-shared-data-key="mobileSearchPageStore"]//text()')
    cleaned_data = clean(raw_json).replace('<!--', "").replace("-->", "")
    json_data = json.loads(cleaned_data)
    search_results = json_data.get('searchResults').get('listResults', [])
    properties = []
    for result in search_results:
        properties.append(ZillowPropertyJson(result))
    return properties


class ZillowHtmlDownloader(object):
    """ Class that downloads zillow zip code searches for scraping """

    def __init__(self, tor, zip_code, verbose=False):
        self.zip_code = zip_code
        self.tor = tor
        self.verbose = verbose

    def create_starting_url(self):
        # Creating Zillow URL based on the filter.
        url = os.path.join(ZILLOW_URL, 'homes/for_sale/', self.zip_code)
        url += '_rb/?fromHomePage=true&shouldFireSellPageImplicitClaimGA=false&fromHomePageTab=buy'
        return url

    def query_zillow(self):
        url = self.create_starting_url()
        response = get_response(
            self.tor,
            url,
            get_headers(),
            verbose=self.verbose)
        if not response:
            print("Failed to fetch the page.")
            return None

        parser = html.fromstring(response.text)
        print('Reading root page results')
        result_count_str = parser.xpath(
            '//div/div/div[@class="search-subtitle"]/span[@class="result-count"]//text()')[0].split()[0]
        total_homes_results = int(result_count_str.replace(',', ''))
        PROPERTIES_PER_PAGE = 40
        # don't add 1 b/c we've already queried the first page
        pages_to_query = int(total_homes_results / PROPERTIES_PER_PAGE)
        next_page = parser.xpath(
            '//li[@class="zsg-pagination-next"]/a/@href')[0]
        next_page_url = os.path.dirname(next_page.rstrip('/'))
        next_page_prefix = ZILLOW_URL + next_page_url

        # create some randomness in page browsing
        pages = [page for page in range(2, 2 + pages_to_query)]
        random.shuffle(pages)
        print('Found {} results'.format(total_homes_results))

        responses = [response.text]
        for page in tqdm(pages):
            url = os.path.join(next_page_prefix, '{}_p'.format(page))
            response = get_response(
                self.tor, url, get_headers(), verbose=self.verbose)
            if not response:
                print("Failed to fetch the next page.")
                continue
            responses.append(response.text)

            parser = html.fromstring(response.text)
            time.sleep(1.0 + random.random() * 1.0)
        return responses


class ZillowScraper(object):
    """ Class for scraping Zillow search html """
    GSHEETS_SCOPE = [
        "https://spreadsheets.google.com/feeds",
        'https://www.googleapis.com/auth/spreadsheets',
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"]

    def __init__(self, description, zipcode, verbose=False):
        self.description = description
        self.zipcode = zipcode
        self.properties_list = []
        self.addresses = []
        self.fieldnames = sorted(['title',
                                  'address',
                                  'days_on_zillow',
                                  'city',
                                  'state',
                                  'postal_code',
                                  'price',
                                  'info',
                                  'broker',
                                  'property_url'])
        self.verbose = verbose

    def parse_properties(self, raw_html):
        parser = html.fromstring(raw_html)
        # try json first as it generally has more consistent info
        properties = maybe_get_json_results(parser)
        # try parsing the xml directly afterwards
        properties.extend(maybe_get_xml_results(parser))
        for prop in properties:
            if prop.address in self.addresses:
                continue
            if self.verbose:
                print('Found {}'.format(prop.address))
            self.addresses.append(prop.address)
            self.properties_list.append(prop)
        return self.properties_list

    def write_data_to_csv(self):
        """ Virtual method, implement in base class """
        raise NotImplementedError

    def scrape(self, filenames=None):
        results_pages = []
        if filenames:
            print('Reading:\n{}'.format('\t\n'.join(filenames)))
            results_pages.extend(read_files(filenames))
        else:
            tr = get_tor_client()
            zquery = ZillowHtmlDownloader(tr, self.zipcode)
            results_pages.extend(zquery.query_zillow())
            if not results_pages:
                assert filenames, 'Must specify a downloaded html file since we cannot query zillow!'
                results_pages.extend(read_files(filenames))

        for i, result in enumerate(results_pages):
            try:
                print('Parsing page {}'.format(i + 1))
                self.parse_properties(result)
            except BaseException:
                print(result)
                raise
        self.write_data_to_csv()


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
    def __init__(self, zip_code, share_email):
        super(ZillowScraperGsheets, self).__init__(description=zip_code,
                                                   zipcode=zip_code)
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            CREDENTIALS, self.GSHEETS_SCOPE)
        self.client = gspread.authorize(creds)
        self.share_email = share_email
        self.zip_code = zip_code

    def write_data_to_csv(self):
        sheetname = 'zillow_data_{}_{}'.format(
            datetime.datetime.now().strftime('%m_%d_%Y__%H_%M_%S'), self.description)
        sheet = self.client.create(sheetname)
        rows = len(self.properties_list) + 2  # title + fieldnames
        cols = len(self.fieldnames)

        # disclaimer worksheet
        worksheet = sheet.get_worksheet(0)
        worksheet.update_title('Info')
        disclaimer = INFO.format(self.zip_code).splitlines()
        disclaimer_cells = worksheet.range(1, 1, len(disclaimer), 1)
        for i, line in enumerate(disclaimer):
            disclaimer_cells[i].value = line
        worksheet.update_cells(disclaimer_cells)

        fmt = gsf.cellFormat(
            backgroundColor=gsf.color(0.7, 0.77, 0.87),
            textFormat=gsf.textFormat(
                bold=True,
                foregroundColor=gsf.color(0, 0, .54)),
            horizontalAlignment='LEFT')
        gsf.format_cell_ranges(worksheet, [('A1:E1', fmt),
                                           ('A3:E3', fmt),
                                           ('A4:E4', fmt),
                                           ('A9:E9', fmt)])

        # data worksheet
        worksheet = sheet.add_worksheet(
            title=self.description,
            rows=str(rows),
            cols=str(cols))
        worksheet.clear()
        cell_list = worksheet.range(1, 1, rows, cols)
        cell_values = [
            'Provided to you by Engineered Cash Flow LLC, www.engineeredcashflow.com']
        cell_values.extend([''] * (cols - 1))
        cell_values.extend(self.fieldnames)

        for p in tqdm(self.properties_list):
            data = []
            for field in self.fieldnames:
                data.append(p.__dict__[field])
            cell_values.extend(data)

        assert len(cell_values) == len(cell_list), 'Cell/value mismatch'

        for i, val in enumerate(cell_values):
            cell_list[i].value = val
        worksheet.update_cells(cell_list)

        fmt_title = gsf.cellFormat(
            backgroundColor=gsf.color(0.7, 0.77, 0.87),
            textFormat=gsf.textFormat(
                bold=True,
                foregroundColor=gsf.color(0, 0, .54)),
            horizontalAlignment='LEFT')
        fmt_fields = gsf.cellFormat(
            backgroundColor=gsf.color(0.7, 0.77, 0.87),
            textFormat=gsf.textFormat(
                bold=True,
                foregroundColor=gsf.color(0, 0, .54)),
            horizontalAlignment='CENTER')
        # hack since gspread_formatting doesn't seem to support
        # full row notation (e.g. '1:2')
        range_str = 'B2:{}2'.format(chr(ord('a') + cols).upper())
        gsf.format_cell_ranges(worksheet, [('A1', fmt_title),
                                           (range_str, fmt_fields)])

        print('Sharing with {}'.format(self.share_email))
        sheet.share(
            self.share_email,
            perm_type='user',
            role='owner',
            notify=True,
            email_message='Here is your zipcode list from Engineered Cash Flow',
            with_link=False)


class ZillowScraperCsv(ZillowScraper):

    def __init__(self, zip_code, outdir):
        super(
            ZillowScraperCsv,
            self).__init__(
            description=zip_code,
            zipcode=zip_code)
        self.outdir = outdir

    def write_data_to_csv(self):
        fieldnames = [
            'title',
            'address',
            'days_on_zillow',
            'city',
            'state',
            'postal_code',
            'price',
            'info',
            'broker',
            'property_url']
        name = 'zillow_data_{}_{}.csv'.format(
            datetime.datetime.now().strftime('%m_%d_%Y__%H_%M_%S'),
            self.description)
        filename = os.path.join(self.outdir, name)
        print('Saving to {}'.format(filename))
        with open(filename, 'wb') as csvfile:
            writer = unicodecsv.DictWriter(csvfile, fieldnames=self.fieldnames)
            writer.writeheader()
            print('Saving {} properties'.format(len(self.properties_list)))
            for p in self.properties_list:
                data = {}
                for field in self.fieldnames:
                    data[field] = p.__dict__[field]
                writer.writerow(data)
