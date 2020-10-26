import datetime
import gspread
import gspread_formatting as gsf
import json
import os
import random
import re
import time
import unicodecsv

from decouple import config
from lxml import html
from oauth2client.service_account import ServiceAccountCredentials
from tqdm import tqdm

from src.properties import ZillowPropertyHtml, ZillowPropertyJson
from src.urls import ZILLOW_URL
from src.util import get_tor_client, read_files, clean, get_response, get_headers
from src.util import EMAIL_REGEX

CREDENTIALS = config(
    'GOOGLE_CREDENTIALS',
    default=None,
    cast=lambda x: json.loads(x))


def scrape_zillow_zipcode(zip_code, email):
    match = re.match(EMAIL_REGEX, email)
    if not match:
        return False
    zsearch = ZillowScraperGsheets([zip_code], email)
    zsearch.scrape()
    return True


def maybe_get_xml_results(parser, verbose=False):
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


def maybe_get_json_results(parser, verbose=False):
    raw_json = parser.xpath(
        '//script[@data-zrr-shared-data-key="mobileSearchPageStore"]//text()')
    cleaned_data = clean(raw_json).replace('<!--', "").replace("-->", "")
    json_data = json.loads(cleaned_data)
    search_results = json_data.get('cat1').get(
        'searchResults').get('listResults', [])
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
            response_path=None,
            verbose=self.verbose)
        if not response:
            print("Failed to fetch the page.")
            return None
        try:
            responses = self.parse_zillow_response(response)
        except BaseException:
            print(url)
            raise
        return responses

    def parse_zillow_response(self, response):
        responses = [response.text]
        parser = html.fromstring(response.text)
        print('Reading root page results')
        result_count_str = parser.xpath(
            "//span[@class=\"result-count\"]/text()")
        result_count_str = result_count_str[0].split()[0]
        total_homes_results = int(result_count_str.replace(',', ''))

        print('Found {} results for {}'.format(total_homes_results, self.zip_code))

        PROPERTIES_PER_PAGE = 40
        # don't add 1 b/c we've already queried the first page
        pages_to_query = int(total_homes_results / PROPERTIES_PER_PAGE)
        if pages_to_query <= 0:
            return responses

        if self.verbose:
            with open('/tmp/output.txt', 'w') as f:
                f.write(response.text)

        next_page = parser.xpath(
            '//nav[@role="navigation"][@aria-label="Pagination"]/ul/li//a/@href')[0]
        next_page_prefix = ZILLOW_URL + next_page

        # create some randomness in page browsing
        pages = [page for page in range(2, 2 + pages_to_query)]
        random.shuffle(pages)

        for page in tqdm(pages):
            url = os.path.join(next_page_prefix, '{}_p'.format(page))
            response = get_response(
                self.tor, url, get_headers(), verbose=self.verbose)
            if not response:
                print("Failed to fetch the next page: {}".format(url))
                continue
            responses.append(response.text)
            time.sleep(2.0 + random.random() * 8.0))
        return responses


class ZillowScraper(object):
    """ Class for scraping Zillow search html """

    def __init__(self, zip_codes, verbose=False):
        self.zip_code = ''
        self.zip_codes = zip_codes
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
        if self.verbose:
            print('Verbose printing enabled!')

    def parse_properties(self, raw_html):
        parser = html.fromstring(raw_html)
        # try json first as it generally has more consistent info
        properties = maybe_get_json_results(parser, self.verbose)
        # try parsing the xml directly afterwards
        properties.extend(maybe_get_xml_results(parser, self.verbose))
        properties_list = []
        parsed_addresses = []
        for prop in properties:
            if prop.address in parsed_addresses:
                continue
            if self.verbose:
                print('Found {}'.format(prop.address))
            parsed_addresses.append(prop.address)
            properties_list.append(prop)
        return properties_list

    def write_csv(self):
        """ Virtual method, implement in base class """
        raise NotImplementedError

    def add_data_to_csv(self, properties):
        """ Virtual method, implement in base class
        properties: list of property data for a zip code
        """
        raise NotImplementedError

    def scrape(self):
        tr = get_tor_client()
        for zip_code in self.zip_codes:
            results_pages = []
            self.zip_code = zip_code
            zquery = ZillowHtmlDownloader(tr, zip_code, verbose=self.verbose)
            results_pages.extend(zquery.query_zillow())

            properties_list = []
            for i, result in enumerate(results_pages):
                try:
                    print('Parsing page {}'.format(i + 1))
                    properties_list.extend(self.parse_properties(result))
                except BaseException:
                    print(result)
                    raise
            self.add_data_to_csv(properties_list)
        self.write_csv()


INFO = """\
Here are your Zillow results for {}

Results are provided by Engineered Cash Flow LLC
Please support us by following us:
https://www.facebook.com/engineeredcashflow
https://www.instagram.com/engineeredcashflow
https://www.engineeredcashflow.com

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
    GSHEETS_SCOPE = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/drive']

    def __init__(self, zip_codes, share_email, verbose=False):
        super(ZillowScraperGsheets, self).__init__(zip_codes=zip_codes,
                                                   verbose=verbose)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            CREDENTIALS, scopes=self.GSHEETS_SCOPE)
        self.client = gspread.authorize(creds)
        self.share_email = share_email
        self.sheet = None

    def create_disclaimer_worksheet(self, sheet):
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

    def create_data_worksheet(self, sheet, rows, cols, properties_list):
        worksheet = sheet.add_worksheet(
            title=self.zip_code,
            rows=str(rows),
            cols=str(cols))
        worksheet.clear()
        cell_list = worksheet.range(1, 1, rows, cols)
        cell_values = [
            'Provided to you by Engineered Cash Flow LLC, https://www.engineeredcashflow.com']
        cell_values.extend([''] * (cols - 1))
        cell_values.extend(self.fieldnames)

        for p in tqdm(properties_list):
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
        col_label = chr(ord('a') + cols).upper()
        gsf.format_cell_ranges(worksheet, [
            ('A1:{}1'.format(col_label), fmt_title),
            ('A2:{}2'.format(col_label), fmt_fields)])

    def add_data_to_csv(self, properties_list):
        if self.sheet is None:
            sheetname = 'zillow_data_{}_{}'.format(
                datetime.datetime.now().strftime('%m_%d_%Y__%H_%M_%S'), '_'.join(self.zip_codes))
            self.sheet = self.client.create(sheetname)
            self.create_disclaimer_worksheet(self.sheet)

        rows = len(properties_list) + 2  # title + fieldnames
        cols = len(self.fieldnames)
        self.create_data_worksheet(self.sheet, rows, cols, properties_list)

    def write_csv(self):
        print('Sharing with {}'.format(self.share_email))
        self.sheet.share(
            self.share_email,
            perm_type='user',
            role='owner' if self.share_email.endswith(
                '@gmail.com') else 'writer',
            notify=True,
            email_message='Here is your zip_code list from Engineered Cash Flow',
            with_link=False)
        self.sheet = None


class ZillowScraperCsv(ZillowScraper):

    def __init__(self, zip_codes, outdir, verbose=False):
        super(ZillowScraperCsv, self).__init__(zip_codes=zip_codes,
                                               verbose=verbose)
        self.outdir = outdir
        self.properties_list = []

    def add_data_to_csv(self, properties_list):
        # for this option, we save all zips in the same csv
        self.properties_list.extend(properties_list)

    def write_csv(self):
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
            datetime.datetime.now().strftime('%m_%d_%Y__%H_%M_%S'), self.zip_code)
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
