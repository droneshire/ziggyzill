import argparse
import os
import re
import time

from src.util import EMAIL_REGEX
from src.zillow_scraper import ZillowScraperCsv, ZillowScraperGsheets


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    # required inputs
    parser.add_argument('zip_codes', nargs='+', help='zip code(s) to search')
    parser.add_argument('--verbose', action='store_true', help='verbose')

    # subparsers
    subparsers = parser.add_subparsers(dest='save_option', help='save option')
    subparsers.required = True

    local_parser = subparsers.add_parser('local', help='save outputs locally')
    local_parser.add_argument('--outdir', help='output dir', required=True)

    web_parser = subparsers.add_parser('web', help='save outputs to gsheets')
    web_parser.add_argument(
        '--email',
        help='email to share spreadsheet with',
        required=True)

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    for zip_code in args.zip_codes:
        assert len(zip_code) == 5, 'invalid zip code argument {}'.format(zip_code)

    if args.save_option == 'local':
        zsearch = ZillowScraperCsv(args.zip_codes, args.outdir, args.verbose)
    elif args.save_option == 'web':
        match = re.match(EMAIL_REGEX, args.email)
        if not match:
            raise Exception('Invalid email type')
        zsearch = ZillowScraperGsheets(args.zip_codes, args.email, args.verbose)
    zsearch.scrape()
