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
    :return list: List of repository definitions containing "name", "type", and "remote" URL values of the remote repositories to create.
    """
    repo_list = []
    with open(filename, 'r') as json_file:
        data = json.load(json_file)
        for item in data:
            tmp_type = "generic"
            if "type" in item.keys():
                if item["type"] in REPO_TYPES:
                    tmp_type = item["type"]
            repo_list.append({
                "name": item["name"],
                "type": tmp_type,
                "remote": item["remoteUrl"]
            })
    return repo_list

def create_remote_repo(login_data, repo_definition):
    """
    Send the request to create the remote repo to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param dict repo_definition: Dictionary containing "name", "type", and "remote" URL of the remote repository to create.
    :return:
    """
    req_url = "{}/artifactory/api/repositories/{}".format(login_data["host"], repo_definition["name"])
    req_headers = {"Content-Type": "application/json"}
    req_data = "{{\"rclass\":\"remote\",\"key\":\"{}\",\"packageType\":\"{}\",\"url\":\"{}\"}}".format(
        repo_definition["name"], repo_definition["type"], repo_definition["remote"]).encode("utf-8")

    logging.debug("req_url: %s", req_url)
    logging.debug("req_headers: %s", req_headers)
    logging.debug("req_data: %s", req_data)

    req_pwmanager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    req_pwmanager.add_password(None, login_data["host"], login_data["user"], login_data["apikey"])
    req_handler = urllib.request.HTTPBasicAuthHandler(req_pwmanager)
    req_opener = urllib.request.build_opener(req_handler)
    urllib.request.install_opener(req_opener)

    request = urllib.request.Request(req_url, data = req_data, headers = req_headers, method = 'PUT')
    try:
        with urllib.request.urlopen(request) as response:
            # Check the status and log
            # NOTE: response.status for Python >=3.9, change to response.code if Python <=3.8
            logging.debug("  Response Status: %d, Response Body: %s", response.status, response.read())
            logging.info("Repo %s created", repo_definition["name"])
    except urllib.error.HTTPError as ex:
        if ex.code == 400:
            logging.warning("Repo %s already exists", repo_definition["name"])
        else:
            logging.warning("Unknown error (%d) creating repo %s", ex.code, repo_definition["name"])
        logging.debug("  response body: %s", ex.read())
    except urllib.error.URLError as ex:
        logging.error("Request Failed (URLError): %s", ex.reason)

### CLASSES ###

### MAIN ###
def main():
    parser_description = """
    Take a JSON file listing the names and URLs of remote repositories as input
    and create the remote repositories in JFrog Artifactory.  The following is
    an example of the JSON file contents:
    [
      {"name": "reponame-maven-remote", "remoteUrl": "https://repo.example.com/snapshots/"},
      {"name": "reponame2-maven-remote", "remoteUrl": "https://repo.example.com/releases/"},
      ...
    ]
    """

    parser = argparse.ArgumentParser(description = parser_description)
    parser.add_argument("-v", "--verbose", action = "store_true")
    parser.add_argument("--user", default = os.getenv("ARTIFACTORY_USER", ""),
                        help = "Artifactory user to use for requests.  Will use ARTIFACTORY_USER if not specified.")
    parser.add_argument("--apikey", default = os.getenv("ARTIFACTORY_APIKEY", ""),
                        help = "Artifactory apikey to use for requests.  Will use ARTIFACTORY_APIKEY if not specified.")
    parser.add_argument("--host", default = os.getenv("ARTIFACTORY_HOST", ""),
                        help = "Artifactory host URL (e.g. https://artifactory.example.com/) to use for requests.  Will use ARTIFACTORY_HOST if not specified.")
    parser.add_argument("input_file", help = "JSON file containing the remote repositories to create.")
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG if args.verbose else logging.INFO
    )

    logging.info("Preparing Environment")
    repo_list = read_json_file(args.input_file)
    logging.debug("Remote Repository List Length: %d", len(repo_list))

    tmp_login_data = {}
    tmp_login_data["user"] = args.user
    tmp_login_data["apikey"] = args.apikey
    tmp_login_data["host"] = args.host

    logging.info("Creating repositories")
    for repo in repo_list:
        create_remote_repo(tmp_login_data, repo)

if __name__ == "__main__":
    main()
