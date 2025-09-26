#!/usr/bin/env python3

### IMPORTS ###
import argparse
import copy
import json
import logging
import os
import sys
import urllib.request
import urllib.error

### GLOBALS ###
# REPO_TYPES = ["alpine", "cargo", "composer", "bower", "chef", "cocoapods", "conan", "cran", "debian", "docker", "helm",
#               "gems", "gitlfs", "go", "gradle", "ivy", "maven", "npm", "nuget", "opkg", "pub", "puppet", "pypi", "rpm",
#               "sbt", "swift", "terraform", "vagrant", "yum", "generic"]

# LOCAL_REPO_KEYS = ["key", "projectKey", "environments", "rclass", "packageType", "description", "notes",
#                    "includesPattern", "excludesPattern", "repoLayoutRef", "debianTrivialLayout", "checksumPolicyType",
#                    "handleReleases", "handleSnapshots", "maxUniqueSnapshots", "maxUniqueTags",
#                    "snapshotVersionBehavior", "suppressPomConsistencyChecks", "blackedOut", "xrayIndex", "propertySets",
#                    "archiveBrowsingEnabled", "calculateYumMetadata", "yumRootDepth", "dockerApiVersion",
#                    "enableFileListsIndexing", "optionalIndexCompressionFormats", "downloadRedirect", "cdnRedirect",
#                    "blockPushingSchema1", "primaryKeyPairRef", "secondaryKeyPairRef", "priorityResolution"]

FED_REPO_KEYS = ["key", "projectKey", "environments", "rclass", "packageType", "members", "description", "proxy",
                 "disableProxy", "notes", "includePattern", "excludePattern", "repoLayoutRef", "debianTrivialLayout",
                 "checksumPolicyType", "handleReleases", "handleSnapshots", "maxUniqueSnapshots", "maxUniqueTags",
                 "snapshotVersionBehavior", "suppressPomConsistencyChecks", "blackedOut", "xrayIndex", "propertySets",
                 "archiveBrowsingEnabled", "calculateYumMetadata", "yumRootDepth", "dockerApiVersion",
                 "enableFileListsIndexing", "optionalIndexCompressionFormats", "downloadRedirect", "cdnRedirect",
                 "blockPushingSchema1", "primaryKeyPairRef", "secondaryKeyPairRef", "priorityResolution"]

