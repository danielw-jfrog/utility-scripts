#!/usr/bin/env python3

### IMPORTS ###
import argparse
import json
import logging
import os
import urllib.request
import urllib.error
import urllib.parse

### GLOBALS ###
REPO_PREFIX = "coord-perms"
BASE_REMOTE_REPO = "MavenTest"

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

def check_repo_exists(login_data, repo_name):
    """
    Perform an API GET call to see if a repo exists.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param str repo_name: Name of repo to verify existence.
    :return bool: Whether repo exists
    """
    req_url = "/artifactory/api/v2/repositories/{}".format(repo_name)
    req_data = ""
    logging.debug("Checking for repo %s", repo_name)
    result = make_api_request(login_data, 'GET', req_url, req_data)
    logging.debug("  Result: %s", result)
    if (result is not None):
        return True
    return False

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
    if ("projectKey" in repo_definition) and (repo_definition["projectkey"] is not None):
        req_data = "{{\"rclass\":\"local\",\"key\":\"{}\",\"packageType\":\"{}\",\"projectKey\":\"{}\"}}".format(
            repo_definition["name"], repo_definition["type"], repo_definition["project-key"])
    else:
        req_data = "{{\"rclass\":\"local\",\"key\":\"{}\",\"packageType\":\"{}\"}}".format(
            repo_definition["name"], repo_definition["type"])
    logging.info("Creating local repository: %s", repo_definition["name"])
    make_api_request(login_data, 'PUT', req_url, req_data)

def create_virtual_repo(login_data, repo_definition):
    """
    Send the request to create the virtual repo to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param dict repo_definition: Dictionary containing "name", "type", "repos" (list), and (optional) "project-key" of
                                 of the virtual repository to create.
    :return:
    """
    req_url = "/artifactory/api/repositories/{}".format(repo_definition["name"])
    req_data = json.dumps({
        "rclass": "virtual",
        "key": repo_definition["name"],
        "packageType": repo_definition["type"],
        "repositories": repo_definition["repos"]
    })
    if ("projectKey" in repo_definition) and (repo_definition["projectkey"] is not None):
        req_data["projectKey"] = repo_definition["project-key"]
    logging.info("Creating local repository: %s", repo_definition["name"])
    make_api_request(login_data, 'PUT', req_url, req_data)

def check_group_exists(login_data, group_name):
    """
    Perform an API GET call to see if a group exists.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param str group_name: Name of group to verify existence.
    :return bool: Whether repo exists
    """
    req_url = "/access/api/v2/groups/{}".format(group_name)
    req_data = ""
    logging.debug("Checking for group %s", group_name)
    result = make_api_request(login_data, 'GET', req_url, req_data)
    logging.debug("  Result: %s", result)
    if (result is not None):
        return True
    return False

def create_group(login_data, group_name):
    """
    Send the request to create the group to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param dict group_name: Name of group to create.
    :return:
    """
    req_url = "/access/api/v2/groups"
    req_data = json.dumps({
      "name": group_name,
      "description": group_name,
      "auto_join": False,
      "admin_privileges": False
    })
    logging.info("Creating group: %s", group_name)
    make_api_request(login_data, 'POST', req_url, req_data)

def delete_group(login_data, group_name):
    """
    Perform an API DELETE call to remove an existing group.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param str group_name: Name of group to remove.
    :return:
    """
    req_url = "/access/api/v2/groups/{}".format(group_name)
    req_data = ""
    logging.debug("Deleting group %s", group_name)
    result = make_api_request(login_data, 'DELETE', req_url, req_data)
    logging.debug("  Result: %s", result)

def check_perm_target_exists(login_data, perm_target_name):
    """
    Perform an API HEAD call to see if a permission target exists.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param str perm_target_name: Name of permission target to verify existence.
    :return bool: Whether permission target exists
    """
    req_url = "/artifactory/api/v2/security/permissions/{}".format(perm_target_name)
    req_data = ""
    logging.debug("Checking for permission target %s", perm_target_name)
    result = make_api_request(login_data, 'HEAD', req_url, req_data)
    logging.debug("  Result: %s", result)
    if (result is not None):
        return True
    return False

def create_perm_target(login_data, perm_target_definition):
    """
    Send the request to create the permission target to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param dict perm_target_definition: Dictionary containing data for the permission target to create.
    :return:
    """
    req_url = "/artifactory/api/v2/security/permissions/{}".format(perm_target_definition["name"])
    req_data = json.dumps({
      "name": perm_target_definition["name"],
      "repo": {
        "include-patterns": perm_target_definition["include_patterns"],
        "exclude-patterns": [""],
        "repositories": perm_target_definition["repositories"],
        "actions": {
          "groups": {
            perm_target_definition["group_name"]: ["read", "write", "annotate", "delete", "manage", "managedXrayMeta", "distribute"]
          }
        }
      }
    })
    logging.info("Creating permission target: %s", perm_target_definition["name"])
    make_api_request(login_data, 'POST', req_url, req_data)

