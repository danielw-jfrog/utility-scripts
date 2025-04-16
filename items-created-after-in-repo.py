#!/usr/bin/env python3

### IMPORTS ###
import argparse
import json
import logging
import os
import queue
import threading
import time
import urllib.request
import urllib.error
import urllib.parse

### GLOBALS ###

### FUNCTIONS ###
def make_api_request(login_data, method, path, data = None, is_data_json = True):
    # Send the request to the JFrog Artifactory API.
    req_url = "{}{}".format(login_data["arti_host"], urllib.parse.quote(path, safe="/?=,&"))
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

def make_aql_request(login_data, aql_query):
    """
    Form the AQL query into the API request and send that request.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param dict aql_query: Dictionary containing the AQL query parameters.
    :return dict result: Dictionary containing the result of the AQL query, if not None.
    """
    req_url = "/artifactory/api/search/aql"
    # FIXME: Should add .sort() and .limit() to the AQL request.
    req_data = "{}.find({}).include({}).limit({})".format(
        aql_query["type"],
        json.dumps(aql_query["find"]),
        ",".join(["\"{}\"".format(item) for item in aql_query["include"]]),
        aql_query["limit"]
    )
    resp_str = make_api_request(login_data, "POST", req_url, data = req_data, is_data_json = False)
    if resp_str is not None:
        resp_str = json.loads(resp_str)
    return resp_str

def get_new_artifacts(config_data, after_days_ago, repo_name = None, num_limit = 1000):
    # AQL to get list of artifacts.
    aql_query = {
        "type": "items",
        "find": {
            "created": {
                "$last": "{}days".format(int(after_days_ago))
            }
        },
        "include": [
            "repo",
            "path",
            "name",
            "created"
        ],
        "limit": num_limit
    }
    if repo_name is not None:
        tmp_created = aql_query["find"]["created"]
        aql_query["find"] = {"$and": [{"repo": str(repo_name)}, {"created": tmp_created}]}
    aql_result = make_aql_request(config_data, aql_query)
    logging.debug("AQL Query Result: %s", aql_result)

    tmp_num_total = aql_result["range"]["total"]
    logging.info("Number of new items: %d", tmp_num_total)
    result = []
    for item in aql_result["results"]:
        result.append({
            "repo": item["repo"],
            "path": item["path"],
            "name": item["name"],
            "date": item["created"]
        })
    return result

### CLASSES ###

### MAIN ###
def main():
    parser_description = "Count the number of artifacts recently added."

    parser = argparse.ArgumentParser(description = parser_description, formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action = "store_true")

    parser.add_argument("--num-limit", default = os.getenv("NUM_LIMIT", "1000"),
                        help = "The number of entries to get from the database for processing.  Default is 1000")

    parser.add_argument("--artifactory-token", default = os.getenv("ARTIFACTORY_TOKEN", ""),
                        help = "Artifactory auth token to use for requests.  Will use ARTIFACTORY_TOKEN if not specified.")
    parser.add_argument("--artifactory-host", default = os.getenv("ARTIFACTORY_HOST", ""),
                        help = "Artifactory host URL (e.g. https://artifactory.example.com/) to use for requests.  Will use ARTIFACTORY_HOST if not specified.")

    parser.add_argument("--days-newer-than", default = "7",
                        help = "The maximum age, in days, of items.")
    parser.add_argument("--repo-name",
                        help = "Filter to a specific repo.")
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG if args.verbose else logging.INFO
    )
    logging.debug("Args: %s", args)

    # Set up the config data
    logging.debug("Preparing the environment.")
    config_data = {}
    config_data["arti_token"] = str(args.artifactory_token)
    config_data["arti_host"] = str(args.artifactory_host)
    logging.debug("Config Data: %s", config_data)

    # Get the list of builds to delete
    new_artifacts = get_new_artifacts(
        config_data,
        int(args.days_newer_than),
        args.repo_name if args.repo_name else None,
        args.num_limit
    )

    logging.debug("Artifacts:")
    for item in new_artifacts:
        logging.debug("  %s", item)

if __name__ == "__main__":
    main()
