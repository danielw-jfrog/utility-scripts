#!/usr/bin/env python3

### IMPORTS ###
import argparse
import json
import logging
import os
import urllib.request
import urllib.error
import urllib.parse

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

def get_artifacts_by_checksum(login_data, checksum_sha256, repo_list = []):
    """
    Make a request to the search by checksum API.

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param str checksum_sha256: String containing the sha256 to use in the search.
    :param list repo_list: List of strings of repositories to search.
    :return list: List of user dictionaries.
    """
    req_url = "/artifactory/api/search/checksum?sha256={}".format(checksum_sha256)
    if len(repo_list) > 0:
        req_url = "{}&repos={}".format(req_url, ",".join(repo_list))
    logging.debug("Getting artifacts by checksum")
    resp_str = make_api_request(login_data, "GET", req_url)
    logging.debug("Result of search checksum request: %s", resp_str)
    resp_list = json.loads(resp_str)
    return resp_list

### CLASSES ###

### MAIN ###
def main():
    parser_description = """
    Get a list of artifacts that match the provided SHA256 value.
    """

    parser = argparse.ArgumentParser(description = parser_description, formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action = "store_true")
    parser.add_argument("--token", default = os.getenv("ARTIFACTORY_TOKEN", ""),
                        help = "Artifactory auth token to use for requests.  Will use ARTIFACTORY_TOKEN if not specified.")
    parser.add_argument("--host", default = os.getenv("ARTIFACTORY_HOST", ""),
                        help = "Artifactory host URL (e.g. https://artifactory.example.com/) to use for requests.  Will use ARTIFACTORY_HOST if not specified.")

    parser.add_argument("--repo_list", help = "Comma separated list of repository keys that should be searched.")
    parser.add_argument("sha256", help = "SHA256 string that should be used to search for artifacts.")

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

    # Get the list of artifacts for the SHA256
    tmp_repo_list = []
    if args.repo_list:
        tmp_repo_list = args.repo_list.split(",")
    tmp_result = get_artifacts_by_checksum(tmp_login_data, args.sha256, tmp_repo_list)

    logging.info("Result: %s", tmp_result)


if __name__ == "__main__":
    main()
