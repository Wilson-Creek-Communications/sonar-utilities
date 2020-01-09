"""
Generates a KML of all active inventoried devices.
"""

from getpass import getpass

from re import match
from requests import get, HTTPError
from requests.auth import HTTPBasicAuth

# TODO: arguments in custom exceptions


class URLError(Exception):
    """A customizable URL error"""

    def __init__(self, url):
        super(URLError, self).__init__(url)
        self.url = url

    def __str__(self):
        return 'Error: URL {} invalid'.format(repr(self.url))


class APIError(HTTPError):
    """A customizable API error"""

    def __init__(self, action, url, code):
        super(APIError, self).__init__(action, url, code)
        self.action = action
        self.url = url
        self.code = code

    def __str__(self):
        return 'Error: requesting {} on {} resulted in the response {}'.format(repr(self.action), repr(self.url), repr(self.code))


BASE_URL = 'https://wilsoncreek.sonar.software/api/v1'

SONAR_USERNAME = input('Username: ')
SONAR_PASSWORD = getpass()


def create_url(endpoint):
    """
    Append an endpoint to the Sonar BASE_URL.

    Keyword arguments:
    endpoint -- the endpoint to append
    """
    if endpoint[:1] != '/':
        raise URLError(endpoint)

    return '{}{}'.format(BASE_URL, endpoint)


def rest_get(endpoint, **kwargs):
    """
    Perform a GET request to Sonar.

    Keyword arguments:
    endpoint -- the REST API endpoint to access
    **kwargs -- any params to include in the GET request
    """
    params = {name: kwargs[name]
              for name in kwargs if kwargs[name] is not None}
    headers = {'content-type': 'application/json',
               'accept-encoding': 'application/gzip'}
    request_url = create_url(endpoint)
    resp = get(request_url, params=params,
               headers=headers, auth=HTTPBasicAuth(SONAR_USERNAME, SONAR_PASSWORD))

    if resp.status_code != 200:
        raise APIError('GET', request_url, resp.status_code)

    return resp.json()


def get_all_accounts_coordinates():
    """Get a dictionary of all account coordinates."""
    geojson = rest_get('/mapping/geojson/accounts')['features']

    accounts = {}

    for point in geojson:
        accounts[point['properties']['id']] = point['geometry']['coordinates']

    return accounts


def get_all_network_sites_coordinates():
    """Get a dictionary of all network site coordinates."""
    geojson = rest_get('/mapping/geojson/network_sites')['features']
    network_sites = {}

    for point in geojson:
        network_sites[point['properties']['id']
                      ] = point['geometry']['coordinates']

    return network_sites


def get_all_coordinates():
    """Get a combined dictionary of both network site and account coordinates."""
    return {**get_all_accounts_coordinates(), **get_all_network_sites_coordinates()}


def get_all_ubiquiti_models():
    """Get a list of all Ubiquiti models."""
    pages = rest_get('/inventory/models')['paginator']['total_pages']
    models = []

    for page in range(pages):
        for model in rest_get('/inventory/models', page=page)['data']:
            if model['manufacturer_id'] == 1:
                models.append(model['id'])

    return models


def get_all_active_ubiquiti_inventory_macs():
    """Get a dictionary of all active Ubiquiti devices which includes id, assignee id, and mac address."""
    models = get_all_ubiquiti_models()
    pages = rest_get('/inventory/items')['paginator']['total_pages']
    macs = {}

    for page in range(pages):
        for item in rest_get('/inventory/items', page=page)['data']:
            if item['assignee_type'] not in ['generic_inventory_assignees', 'inventory_locations', 'vehicles']:
                if item['inventory_model_id'] in models:
                    for field in item['fields']:
                        if match("^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$", field['data'].upper()):
                            macs[item['id']] = {
                                'assignee_id': item['assignee_id'],
                                'mac': field['data']
                            }

    return macs


def match_coordinates_to_inventory():
    macs = get_all_active_ubiquiti_inventory_macs()
    coordinates = get_all_coordinates()

    matched = {}

    for item in macs:
        matched[macs[item]['mac']] = coordinates[macs[item]['assignee_id']]

    return matched

########
# MAIN #
########


with open('aircontrol_locations.kml', 'w', newline='') as kmlfile:
    kmlfile.write("<?xml version='1.0' encoding='UTF-8'?>\n")
    kmlfile.write("<kml xmlns='http://earth.google.com/kml/2.1'>\n")
    kmlfile.write("<Document>\n")
    kmlfile.write("   <name>" + 'aircontrol_locations.kml' + "</name>\n")

    for mac, location in match_coordinates_to_inventory().items():
        kmlfile.write("   <Placemark>\n")
        kmlfile.write("       <name>" + mac + "</name>\n")
        kmlfile.write("       <description>" + mac + "</description>\n")
        kmlfile.write("       <Point>\n")
        kmlfile.write("           <coordinates>" +
                      str(location[0]) + "," + str(location[1]) + "</coordinates>\n")
        kmlfile.write("       </Point>\n")
        kmlfile.write("   </Placemark>\n")

    kmlfile.write("</Document>\n")
    kmlfile.write("</kml>\n")
