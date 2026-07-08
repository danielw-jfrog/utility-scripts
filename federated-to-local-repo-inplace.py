#!/usr/bin/env python3

### IMPORTS ###
import argparse
import json
import logging
import os
import urllib.request
import urllib.error

### GLOBALS ###
REPO_TYPES = ["alpine", "cargo", "composer", "bower", "chef", "cocoapods", "conan", "cran", "debian", "docker", "helm",
              "gems", "gitlfs", "go", "gradle", "ivy", "maven", "npm", "nuget", "opkg", "pub", "puppet", "pypi", "rpm",
              "sbt", "swift", "terraform", "vagrant", "yum", "generic"]

LOCAL_REPO_KEYS = ["key", "projectKey", "environments", "rclass", "packageType", "description", "notes",
                   "includesPattern", "excludesPattern", "repoLayoutRef", "debianTrivialLayout", "checksumPolicyType",
                   "handleReleases", "handleSnapshots", "maxUniqueSnapshots", "maxUniqueTags",
                   "snapshotVersionBehavior", "suppressPomConsistencyChecks", "blackedOut", "xrayIndex", "propertySets",
                   "archiveBrowsingEnabled", "calculateYumMetadata", "yumRootDepth", "dockerApiVersion",
                   "enableFileListsIndexing", "optionalIndexCompressionFormats", "downloadRedirect", "cdnRedirect",
                   "blockPushingSchema1", "primaryKeyPairRef", "secondaryKeyPairRef", "priorityResolution"]

### FUNCTIONS ###
def make_api_request(login_data, method, path, data = None, is_data_json = True):
    """
    Send the request to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param str method: One of "GET", "PUT", or "POST".
    :param str path: URL path of the API sans the "host" part.
    :param str data: String containing the data serialized into JSON format.
    :param bool is_data_json: Sets whether the request data will be sent as JSON.
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

    req_pwmanager = urllib.request.HTTPPasswordMgrWithPriorAuth()
    req_pwmanager.add_password(
        None,
        login_data["host"],
        login_data["user"],
        login_data["apikey"],
        is_authenticated = True)
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

def convert_federated_to_local(login_data, repo_key_list):
    """
    Send the request to convert the list of federated repo keys to local repos to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing login and host values.
    :param list repo_key_list: List of federated repository keys that will be converted.
                               https://docs.jfrog.com/artifactory/reference/convertfederatedrepositorytolocal
    """
    req_url = "/artifactory/api//federation/convertToLocal"
    req_data = json.dumps(repo_key_list)
    logging.info("Converting federated repositories to local: %s", req_data)
    if login_data["dry_run"] == False:
        result = make_api_request(login_data, 'POST', req_url, req_data)
        # FIXME: Handle the failure to create the repo

### CLASSES ###

### MAIN ###
def main():
    parser_description = """
    Converts a federated repository to a local repository.  If the federated and
    local repository names are different, create the local repository and copy
    the artifacts to the local repository.  If the repository names are to be
    the same, also delete the federated repository, create another local
    repository with the same name as the federated repository, and copy the
    artifacts to this local repository.
    """

    parser = argparse.ArgumentParser(description = parser_description, formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action = "store_true")
    parser.add_argument("--dry-run", action = "store_true",
                        help = "Bypass the Delete API call for verification purposes.")
    parser.add_argument("--token", default = os.getenv("ARTIFACTORY_TOKEN", ""),
                        help = "Artifactory auth token to use for requests.  Will use ARTIFACTORY_TOKEN if not specified.")
    parser.add_argument("--user", default = os.getenv("ARTIFACTORY_USER", ""),
                        help = "Artifactory user to use for requests.  Will use ARTIFACTORY_USER if not specified.")
    parser.add_argument("--apikey", default = os.getenv("ARTIFACTORY_APIKEY", ""),
                        help = "Artifactory apikey to use for requests.  Will use ARTIFACTORY_APIKEY if not specified.")
    parser.add_argument("--host", default = os.getenv("ARTIFACTORY_HOST", ""),
                        help = "Artifactory host URL (e.g. https://artifactory.example.com/) to use for requests.  Will use ARTIFACTORY_HOST if not specified.")

    parser.add_argument("repos", required = True, help = "List of federated repositories that should be converted back to local repositories.")

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG if args.verbose else logging.INFO
    )
    logging.debug("Args: %s", args)

    logging.info("Preparing Environment")

    login_data = {
        "host": args.host
    }
    if (args.token):
        login_data["token"] = args.token
    if ((args.user) and (args.apikey)):
        login_data["user"] = args.user
        login_data["apikey"] = args.apikey
    login_data["dry_run"] = True if args.dry_run else False

    input_repo_str = str(args.repos)
    input_repo_keys = input_repo_str.split(',')

    convert_federated_to_local(login_data, input_repo_keys)

if __name__ == "__main__":
    main()