def delete_perm_target(login_data, perm_target_name):
    """
    Perform an API DELETE call to remove an existing permission target.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param str perm_target_name: Name of permission target to remove.
    :return:
    """
    req_url = "/artifactory/api/v2/security/permissions/{}".format(perm_target_name)
    req_data = ""
    logging.debug("Deleting permission target %s", perm_target_name)
    result = make_api_request(login_data, 'DELETE', req_url, req_data)
    logging.debug("  Result: %s", result)

### CLASSES ###

### MAIN ###
def main():
    parser_description = "description goes here."

    parser = argparse.ArgumentParser(description = parser_description, formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action = "store_true")

    parser.add_argument("--artifactory-token", default = os.getenv("ARTIFACTORY_TOKEN", ""),
                        help = "Artifactory auth token to use for requests.  Will use ARTIFACTORY_TOKEN if not specified.")
    parser.add_argument("--artifactory-host", default = os.getenv("ARTIFACTORY_HOST", ""),
                        help = "Artifactory host URL (e.g. https://artifactory.example.com/) to use for requests.  Will use ARTIFACTORY_HOST if not specified.")

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
    config_data["arti_token"] = str(args.artifactory_token)
    config_data["arti_host"] = str(args.artifactory_host)
    logging.debug("Config Data: %s", config_data)

    # Generate names of repos to be created
    # 10 local repos
    local_repo_names = []
    for i in range(10):
        local_repo_names.append("{}-maven-local-{:03}".format(REPO_PREFIX, i+1))
    logging.info("Local Repo Names: %s", local_repo_names)

    # 10 virtual repos (one for each local)
    virtual_repo_names = []
    for i in range(10):
        virtual_repo_names.append("{}-maven-virt-{:03}".format(REPO_PREFIX, i+1))
    logging.info("Virtual Repo Names: %s", virtual_repo_names)

    # Generate a group for each permissions target to be applied to
    # 1000 groups for each local
    group_names = {}
    for i in range(len(local_repo_names)):
        group_names[local_repo_names[i]] = []
        for j in range(1000):
            group_names[local_repo_names[i]].append("{}-{:03}-{:03}".format(REPO_PREFIX, i+1, j+1))

    # Generate permissions to be applied to each repo
    # 1000 perms for each local
    permission_targets = {}
    for i in range(len(local_repo_names)):
        local_repo = local_repo_names[i]
        permission_targets[local_repo] = []
        for j in range(len(group_names[local_repo])):
            permission_targets[local_repo].append({
                "name": "{}-pt-{:03}-{:03}".format(REPO_PREFIX, i+1, j+1),
                "group_name": group_names[local_repo][j],
                "repositories": [local_repo],
                "include_patterns": ["com/example/maven/{}/**".format(group_names[local_repo][j])]
            })



    # Check for the existence of each local repo.  Create as needed.
    for item in local_repo_names:
        exists = check_repo_exists(config_data, item)
        if (exists):
            logging.debug("Local Repo Exists: %s", item)
        else:
            logging.debug("Local Repo Create: %s", item)
            create_local_repo(config_data, {
                "name": item,
                "type": "maven"
            })

    # Check for the existence of each virtual repo.  Create as needed.
    for i in range(len(virtual_repo_names)):
        exists = check_repo_exists(config_data, virtual_repo_names[i])
        if (exists):
            logging.debug("Virtual Repo Exists: %s", virtual_repo_names[i])
        else:
            logging.debug("Virtual Repo Create: %s", virtual_repo_names[i])
            create_virtual_repo(config_data, {
                "name": virtual_repo_names[i],
                "type": "maven",
                "repos": [local_repo_names[i], BASE_REMOTE_REPO]
            })

    # Check for the existence of each group.  Create as needed.
    for i in range(1, len(local_repo_names)):
        for j in range(1, len(group_names[local_repo_names[i]])):
            group_name = group_names[local_repo_names[i]][j]
            exists = check_group_exists(config_data, group_name)
            if (exists):
                logging.debug("Group exists: %s", group_name)
                # The following was used to clean up the demo instance.
                # delete_group(config_data, group_name)
            else:
                logging.debug("Group create: %s", group_name)
                create_group(config_data, group_name)

    # Check for the existence of each permission target.  Create as needed.
    for i in range(len(local_repo_names)):
        for j in range(len(permission_targets[local_repo_names[i]])):
            perm_target = permission_targets[local_repo_names[i]][j]
            exists = check_perm_target_exists(config_data, perm_target["name"])
            if (exists):
                logging.debug("Permission Target exists: %s", perm_target["name"])
                # The following was used to clean up the demo instance.
                # delete_perm_target(config_data, perm_target["name"])
            else:
                logging.debug("Permission Target create: %s", perm_target["name"])
                create_perm_target(config_data, perm_target)

if __name__ == "__main__":
    main()

