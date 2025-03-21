#!/usr/bin/env python3

### IMPORTS ###
import argparse
import datetime
import json
import logging
import os
import pathlib
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
    req_url = "{}{}".format(login_data["arti_host"], path)
    req_headers = {}
    if is_data_json:
        req_headers["Content-Type"] = "application/json"
    else:
        req_headers["Content-Type"] = "text/plain"
    req_data = data.encode("utf-8") if data is not None else None

    logging.debug("req_url: %s", req_url)
    logging.debug("req_headers: %s", req_headers)
    logging.debug("req_data: %s", req_data)

    req_headers["Authorization"] = "Bearer {}".format(login_data["arti_token"])

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

def create_remote_repo(login_data, repo_key, package_type, repo_url):
    """
    Create a remote repo using the supplied info.
    https://jfrog.com/help/r/jfrog-rest-apis/create-repository

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param str repo_key: String containing the key or name of the remote repo.
    :param str package_type: String containing the package type of the remote repo.
    :param str repo_url: String containing the URL for the remote repo.
    """
    req_json = {
        "key": repo_key,
        "rclass": "remote",
        "packageType": package_type,
        "url": repo_url
    }
    req_data = json.dumps(req_json)
    req_url = "/artifactory/api/repository/{}".format(repo_key)
    logging.debug("PUTing create repo: %s", repo_key)
    resp_str = make_api_request(login_data, "PUT", req_url, req_data)
    logging.debug("  response: %s", resp_str)

### CLASSES ###

### MAIN ###
def main():
    parser_description = """
    Create an access token for a user scope with write permissions.
    """

    parser = argparse.ArgumentParser(description = parser_description, formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action = "store_true")
    parser.add_argument("--dry_run", action = "store_true")

    parser.add_argument("--token", default = os.getenv("ARTIFACTORY_TOKEN", ""),
                        help = "Artifactory auth token to use for requests.  Will use ARTIFACTORY_TOKEN if not specified.")
    parser.add_argument("--host", default = os.getenv("ARTIFACTORY_HOST", ""),
                        help = "Artifactory host URL (e.g. https://artifactory.example.com/) to use for requests.  Will use ARTIFACTORY_HOST if not specified.")

    parser.add_argument("--start_index", type = int, default = 0,
                        help = "Starting entry in the JSON list in the input file.  Defaults to 0.")
    parser.add_argument("--stop_index", type = int, default = -1,
                        help = "Stopping entry in the JSON list in the input file.  Defaults to last.")
    parser.add_argument("input_json", help = "JSON file containing the projects to create.")
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG if args.verbose else logging.INFO
    )
    logging.debug("Args: %s", args)

    logging.info("Preparing Environment")

    config_data = {}
    config_data["dry_run"] = True if args.dry_run else False
    config_data["arti_token"] = str(args.artifactory_token)
    config_data["arti_host"] = str(args.artifactory_host)
    logging.debug("Config Data: %s", config_data)

    # Import the JSON file with the format:
    # [
    #   { "key": "...", "type": "REMOTE", "url": "...", "packageType": "...", "description": "...optional..." },
    #   { "key": "...", "type": "REMOTE", "url": "...", "packageType": "...", "description": "...optional..." },
    #   { "key": "...", "type": "REMOTE", "url": "...", "packageType": "...", "description": "...optional..." },
    #   ...
    # ]
    input_json_path = pathlib.Path(args.input_json)
    output_json_path = pathlib.Path(input_json_path.parent, "{}_new_remotes.json".format(input_json_path.stem))
    with open(input_json_path, 'r') as ij:
        input_data = json.load(ij)

    modified_data = []

    # For each item in the input_data, between the indexes inclusive, create the repo.
    index_limit = len(input_data)
    start_index = 0
    stop_index = index_limit
    if (args.start_index > 0) and (args.start_index < index_limit):
        start_index = args.start_index
    if (args.stop_index >= start_index) and (args.stop_index < index_limit):
        stop_index = args.stop_index
    logging.debug("Using range from %d to %d", start_index, stop_index)
    for i in range(start_index, stop_index):
        # 'i' is the index into the input_data
        tmp_repo_key = input_data[i]["key"]
        tmp_package_type = input_data[i]["packageType"]
        tmp_repo_url = input_data[i]["url"]
        # FIXME: Do we need to collect the results and do something else?
        create_remote_repo(config_data, tmp_repo_key, tmp_package_type, tmp_repo_url)
        # Add an updated version of this entry to the modified data
        modified_data.append({
            "key": tmp_repo_key,
            "type": "REMOTE",
            "url": "{}/artifactory/{}".format(config_data["arti_host"], tmp_repo_key),
            "packageType": tmp_package_type
        })

    # Output the modified data as a JSON file
    if len(modified_data) > 0:
        logging.info("Entries Modified, outputing new JSON")
        with open(output_json_path, 'w') as oj:
            json.dump(modified_data, oj)

if __name__ == "__main__":
    main()
