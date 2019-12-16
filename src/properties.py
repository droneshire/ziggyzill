from urls import ZILLOW_URL
from util import clean

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


class ZillowPropertyHtml(Property):

    def __init__(self, html_elements, json_elements):
        super(ZillowPropertyHtml, self).__init__()
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

class ZillowPropertyJson(Property):

    def __init__(self, json_input):
        super(ZillowPropertyJson, self).__init__()
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