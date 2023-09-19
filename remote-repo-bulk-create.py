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
    req_url = "/artifactory/api/repositories/{}".format(repo_definition["name"])
    req_data = "{{\"rclass\":\"remote\",\"key\":\"{}\",\"packageType\":\"{}\",\"url\":\"{}\"}}".format(
        repo_definition["name"], repo_definition["type"], repo_definition["remote"])
    logging.info("Creating remote repository: %s", repo_definition["name"])
    make_api_request(login_data, 'PUT', req_url, req_data)

def read_virtual_repo(login_data, repo_name):
    """
    Get the definition of the named virtual repository from the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param str repo_name: Name of the virtual repository to query.
    :return:
    """
    req_url = "/artifactory/api/repositories/{}".format(repo_name)
    logging.info("Getting virtual repository: %s", repo_name)
    resp_str = make_api_request(login_data, 'GET', req_url, None)
    return resp_str

def create_virtual_repo(login_data, repo_definition):
    """
    Send the request to create the remote repo to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param dict repo_definition: Dictionary containing "name", "type", and "remote" URL of the remote repository to create.
    :return:
    """
    req_url = "/artifactory/api/repositories/{}".format(repo_definition["name"])
    req_data_dict = {
        "rclass": "virtual",
        "key": repo_definition["name"],
        "packageType": repo_definition["type"],
        "repositories": repo_definition["repos"]
    }
    req_data = json.dumps(req_data_dict)
    logging.info("Creating virtual repository: %s", repo_definition["name"])
    make_api_request(login_data, 'PUT', req_url, req_data)

def update_virtual_repo(login_data, repo_data):
    """
    Send the request to create the remote repo to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param dict repo_data: Dictionary containing the updated repository configuration data.
    :return:
    """
    req_url = "/artifactory/api/repositories/{}".format(repo_data["key"])
    req_data = json.dumps(repo_data)
    logging.info("Updating virtual repository: %s", repo_data["key"])
    make_api_request(login_data, 'POST', req_url, req_data)

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

    req_pwmanager = urllib.request.HTTPPasswordMgrWithPriorAuth()
    req_pwmanager.add_password(None, login_data["host"], login_data["user"], login_data["apikey"], is_authenticated = True)
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
    Take a JSON file listing the names and URLs of remote repositories as input
    and create the remote repositories in JFrog Artifactory.  If specified, the
    repositories can be added to a virtual repository, either updating an
    existing or creating a new virtual repository.  The following is an example
    of the JSON file contents:
    [
      {
        "name": "reponame-maven-remote",
        "type":"maven",
        "remoteUrl": "https://repo.example.com/snapshots/"
      },
      {
        "name": "reponame2-maven-remote",
        "type":"maven",
        "remoteUrl": "https://repo.example.com/releases/"
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
    parser.add_argument("--virtual_repo_name", default = None,
                        help = "Name of a virtual repository that will be created or updated with the created remote repositories.")
    parser.add_argument("--virtual_repo_type", default = 'generic',
                        help = "Package type of a virtual repository if a virtual repository is to be created.  Defaults to 'generic'.")
    parser.add_argument("input_file", help = "JSON file containing the remote repositories to create.")
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG if args.verbose else logging.INFO
    )
    logging.debug("Args: %s", args)

    logging.info("Preparing Environment")
    repo_list = read_json_file(args.input_file)
    logging.debug("Remote Repository List Length: %d", len(repo_list))

    tmp_login_data = {}
    tmp_login_data["user"] = args.user
    tmp_login_data["apikey"] = args.apikey
    tmp_login_data["host"] = args.host

    logging.info("Creating Repositories")
    for repo in repo_list:
        create_remote_repo(tmp_login_data, repo)

    if args.virtual_repo_name is not None:
        logging.info("Updating Virtual Repository")
        # Check for repo and read current data if exists
        tmp_virtual_repo = read_virtual_repo(tmp_login_data, args.virtual_repo_name)
        logging.debug("Virtual Repository Data: %s", tmp_virtual_repo)
        v_repo_list = [repo["name"] for repo in repo_list]
        if tmp_virtual_repo is None:
            logging.info("Virtual repository doesn't exist.  Creating...")
            v_repo_definition = {
                "name": args.virtual_repo_name,
                "type": args.virtual_repo_type,
                "repos": v_repo_list
            }
            v_repo_definition["type"] = args.virtual_repo_type
            if v_repo_definition["type"] not in REPO_TYPES:
                logging.warning("Virtual Repository Package Type Invalid.  Defaulting to 'generic'.")
                v_repo_definition["type"] = 'generic'
            logging.debug("Virtual repo definition: %s", v_repo_definition)
            create_virtual_repo(tmp_login_data, v_repo_definition)
        else:
            logging.info("Updating virtual repository.")
            v_repo_data = json.loads(tmp_virtual_repo)
            for repo_name in v_repo_list:
                if repo_name not in v_repo_data["repositories"]:
                    v_repo_data["repositories"].append(repo_name)
            logging.debug("Virtual repo data: %s", v_repo_data)
            update_virtual_repo(tmp_login_data, v_repo_data)

if __name__ == "__main__":
    main()
