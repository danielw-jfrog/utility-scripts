#!/usr/bin/env python3

### IMPORTS ###
import argparse
import json
import logging
import os
import urllib.request
import urllib.error

### GLOBALS ###
REPO_TYPES = ["alpine","cargo","composer","bower","chef","cocoapods","conan","cran","debian","docker","helm","gems",
              "gitlfs","go","gradle","ivy","maven","npm","nuget","opkg","pub","puppet","pypi","rpm","sbt","swift",
              "terraform","vagrant","yum","generic"]

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

def generate_repo_definitions(prefix = "zzz"):
    """
    Generate a list of repo definitions for the 4096 generic repos.
    :param str prefix: the prefix for the repo name
    :return list: list of dictionaries with repo definitions
    """
    repo_list = []
    for i in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F"]:
        for j in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F"]:
            for k in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F"]:
                repo_list.append({
                    "name": "{}-{}{}{}".format(prefix, i, j, k),
                    "type": "generic"
                })
    return repo_list

def create_local_repo(login_data, repo_definition):
    """
    Send the request to create the local repo to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "token", and "host" values.
    :param dict repo_definition: Dictionary containing "name", "type", and (optional) "project-key" of the local
                                 repository to create.
    :return:
    """
    req_url = "/artifactory/api/repositories/{}".format(repo_definition["name"])
    req_data = ""
    if "project-key" in repo_definition and repo_definition["project-key"] is not None:
        req_data = "{{\"rclass\":\"local\",\"key\":\"{}\",\"packageType\":\"{}\",\"projectKey\":\"{}\"}}".format(
            repo_definition["name"], repo_definition["type"], repo_definition["project-key"])
    else:
        req_data = "{{\"rclass\":\"local\",\"key\":\"{}\",\"packageType\":\"{}\"}}".format(
            repo_definition["name"], repo_definition["type"])
    logging.info("Creating local repository: %s", repo_definition["name"])
    make_api_request(login_data, 'PUT', req_url, req_data)

### CLASSES ###

### MAIN ###
def main():
    parser_description = """
    Generate 4096 generic repos using a prefix and all possible three digit hexadecimal numbers.
    """

    parser = argparse.ArgumentParser(description = parser_description, formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action = "store_true")
    parser.add_argument("--token", default = os.getenv("ARTIFACTORY_TOKEN", ""),
                        help = "Artifactory auth token to use for requests.  Will use ARTIFACTORY_TOKEN if not specified.")
    parser.add_argument("--host", default = os.getenv("ARTIFACTORY_HOST", ""),
                        help = "Artifactory host URL (e.g. https://artifactory.example.com/) to use for requests.  Will use ARTIFACTORY_HOST if not specified.")
    parser.add_argument("--prefix", default = "z-test-repo",
                        help = "Add a prefix to the repository name.")
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

    logging.info("Creating Repositories")
    repo_list = generate_repo_definitions(args.prefix)
    for repo_def in repo_list:
        create_local_repo(tmp_login_data, repo_def)

if __name__ == "__main__":
    main()
