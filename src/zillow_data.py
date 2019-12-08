""" Get area info from Zillow """
import argparse
import datetime

import zillow

GOOGLE_CONF = '/home/ross/.google.conf'
ZILLOW_CONF = '/home/ross/.zillow.conf'

class ApiKey(object):
    """ Simple wrapper to get a key from conf file"""
    def __new__(cls, key_file):
        with open(key_file, 'r') as f:
            key = f.readline().replace('\n', '')
        if not key:
            raise ValueError
        return key

def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip-code', type=int, help='zip code', required=True)
    parser.add_argument('--address', nargs='+', help='address of property', required=True)
    return parser.parse_args()


if __name__== '__main__':
    zkey = ApiKey(ZILLOW_CONF)
    # gmaps = googlemaps.Client(ApiKey(GOOGLE_CONF))
    args = parse_args()
    api = zillow.ValuationApi()

    if args.address:
        addy = ' '.join(args.address)
        data = api.GetSearchResults(zkey, addy, args.zip_code)
        comps = api.GetComps(zkey, data.zpid)
        for comp in comps['comps']:
            print(comp.full_address.street)

    print(data)
    # if args.zip_code:
    #     pass
    # if args.address:
    #     deep_search_response = zillow.get_deep_search_results(args.address,zipcode)
    #     result = pyzillow.GetDeepSearchResults(deep_search_response)
    # for i in result.__dict__:
    #     print(i , getattr(result, i))
    # geocode_result = gmaps.geocode(address)
    # print(geocode_result)