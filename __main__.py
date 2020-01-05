import argparse
import os
import re
import time

from src.util import EMAIL_REGEX
from src.zillow_scraper import ZillowScraperCsv, ZillowScraperGsheets

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
    zsearch.scrape(args.filenames)