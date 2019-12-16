import argparse
import os
import re
import time

from util import get_tor_client, read_files
from zillow_scraper import ZillowHtmlDownloader
from zillow_scraper import ZillowScraperCsv, ZillowScraperGsheets

EMAIL_REGEX = re.compile('\S+@\S+')

def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    # required inputs
    parser.add_argument('zipcode', help='zip code to search')

    # optional inputs
    parser.add_argument('--filenames', nargs='+', help='html file(s) of Zillow search results')

    # subparsers
    subparsers = parser.add_subparsers(dest='save_option', help='save option')
    subparsers.required = True

    local_parser = subparsers.add_parser('local', help='save outputs locally')
    local_parser.add_argument('--outdir', help='output dir', required=True)

    web_parser = subparsers.add_parser('web', help='save outputs to gsheets')    
    web_parser.add_argument('--email', help='email to share spreadsheet with', required=True)
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    assert len(args.zipcode) == 5, 'invalid zip code argument'

    if args.save_option == 'local':
        zsearch = ZillowScraperCsv(args.zipcode, args.outdir)
    elif args.save_option == 'web':
        match = re.match(EMAIL_REGEX, args.email)
        if not match:
            raise Exception('Invalid email type')
        zsearch = ZillowScraperGsheets(args.zipcode, args.email)
        
    results_pages = []
    if args.filenames:
        print('Reading:\n{}'.format('\t\n'.join(args.filenames)))
        results_pages.extend(read_files(args.filenames))
    else:
        tr = get_tor_client()
        zquery = ZillowHtmlDownloader(tr, args.zipcode)
        results_pages.extend(zquery.query_zillow())
        if not results_pages:
            assert args.filenames, 'Must specify a downloaded html file since we cannot query zillow!'
            results_pages.extend(read_files(args.filenames))

    for result in results_pages:
        try:
            print('Parsing result...')
            zsearch.parse_properties(result)
        except:
            print(result)
            raise
    zsearch.write_data_to_csv()