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
def read_json_file(filename):
    """
    Read in and minimal sanitizing of the JSON input file.

    :param str filename: Name of JSON input file to read.
    :return list: List of repository definitions containing "name", "type", and (optional) "project-key" of the local
                  repositories to create.
    """
    repo_list = []
    with open(filename, 'r') as json_file:
        data = json.load(json_file)
        for item in data:
            tmp_type = "generic"
            tmp_pkey = None
            if "type" in item.keys():
                if item["type"] in REPO_TYPES:
                    tmp_type = item["type"]
            if "project-key" in item.keys():
                tmp_pkey = item["project-key"]
            repo_list.append({
                "name": item["name"],
                "type": tmp_type,
                "project-key": tmp_pkey
            })
    return repo_list

def create_local_repo(login_data, repo_definition):
    """
    Send the request to create the local repo to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param dict repo_definition: Dictionary containing "name", "type", and (optional) "project-key" of the local
                                 repository to create.
    :return:
    """
    req_url = "/artifactory/api/repositories/{}".format(repo_definition["name"])
    req_data = ""
    if repo_definition["projectkey"] is not None:
        req_data = "{{\"rclass\":\"local\",\"key\":\"{}\",\"packageType\":\"{}\",\"projectKey\":\"{}\"}}".format(
            repo_definition["name"], repo_definition["type"], repo_definition["project-key"])
    else:
        req_data = "{{\"rclass\":\"local\",\"key\":\"{}\",\"packageType\":\"{}\"}}".format(
            repo_definition["name"], repo_definition["type"])
    logging.info("Creating local repository: %s", repo_definition["name"])
    make_api_request(login_data, 'PUT', req_url, req_data)

def make_api_request(login_data, method, path, data):
    """
    Send the request to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param str method: One of "GET", "PUT", or "POST".
    :param str url: URL of the API sans the "host" part.
    :param str data: String containing the data serialized into JSON format.
    :return:
    """
    req_url = "{}{}".format(login_data["host"], path)
    req_headers = {"Content-Type": "application/json"}
    req_data = data.encode("utf-8") if data is not None else None

    logging.debug("req_url: %s", req_url)
    logging.debug("req_headers: %s", req_headers)
    logging.debug("req_data: %s", req_data)

    req_pwmanager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    req_pwmanager.add_password(None, login_data["host"], login_data["user"], login_data["apikey"])
    req_handler = urllib.request.HTTPBasicAuthHandler(req_pwmanager)
    req_opener = urllib.request.build_opener(req_handler)
    urllib.request.install_opener(req_opener)

    request = urllib.request.Request(req_url, data = req_data, headers = req_headers, method = method)
    resp = None
    try:
        with urllib.request.urlopen(request) as response:
            # Check the status and log
            # NOTE: response.status for Python >=3.9, change to response.code if Python <=3.8
            resp = response.read().decode("utf-8")
            logging.debug("  Response Status: %d, Response Body: %s", response.status, resp)
            logging.info("Repository operation successful")
    except urllib.error.HTTPError as ex:
        logging.warning("Error (%d) for repository operation", ex.code)
        logging.debug("  response body: %s", ex.read().decode("utf-8"))
    except urllib.error.URLError as ex:
        logging.error("Request Failed (URLError): %s", ex.reason)
    return resp

### CLASSES ###

### MAIN ###
def main():
    parser_description = """
    Take a JSON file listing the names and (optional) project key of local
    repositories as input and create the local repositories in JFrog
    Artifactory.  The following is an example of the JSON file contents:
    [
      {
        "name": "reponame-docker-local",
        "type":"docker",
        "project-key": "PO"
      },
      {
        "name": "reponame2-maven-local",
        "type":"maven"
      },
      ...
    ]
    """

    parser = argparse.ArgumentParser(description = parser_description, formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action = "store_true")
    parser.add_argument("--user", default = os.getenv("ARTIFACTORY_USER", ""),
                        help = "Artifactory user to use for requests.  Will use ARTIFACTORY_USER if not specified.")
    parser.add_argument("--apikey", default = os.getenv("ARTIFACTORY_APIKEY", ""),
                        help = "Artifactory apikey to use for requests.  Will use ARTIFACTORY_APIKEY if not specified.")
    parser.add_argument("--host", default = os.getenv("ARTIFACTORY_HOST", ""),
                        help = "Artifactory host URL (e.g. https://artifactory.example.com/) to use for requests.  Will use ARTIFACTORY_HOST if not specified.")
    parser.add_argument("input_file", help = "JSON file containing the local repositories to create.")
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG if args.verbose else logging.INFO
    )
    logging.debug("Args: %s", args)

    logging.info("Preparing Environment")
    repo_list = read_json_file(args.input_file)
    logging.debug("Local Repository List Length: %d", len(repo_list))

    tmp_login_data = {}
    tmp_login_data["user"] = args.user
    tmp_login_data["apikey"] = args.apikey
    tmp_login_data["host"] = args.host

    logging.info("Creating Repositories")
    for repo in repo_list:
        create_local_repo(tmp_login_data, repo)

if __name__ == "__main__":
    main()
