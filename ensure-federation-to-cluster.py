#!/usr/bin/env python3

### IMPORTS ###
import argparse
import json
import logging
import os
import sys
import urllib.request
import urllib.error
import urllib.parse

### GLOBALS ###

### FUNCTIONS ###
def make_api_request(login_data, method, path, data = None, is_data_json = True, headers = {}):
    """
    Send the request to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param str method: One of "GET", "PUT", or "POST".
    :param str url: URL of the API sans the "host" part.
    :param str data: String containing the data serialized into JSON format.
    :param bool is_data_json: True if the data should be interpretted as application/json, false if text/plain.
    :param dict headers: Dictionary of headers with key as header name and value as header value.
    :return:
    """
    # FIXME: Add query parameters to the function arguments
    req_url = "{}{}".format(login_data["host"], path)
    req_headers = headers
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
    # FIXME: Should make the status code available to the calling method.
    return resp

def get_federated_repositories(login_data):
    """
    Make a request to the repository configuration API.

    :param dict login_data: Dictionary containing "token" and "host" values.
    :return list: List of repository configuration dictionaries.
    """
    req_url = "/artifactory/api/repositories/configurations?repoType=federated"
    logging.debug("Getting federated repository list")
    resp_str = make_api_request(login_data, "GET", req_url)
    logging.debug("Result of get_federated_repositories request: %s", resp_str)
    resp_list = json.loads(resp_str)["FEDERATED"]
    return resp_list

def get_available_federation_clusters(login_data):
    """
    Make a request to the mission control API.

    :param dict login_data: Dictionary containing "token" and "host" values.
    :return list: List of federation clusters dictionaries.
    """
    req_url = "/mc/api/v1/jpds"
    logging.debug("Getting federation cluster list")
    resp_str = make_api_request(login_data, "GET", req_url)
    logging.debug("Result of get_available_federation_clusters request: %s", resp_str)
    resp_list = json.loads(resp_str)
    return resp_list

def update_federated_repository(login_data, partial_repo_config):
    """
    Send the request to update the federated repo to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing login and host values.
    :param dict virtual_repo_config: Dictionary containing partial configuration of the federated repository to update.
                                     https://jfrog.com/help/r/jfrog-rest-apis/repository-configuration-json
    """
    req_url = "/artifactory/api/repositories/{}".format(partial_repo_config["key"])
    req_data = json.dumps(partial_repo_config)
    logging.info("Updating federated repository: %s", partial_repo_config["key"])
    if login_data["dry_run"] == False:
        result = make_api_request(login_data, 'POST', req_url, req_data)
        # FIXME: Handle the failure to update the repo

### CLASSES ###

### MAIN ###
def main():
    parser_description = """
    Ensure all of the federated repositories on the host cluster (JPD) are federated to the second cluster (JPD).
    
    NOTE: This script assumes that Mission Control and Federation Bindings are set between the two clusters.
          This also assumes that the repository names on both clusters will be the same.
    """

    parser = argparse.ArgumentParser(description = parser_description, formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action = "store_true")

    parser.add_argument("--dry-run", action = "store_true",
                        help = "Bypass the changing API calls for verification purposes.")

    # FIXME: Add other arguments here

    parser.add_argument("--artifactory-token", default = os.getenv("ARTIFACTORY_TOKEN", ""),
                        help = "Artifactory auth token to use for requests.  Will use ARTIFACTORY_TOKEN if not specified.")
    parser.add_argument("--artifactory-host", default = os.getenv("ARTIFACTORY_HOST", ""),
                        help = "Artifactory host URL (e.g. https://artifactory.example.com/) to use for requests.  Will use ARTIFACTORY_HOST if not specified.")
    parser.add_argument("--second-cluster-host",
                        help = "The base_url of the second cluster that all of the federated repositories should be federated.")

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(thread)d-%(threadName)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG if args.verbose else logging.INFO
    )
    logging.debug("Args: %s", args)

    # Set up the config data
    logging.debug("Preparing the environment.")
    config_data = {}
    config_data["dry_run"] = True if args.dry_run else False
    config_data["token"] = str(args.artifactory_token)
    config_data["host"] = str(args.artifactory_host)
    logging.debug("Config Data: %s", config_data)

    # FIXME: What second cluster argument validations be here?
    second_cluster = str(args.second_cluster_host)
    if "https://" not in second_cluster and "http://" not in second_cluster:
        logging.error("Second Cluster Host Argument must be a base_url.")
        sys.exit(1)

    # Get a list of the federated repositories.
    fed_repos = get_federated_repositories(config_data)
    logging.debug("Federated Repositories: %s", fed_repos)

    # Get a list of the available clusters.
    # NOTE: There's not a good way to tell if federation bindings have been established with a cluster.
    #       It is assumed that the federation bindings have already been established.
    fed_clusters = get_available_federation_clusters(config_data)
    logging.debug("Available Clusters: %s", fed_clusters)

    # Check if requested second cluster is in the available cluster list.
    second_cluster_base_url = None
    for cluster in fed_clusters:
        if second_cluster in cluster["base_url"]:
            second_cluster_base_url = cluster["base_url"]
    if second_cluster_base_url is None:
        logging.error("Second Cluster Host not found in linked clusters.")
        sys.exit(2)
    logging.debug("Found second cluster base_url: %s", second_cluster_base_url)

    # For each of the repositories, check if the repository is already federated.
    logging.info("Number of federated repositories: %s", len(fed_repos))
    repos_to_update = []
    for repo in fed_repos:
        logging.debug("repo: %s", repo)
        has_second_cluster_member = False
        for member in repo["members"]:
            if second_cluster_base_url in member["url"]:
                has_second_cluster_member = True
        if not has_second_cluster_member:
            repos_to_update.append(repo)
    logging.info("Number of federated repositories to update: %s", len(repos_to_update))

    # For each of the repositories needing update, POST update.
    for repo in repos_to_update:
        repo["members"].append({
            "url": "{}artifactory/{}".format(second_cluster_base_url, repo["key"]),
            "enabled": True
        })
        update_federated_repository(config_data, repo)


if __name__ == "__main__":
    main()

