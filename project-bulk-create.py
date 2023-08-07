#!/usr/bin/env python3

### IMPORTS ###
import argparse
import json
import logging
import os
import urllib.request
import urllib.error

### GLOBALS ###

### FUNCTIONS ###
def read_json_file(filename):
    """
    Read in and minimal sanitizing of the JSON input file.

    :param str filename: Name of JSON input file to read.
    :return list: List of projects definitions containing values of the projects to create.
    """
    project_list = []
    with open(filename, 'r') as json_file:
        data = json.load(json_file)
        for item in data:
            tmp_project = {}
            tmp_project["name"]: item["name"]
            tmp_project["key"]: item["key"]
            if "description" in item:
                tmp_project["description"] = item["description"]
            if "storage_quota_bytes" in item:
                tmp_project["storage_quota_bytes"] = item["storage_quota_bytes"]
            if "admin_privileges" in item:
                tmp_project["admin_privileges"] = {}
                if "manage_members" in item["admin_privileges"]:
                    tmp_project["admin_privileges"]["manage_members"] = item["admin_privileges"]["manage_members"]
                if "manage_resources" in item["admin_privileges"]:
                    tmp_project["admin_privileges"]["manage_resources"] = item["admin_privileges"]["manage_resources"]
                if "manage_security_assets" in item["admin_privileges"]:
                    tmp_project["admin_privileges"]["manage_security_assets"] = item["admin_privileges"]["manage_security_assets"]
                if "index_resources" in item["admin_privileges"]:
                    tmp_project["admin_privileges"]["index_resources"] = item["admin_privileges"]["index_resources"]
                if "allow_ignore_rules" in item["admin_privileges"]:
                    tmp_project["admin_privileges"]["allow_ignore_rules"] = item["admin_privileges"]["allow_ignore_rules"]
            project_list.append(tmp_project)
    return project_list

def create_project(login_data, project_definition):
    """
    Send the request to create the project to the JFrog Access API.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param dict project_definition: Dictionary containing values of the project to create.
    :return:
    """
    req_url = "/access/api/v1/projects/"
    req_data = json.dumps(project_definition) # NOTE: Just using the JSON directly.
    logging.info("Creating project: %s", project_definition["key"])
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
    Take a JSON file listing the values of projects as input and create the
    projects in JFrog Artifactory.  The following is an example of the JSON file
    contents:
    [
      {
        "name": "project-one",
        "key": "pone",
        "description": "Project One Example",
        "admin_privileges": {
          "manage_members": true,
          "manage_resources": true,
          "manage_security_assets": true,
          "index_resources": true,
          "allow_ignore_rules": true
        },
        "storage_quota_bytes": 0
      },
      {
        "name": "project-two",
        "key": "ptwo",
        "description": "Project Two Testing",
        "admin_privileges": {
          "manage_members": true,
          "manage_resources": true,
          "manage_security_assets": true,
          "index_resources": true,
          "allow_ignore_rules": true
        },
        "storage_quota_bytes": 0
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
    parser.add_argument("input_file", help = "JSON file containing the projects to create.")
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG if args.verbose else logging.INFO
    )
    logging.debug("Args: %s", args)

    logging.info("Preparing Environment")
    project_list = read_json_file(args.input_file)
    logging.debug("Project List Length: %d", len(project_list))

    tmp_login_data = {}
    tmp_login_data["user"] = args.user
    tmp_login_data["apikey"] = args.apikey
    tmp_login_data["host"] = args.host

    logging.info("Creating Projects")
    for project in project_list:
        create_project(tmp_login_data, project)

if __name__ == "__main__":
    main()
