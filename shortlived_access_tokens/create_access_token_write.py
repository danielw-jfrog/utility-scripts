#!/usr/bin/env python3

### IMPORTS ###
import argparse
import datetime
import json
import logging
import os
import urllib.request
import urllib.error

### GLOBALS ###

### FUNCTIONS ###
def make_api_request(login_data, method, path, data = None, is_data_json = True):
    """
    Send the request to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param str method: One of "GET", "PUT", or "POST".
    :param str url: URL of the API sans the "host" part.
    :param str data: String containing the data serialized into JSON format.
    :return:
    """
    req_url = "{}{}".format(login_data["host"], path)
    req_headers = {}
    if is_data_json:
        req_headers["Content-Type"] = "application/json"
    else:
        req_headers["Content-Type"] = "text/plain"
    req_data = data.encode("utf-8") if data is not None else None

    logging.debug("req_url: %s", req_url)
    logging.debug("req_headers: %s", req_headers)
    logging.debug("req_data: %s", req_data)

    req_headers["Authorization"] = "Bearer {}".format(login_data["token"])

    #req_pwmanager = urllib.request.HTTPPasswordMgrWithPriorAuth()
    #req_pwmanager.add_password(None, login_data["host"], login_data["user"], login_data["apikey"], is_authenticated = True)
    #req_handler = urllib.request.HTTPBasicAuthHandler(req_pwmanager)
    #req_opener = urllib.request.build_opener(req_handler)
    #urllib.request.install_opener(req_opener)

    request = urllib.request.Request(req_url, data = req_data, headers = req_headers, method = method)
    resp = None
    try:
        with urllib.request.urlopen(request) as response:
            # Check the status and log
            # NOTE: response.status for Python >=3.9, change to response.code if Python <=3.8
            resp = response.read().decode("utf-8")
            logging.debug("  Response Status: %d, Response Body: %s", response.status, resp)
            logging.debug("Repository operation successful")
    except urllib.error.HTTPError as ex:
        logging.warning("Error (%d) for repository operation", ex.code)
        logging.debug("  response body: %s", ex.read().decode("utf-8"))
    except urllib.error.URLError as ex:
        logging.error("Request Failed (URLError): %s", ex.reason)
    return resp

def create_access_token(login_data, access_token_create_request):
    """
    Make a request to the create access token API.

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param dict access_token_create_request: Dictionary containing the values for the Access Token.
    :return dict: Dictionary containing the Access Token and information.
    """
    req_url = "/access/api/v1/tokens"
    logging.debug("Posting create token request")
    resp_str = make_api_request(login_data, "POST", req_url, json.dumps(access_token_create_request))
    logging.debug("Result of create_access_token request: %s", resp_str)
    resp_dict = json.loads(resp_str)
    return resp_dict

### CLASSES ###

### MAIN ###
def main():
    parser_description = """
    Create an access token for a user scope with write permissions.
    """

    parser = argparse.ArgumentParser(description = parser_description, formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action = "store_true")
    parser.add_argument("--token", default = os.getenv("ARTIFACTORY_TOKEN", ""),
                        help = "Artifactory auth token to use for requests.  Will use ARTIFACTORY_TOKEN if not specified.")
    parser.add_argument("--host", default = os.getenv("ARTIFACTORY_HOST", ""),
                        help = "Artifactory host URL (e.g. https://artifactory.example.com/) to use for requests.  Will use ARTIFACTORY_HOST if not specified.")

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG if args.verbose else logging.INFO
    )
    logging.debug("Args: %s", args)

    logging.info("Preparing Environment")

    tmp_login_data = {}
    tmp_login_data["token"] = args.token
    tmp_login_data["host"] = args.host

    # Create and log the access token
    access_token_create_request = {
      "username": "danielw-test-write",
      "scope": "applied-permissions/user", # Using the "user" scope for this demo, but the "groups" scope could be used.
      "expires_in": 600,
      "description": "Temporary write token for danielw-test-write",
      "include_reference_token": True,
      "force_revokable": True
    }
    logging.info("Creating Access Token for username: %s", access_token_create_request["username"])

    access_token_create_response = create_access_token(tmp_login_data, access_token_create_request)
    logging.info("Access Token Create Response: %s", access_token_create_response)

if __name__ == "__main__":
    main()
