""" Util functions """
import requests

def get_response(tor, url, headers, response_path=None):
    for i in range(5):
        print('URL: {}'.format(url))
        response = tor.get(url, headers=headers)
        if response_path:
            save_to_file(response_path, response.text)
        if response.status_code != 200:
            continue            
        if 'Please verify you\'re a human to continue.' in response.text:
            raise Exception('!!!REcaptcha robot blocking us from site!!!'.format(url))
        return response
    return None

def get_headers():
    headers = {'user-agent': 'Chrome/78.0.3904.108 Safari/537.36'}
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