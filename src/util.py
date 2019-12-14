""" Util functions """
import requests

def get_response(url, headers, response_path=None):
    for i in range(5):
        print('URL: {}'.format(url))
        response = requests.get(url, headers=headers)
        if response_path:
            save_to_file(response_path, response.text)
        if response.status_code != 200:
            continue            
        if 'Please verify you\'re a human to continue.' in response.text:
            raise Exception('!!!REcaptcha robot blocking us from site!!!'.format(url))
        return response
    return None

def get_headers():
    headers = {'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'accept-encoding': 'gzip, deflate, sdch, br',
            'accept-language': 'en-GB,en;q=0.8,en-US;q=0.6,ml;q=0.4',
            'cache-control': 'max-age=0',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36'}
    return headers

def clean(text):
    if text:
        return ' '.join(' '.join(text).split())
    return None

def save_to_file(path, data):
    with open(path, 'w') as fp:
        fp.write(data.encode('utf8'))

def read_files(filenames):
    read_files = []
    for filename in filenames:
        with open(filename) as input:
            data = input.read() 
        read_files.append(data)
    return read_files