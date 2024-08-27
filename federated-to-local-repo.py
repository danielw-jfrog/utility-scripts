#!/usr/bin/env python3

### IMPORTS ###
import argparse
import json
import logging
import os
import sys
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

def make_aql_request(login_data, aql_query):
    """
    Form the AQL query into the API request and send that request.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param dict aql_query: Dictionary containing the AQL query parameters.
    :return dict result: Dictionary containing the result of the AQL query, if not None.
    """
    req_url = "/artifactory/api/search/aql"
    req_data = "items.find({}).include({})".format(
        json.dumps(aql_query["find"]),
        ",".join(["\"{}\"".format(item) for item in aql_query["include"]]))
    resp_str = make_api_request(login_data, "POST", req_url, data = req_data, is_data_json = False)
    if resp_str is not None:
        resp_str = json.loads(resp_str)
    return resp_str

def convert_repo_definition_to_local(repo_definition, temporary = False):
    """
    Walk through the repository definition dictionary and make sure that it only includes the keys for a local
    repository.  Also, convert any keys that need converting, such as changing the "rclass" to "local".

    :param dict repo_definition: The repository definition of the source repository, the repository that is being
                                 converted to a local repository.
    :param bool temporary: Whether the resulting repository definition is going to be used for a temporary repository.
                           This sets a number of options to a lower effort mode, such as xray indexing to disabled.
    :return dict local_repo_definition: Returns a dictionary containing the repository definition converted to a local
                                        repository.
    """
    local_repo_definition = {}
    for k in LOCAL_REPO_KEYS:
        if k in repo_definition:
            local_repo_definition[k] = repo_definition[k]
    local_repo_definition["rclass"] = "local"
    if temporary:
        # FIXME: What things can be disabled for the temporary repo?
        local_repo_definition["xrayIndex"] = False
        local_repo_definition["suppressPomConsistencyChecks"] = True
        local_repo_definition["calculateYumMetadata"] = False
        local_repo_definition["enableFileListsIndexing"] = False
    return local_repo_definition

def read_repo(login_data, repo_name):
    """
    Get the definition of the named virtual repository from the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param str repo_name: Name of the virtual repository to query.
    :return str resp_str: Returns the JSON string of the repository definition if it exists, otherwise None.
    """
    req_url = "/artifactory/api/repositories/{}".format(repo_name)
    logging.info("Getting repository data: %s", repo_name)
    resp_str = make_api_request(login_data, "GET", req_url)
    return resp_str

def create_local_repo(login_data, repo_definition):
    """
    Send the request to create the local repo to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param dict repo_definition: Dictionary containing definition of the local repository to create.
                                 https://jfrog.com/help/r/jfrog-rest-apis/repository-configuration-json
    """
    req_url = "/artifactory/api/repositories/{}".format(repo_definition["key"])
    req_data = json.dumps(repo_definition)
    logging.info("Creating local repository: %s", repo_definition["key"])
    result = make_api_request(login_data, 'PUT', req_url, req_data)
    # FIXME: Handle the failure to create the repo

def delete_repo(login_data, repo_name):
    """
    Make the API request to delete the named repo.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param str repo_name: The name of the repository to be deleted.
    """
    req_url = "/artifactory/api/repositories/{}".format(repo_name)
    resp_str = make_api_request(login_data, "DELETE", req_url)
    # FIXME: Handle failed repo delete

def make_item_copy_request(login_data, source_repo, destination_repo, path, name):
    """
    Make a request to the copy API.

    :param dict login_data: Dictionary containing "user", "apikey", and "host" values.
    :param str source_repo: The name of the repository containing the artifact.
    :param str destination_repo: The name of the repository where the artifact will be copied.
    :param str path: The path in the repository where the artifact is located.
    :param str name: The name of the artifact.
    """
    req_url = "/artifactory/api/copy/{}/{}/{}?to=/{}/{}/{}".format(
        source_repo,
        path,
        name,
        destination_repo,
        path,
        name)
    resp_str = make_api_request(login_data, "POST", req_url)
    # FIXME: Handle an failed copy