### FUNCTIONS ###
def make_api_request(login_data, method, path, data = None, is_data_json = True):
    """
    Send the request to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "host" and ("user", "apikey") or "token" values.
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

    if("token" in login_data):
        req_headers["Authorization"] = "Bearer {}".format(login_data["token"])
    elif("apikey" in login_data):
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

def get_repository_configurations(login_data):
    """
    Get the configuration list for all the repositories from the JFrog Artifactory API.

    :param dict login_data: Dictionary containing login and host values.
    :return dict configuration_list: Returns a dict of lists of dicts containing the configurations of all of the
                                     repositories grouped by repository type (e.g. local, remote, etc).
    """
    req_url = "/artifactory/api/repositories/configurations"
    logging.info("Getting repository configurations")
    resp_str = make_api_request(login_data, "GET", req_url)
    logging.debug("Result of get_repository_configurations request: %s", resp_str)
    resp_dict = json.loads(resp_str)
    return resp_dict

def create_federated_repository(login_data, federated_repo_config):
    """
    Send the request to create the federated repo to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing login and host values.
    :param dict federated_repo_config: Dictionary containing configuration of the federated repository to create.
                                       https://jfrog.com/help/r/jfrog-rest-apis/repository-configuration-json
    """
    req_url = "/artifactory/api/repositories/{}".format(federated_repo_config["key"])
    req_data = json.dumps(federated_repo_config)
    logging.info("Creating federated repository: %s", federated_repo_config["key"])
    if login_data["dry_run"] == False:
        result = make_api_request(login_data, 'PUT', req_url, req_data)
        # FIXME: Handle the failure to create the repo

def update_virtual_repository(login_data, virtual_repo_config):
    """
    Send the request to update the virtual repo to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing login and host values.
    :param dict virtual_repo_config: Dictionary containing configuration of the virtual repository to update.
                                     https://jfrog.com/help/r/jfrog-rest-apis/repository-configuration-json
    """
    req_url = "/artifactory/api/repositories/{}".format(virtual_repo_config["key"])
    req_data = json.dumps(virtual_repo_config)
    logging.info("Creating federated repository: %s", virtual_repo_config["key"])
    if login_data["dry_run"] == False:
        result = make_api_request(login_data, 'POST', req_url, req_data)
        # FIXME: Handle the failure to create the repo

def add_federated_repo_to_virtual_repo(virtual_repo_config, federated_repo_key):
    """
    Output an updated virtual_repo_config with the federated repository key prepended to the repositories list.

    :param dict virtual_repo_config: The repository configuration of the virtual repository that is to be updated.
    :param str federated_repo_key: The repository key of the federated repository that is to be inserted.
    :return dict updated_virtual_repo_config: The updated virtual repository config
    """
    updated_virt_repo = copy.deepcopy(virtual_repo_config)
    updated_virt_repo["repositories"].insert(0, federated_repo_key)
    updated_virt_repo["defaultDeploymentRepo"] = federated_repo_key
    return updated_virt_repo

def convert_local_repo_config_to_federated(local_repo_config):
    """
    Walk through the repository configuration dictionary and make sure that it only includes the keys for a federated
    repository.  Also, convert any keys that need converting, such as changing the "rclass" to "federated".

    :param dict local_repo_config: The repository configuration of the source local repository, the repository
                                   configuration that is being converted to a federated repository.
    :return dict federated_repo_config: Returns a dictionary containing the repository configuration converted to a
                                        federated repository.
    """
    federated_repo_config = {}
    for k in FED_REPO_KEYS:
        if k in local_repo_config:
            federated_repo_config[k] = local_repo_config[k]
    federated_repo_config["rclass"] = "federated"
    return federated_repo_config

### CLASSES ###

### MAIN ###
def main():
    parser_description = """
    Makes a Federated Repository for each Local Repository, then add the new
    repository to the corresponding Virtual Repository.
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

    # FIXME: Add a dry-run option

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
    if(args.token):
        login_data["token"] = args.token
    if((args.user) and (args.apikey)):
        login_data["user"] = args.user
        login_data["apikey"] = args.apikey
    login_data["dry_run"] = True if args.dry_run else False

    # Get all of the repository configurations
    all_repos = get_repository_configurations(login_data)

    # Make a list of all of the locals with their configurations and prepared federated configurations
    local_repos = {}
    for repo in all_repos["LOCAL"]:
        logging.debug("Preparing Repo Key: %s", repo["key"])
        local_repos[repo["key"]] = {
            "local_config": repo,
            "virtuals": [],
            "federated_key": repo["key"],
            "federated_config": convert_local_repo_config_to_federated(repo)
        }

        # If federated_key ends in "-local", then remove.  Append "-fed"
        local_repos[repo["key"]]["federated_key"] = local_repos[repo["key"]]["federated_key"].removesuffix("-local")
        local_repos[repo["key"]]["federated_key"] = local_repos[repo["key"]]["federated_key"].__add__("-fed")
        # Update the key in the federated config
        local_repos[repo["key"]]["federated_config"]["key"] = local_repos[repo["key"]]["federated_key"]
        logging.debug("  New Federated Key: %s", local_repos[repo["key"]]["federated_key"])

    # Check each Virtual to find the associated locals
    for vrepo in all_repos["VIRTUAL"]:
        logging.debug("Preparing Virtual Repo Key: %s", vrepo["key"])
        logging.debug("  contained repository list: %s", vrepo["repositories"])
        for arepo in vrepo["repositories"]:
            if arepo in local_repos:
                logging.debug("  Found associated Local Repo Key: %s", arepo)
                local_repos[arepo]["virtuals"].append(add_federated_repo_to_virtual_repo(vrepo, local_repos[arepo]["federated_key"]))

    # For each local, create the associated federated if it doesn't already exist
    fed_repo_keys = []
    for frepo in all_repos["FEDERATED"]:
        fed_repo_keys.append(frepo["key"])

    for repo_key in local_repos:
        if local_repos[repo_key]["federated_key"] not in fed_repo_keys:
            # Federated repo doesn't exist, so create it
            logging.debug("Creating Federated Repo Key: %s", local_repos[repo_key]["federated_key"])
            create_federated_repository(login_data, local_repos[repo_key]["federated_config"])
        else:
            logging.debug("Federated Repo already exists: %s", local_repos[repo_key]["federated_key"])

    # For each local, update the associated virtual with the new federated repo
    for lrepo_key in local_repos:
        for vrepo in local_repos[lrepo_key]["virtuals"]:
            logging.debug("Updating Repo Key: %s", vrepo["key"])
            update_virtual_repository(login_data, vrepo)


if __name__ == "__main__":
    main()
