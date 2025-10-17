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

def get_remote_repo(login_data, repo_key):
    """
    Get a remote repo configuration using the supplied info.
    https://jfrog.com/help/r/jfrog-rest-apis/get-repository-configuration

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param str repo_key: String containing the key or name of the remote repo.
    :return dict: Dictionary containing repository config.
    """
    req_url = "/artifactory/api/repositories/{}".format(repo_key)
    logging.debug("GETing repo config: %s", repo_key)
    resp_str = make_api_request(login_data, "GET", req_url)
    logging.debug("  response: %s", resp_str)
    if resp_str is None:
        return None
    resp_dict = json.loads(resp_str)
    return resp_dict

def update_remote_repo(login_data, repo_key, repo_url, pypi_reg_url = None):
    """
    Update a remote repo using the supplied info.
    https://jfrog.com/help/r/jfrog-rest-apis/?

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param str repo_key: String containing the key or name of the remote repo.
    :param str repo_url: String containing the URL for the remote repo.
    """
    req_json = {
        "key": repo_key,
        "url": repo_url
    }
    if pypi_reg_url is not None:
        req_json["pyPIRegistryUrl"] = pypi_reg_url
    req_data = json.dumps(req_json)
    req_url = "/artifactory/api/repositories/{}".format(repo_key)
    logging.debug("POSTing update repo: %s", repo_key)
    resp_str = make_api_request(login_data, "POST", req_url, req_data)
    logging.debug("  response: %s", resp_str)

### CLASSES ###

### MAIN ###
def main():
    parser_description = """
    Update the remote repos from the JSON with the URLs from the JSON.
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
    parser.add_argument("--repo_prefix", default = "",
                        help = "Add a prefix to the repository name.")
    parser.add_argument("input_json", help = "JSON file containing the projects to update.")
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
    config_data["arti_token"] = str(args.token)
    config_data["arti_host"] = str(args.host)
    logging.debug("Config Data: %s", config_data)

    # Import the JSON file with the format:
    # [
    #   { "key": "...", "type": "REMOTE", "url": "...", "packageType": "...", "description": "...optional..." },
    #   { "key": "...", "type": "REMOTE", "url": "...", "packageType": "...", "description": "...optional..." },
    #   { "key": "...", "type": "REMOTE", "url": "...", "packageType": "...", "description": "...optional..." },
    #   ...
    # ]
    input_json_path = pathlib.Path(args.input_json)
    output_json_path = pathlib.Path(input_json_path.parent, "{}_old_remotes.json".format(input_json_path.stem))
    repo_prefix = str(args.repo_prefix)
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
        tmp_repo_key = "{}{}".format(repo_prefix, input_data[i]["key"])
        tmp_package_type = input_data[i]["packageType"]
        tmp_repo_url = input_data[i]["url"]

        # Get the current repo config to save for later
        tmp_current_config = get_remote_repo(config_data, tmp_repo_key)
        if tmp_current_config is None:
            continue

        # FIXME: Certain repos require special formats for the URL
        #        - NPM requires the artifactory/api/npm/<repo_key> URL
        #        - PyPi requires the non api format for the URL, but needs the
        #             Registry URL set to the api/pypi version.
        # FIXME: Verify other package type URLs
        # FIXME: Should add a username & password/token option as it's usually
        #           needed for access to the curation environment.  Environs for
        #           all repos, but should there be a per repo version in the JSON?

        # Update the repo
        if tmp_package_type in ["pypi", "Pypi", "PYPI"]:
            tmp_pypi_reg = "https://pypi.org"
            if ".jfrog.io" in tmp_repo_url:
                # This is an artifactory smart repo, so make the Registry URL
                # https://xxx.jfrog.io/artifactory/repo-name
                tmp_repo_split = tmp_repo_url.split("/")
                tmp_repo_split.insert(4, "api")
                tmp_repo_split.insert(5, "pypi")
                tmp_repo_split.append("")
                tmp_pypi_reg = "/".join(tmp_repo_split)
            update_remote_repo(config_data, tmp_repo_key, tmp_repo_url, tmp_pypi_reg)
        else:
            update_remote_repo(config_data, tmp_repo_key, tmp_repo_url)

        # Add an updated version of this entry to the modified data
        modified_data.append({
            "key": tmp_repo_key,
            "type": "REMOTE",
            "url": tmp_current_config["url"],
            "packageType": tmp_package_type
        })

    # Output the modified data as a JSON file
    if len(modified_data) > 0:
        logging.info("Entries Modified, outputing new JSON")
        with open(output_json_path, 'w') as oj:
            json.dump(modified_data, oj, indent = 2)

if __name__ == "__main__":
    main()