def copy_artifacts_to_repo(login_data, source_repo_name, destination_repo_name):
    """
    Copy the artifacts from one repo to another.  This will use an AQL request to get a listing of all of the artifacts,
    then walk the listing copying each artifact one-by-one.  This is due to a limitation of the number of artifacts that
    the "built-in" copy API can handle.

    NOTE: This copy method is specifically copying each artifact one-by-one due to the internal limitation of roughly
          50,000 items for a single call to the copy API.  This copy method can be optimized in a few of ways:
          First, any repositories that contain less than 50,000 artifacts could just be copied by one call to the copy
          API for the whole repository.
          Second, for repositories larger then 50,000 artifacts, the one-by-one calls can be threaded, parallelizing
          the requests (up to 30 threads in parallel on a small VM).
          Third, each parallelized request can be made to copy multiple artifacts, likely using the folder structure.

    :param str source_repo_name: String containing the name of the source ("From") repository.
    :param str destination_repo_name: String containing the name of the destination ("To") repository.
    """
    # AQL to get list of artifacts.
    aql_query = {
        "find": {
            "repo": {
                "$eq": str(source_repo_name)
            }
        },
        "include": [
            "path", "name"
        ]
    }
    aql_result = make_aql_request(login_data, aql_query)
    logging.debug("AQL Query Result: %s", aql_result)

    # Call the Copy API for each item in the list.
    tmp_num_total = aql_result["range"]["total"]
    logging.info("Number of artifacts to copy: %d", tmp_num_total)
    tmp_num_copied = 0
    for item in aql_result["results"]:
        make_item_copy_request(login_data, source_repo_name, destination_repo_name, item["path"], item["name"])
        tmp_num_copied = tmp_num_copied + 1
        if (tmp_num_copied % 100) == 0:
            logging.info("Number of artifacts copied: %d (%d)",
                         tmp_num_copied,
                         int(tmp_num_copied * 100 / tmp_num_total))
    logging.info("Number of artifacts copied: %d (%d)",
                 tmp_num_copied,
                 int(tmp_num_copied * 100 / tmp_num_total))

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
    parser.add_argument("--user", default = os.getenv("ARTIFACTORY_USER", ""),
                        help = "Artifactory user to use for requests.  Will use ARTIFACTORY_USER if not specified.")
    parser.add_argument("--apikey", default = os.getenv("ARTIFACTORY_APIKEY", ""),
                        help = "Artifactory apikey to use for requests.  Will use ARTIFACTORY_APIKEY if not specified.")
    parser.add_argument("--host", default = os.getenv("ARTIFACTORY_HOST", ""),
                        help = "Artifactory host URL (e.g. https://artifactory.example.com/) to use for requests.  Will use ARTIFACTORY_HOST if not specified.")

    parser.add_argument("--destination-repo", help = "Local repository where the artifacts will eventually end up.  This defaults to the same value as the source-repo, which causes a two stage copy via a temporary repository.")
    parser.add_argument("--temporary-repo", help = "Temporary repository that will be used if the source and destination repositories have the same name.  This defaults to '<source-repo>-temp'.")
    parser.add_argument("--remove-repos", action = "store_true", help = "Delete the source repo (if different name) and temporary repo (if same name).")

    parser.add_argument("--source-repo", required = True, help = "The federated repository where the artifacts currently exist.")

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG if args.verbose else logging.INFO
    )
    logging.debug("Args: %s", args)

    logging.info("Preparing Environment")
    source_repo_name = args.source_repo
    logging.info("Source Repository: %s", source_repo_name)
    destination_repo_name = args.destination_repo if args.destination_repo else source_repo_name
    logging.info("Destination Repository: %s", destination_repo_name)
    temporary_repo_name = None
    if source_repo_name == destination_repo_name:
        temporary_repo_name = args.temporary_repo if args.temporary_repo else "{}-temp".format(source_repo_name)
        logging.info("Temporary Repository: %s", temporary_repo_name)
        if temporary_repo_name == destination_repo_name:
            # NOTE: This means all three names are the same, which is an error.
            logging.error("All three names are the same, which is invalid.  Exiting.")
            sys.exit(3)

    tmp_login_data = {
        "user": args.user,
        "apikey": args.apikey,
        "host": args.host
    }

    # Gather data from the source repository.
    logging.info("Gathering repo information for the source repo: %s", source_repo_name)
    source_repo_definition_raw = read_repo(tmp_login_data, source_repo_name)
    if source_repo_definition_raw is None:
        # NOTE: This means the source repo doesnt' exist
        logging.error("Source repository doesn't exist.")
        sys.exit(1)
    source_repo_definition = json.loads(source_repo_definition_raw)
    logging.debug("Source Repo Definition: %s", source_repo_definition)

    # If temporary_repo_name:
    if temporary_repo_name is not None:
        # Create the temporary repo as a local repo.  Make sure Xray is disabled
        #    for the temporary repo, as scanning isn't needed for the transfer.
        logging.info("Creating the temporary repo: %s", temporary_repo_name)
        temporary_repo_definition = convert_repo_definition_to_local(source_repo_definition, temporary = True)
        temporary_repo_definition["key"] = str(temporary_repo_name)
        logging.debug("Temporary Repo Definition: %s", temporary_repo_definition)
        create_local_repo(tmp_login_data, temporary_repo_definition)

        # Copy artifacts to temporary repo from source repo.
        logging.info("Copying the artifacts from source repo: %s to temporary repo: %s",
                     source_repo_name,
                     temporary_repo_name)
        copy_artifacts_to_repo(tmp_login_data, source_repo_name, temporary_repo_name)

        # Delete the source repo (source and destination repos have the same name).
        logging.info("Deleting the source repo: %s", source_repo_name)
        delete_repo(tmp_login_data, source_repo_name)

    # Create the destination repo as a local repo.
    logging.info("Creating the destination repo: %s", destination_repo_name)
    destination_repo_definition = convert_repo_definition_to_local(source_repo_definition)
    destination_repo_definition["key"] = str(destination_repo_name)
    logging.debug("Destination Repo Definition: %s", destination_repo_definition)
    create_local_repo(tmp_login_data, destination_repo_definition)

    # If temporary_repo_name:
    if temporary_repo_name is not None:
        # Copy the artifacts to the destination repo from the temporary repo.
        logging.info("Copying the artifacts from temporary repo: %s to destination repo: %s",
                     temporary_repo_name,
                     destination_repo_name)
        copy_artifacts_to_repo(tmp_login_data, temporary_repo_name, destination_repo_name)
    # else:
    else:
        # Copy the artifacts to the destination repo from the source repo.
        logging.info("Copying the artifacts from source repo: %s to destination repo: %s",
                     source_repo_name,
                     destination_repo_name)
        copy_artifacts_to_repo(tmp_login_data, source_repo_name, destination_repo_name)

    # If args.remove_repos:
    if args.remove_repos:
        # Delete the source or temporary repos if they still exist.
        if temporary_repo_name is not None:
            logging.info("Deleteing the temporary repo: %s", temporary_repo_name)
            delete_repo(tmp_login_data, temporary_repo_name)
        else:
            logging.info("Deleteing the source repo: %s", source_repo_name)
            delete_repo(tmp_login_data, source_repo_name)

if __name__ == "__main__":
    main()
