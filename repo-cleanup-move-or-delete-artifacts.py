#!/usr/bin/env python3

### IMPORTS ###
import json
import argparse
import logging
import os
import queue
import threading
import time
import urllib.request
import urllib.error

### GLOBALS ###

### FUNCTIONS ###

# Newer API Handler copied from other script.
def make_api_request(login_data, method, path, data = None, is_data_json = True):
    # Send the request to the JFrog Artifactory API.
    req_url = "{}{}".format(login_data["arti_host"], path)
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
    # Form the AQL query into the API request and send that request.
    req_url = "/artifactory/api/search/aql"
    # FIXME: Should add .sort() and .limit() to the AQL request.
    req_data = "{}.find({}).include({})".format(
        aql_query["type"],
        json.dumps(aql_query["find"]),
        ",".join(["\"{}\"".format(item) for item in aql_query["include"]]))
    resp_str = make_api_request(login_data, "POST", req_url, data = req_data, is_data_json = False)
    if resp_str is not None:
        resp_str = json.loads(resp_str)
    return resp_str

def create_directory(login_data, directory_path):
    # Make a request to download the artifact from Artifactory.
    req_url = "/artifactory/{}".format(directory_path)
    logging.debug("Creating directory %s", directory_path)
    if login_data["dry_run"] == False:
        resp_str = make_api_request(login_data, "PUT", req_url)
        logging.debug("Result of create_directory request: %s", resp_str)

def copy_artifact(login_data, old_artifact_path, new_artifact_path):
    # Make a request to download the artifact from Artifactory.
    req_url = "/artifactory/api/copy/{}?to=/{}".format(old_artifact_path, new_artifact_path)
    logging.debug("Copying the artifact from %s to %s", old_artifact_path, new_artifact_path)
    if login_data["dry_run"] == False:
        resp_str = make_api_request(login_data, "POST", req_url)
        logging.debug("Result of copy artifact request: %s", resp_str)

def move_artifact(login_data, old_artifact_path, new_artifact_path):
    # Make a request to download the artifact from Artifactory.
    req_url = "/artifactory/api/move/{}?to=/{}".format(old_artifact_path, new_artifact_path)
    logging.debug("Moving the artifact from %s to %s", old_artifact_path, new_artifact_path)
    if login_data["dry_run"] == False:
        resp_str = make_api_request(login_data, "POST", req_url)
        logging.debug("Result of move artifact request: %s", resp_str)

def delete_artifact(login_data, artifact_path):
    # Make a request to download the artifact from Artifactory
    req_url = "/artifactory/{}".format(artifact_path)
    logging.debug("Deleting artifact %s", artifact_path)
    if login_data["dry_run"] == False:
        resp_str = make_api_request(login_data, "DELETE", req_url)
        logging.debug("Result of delete_artifact request: %s", resp_str)

def get_artifact_list(login_data, remote_repo_name):
    """
    Use an AQL request to get a listing of all of the artifacts, then walk the listing copying each artifact one-by-one.
    This is due to a limitation of the number of artifacts that the "built-in" copy and move APIs can handle.

    NOTE: This copy method is specifically copying each artifact one-by-one due to the internal limitation of roughly
          50,000 items for a single call to the copy API.  This copy method can be optimized in a few of ways:
          First, any repositories that contain less than 50,000 artifacts could just be copied by one call to the copy
          API for the whole repository.
          Second, for repositories larger then 50,000 artifacts, the one-by-one calls can be threaded, parallelizing
          the requests (up to 30 threads in parallel on a small VM).
          Third, each parallelized request can be made to copy multiple artifacts, likely using the folder structure.
    """
    # AQL to get list of artifacts.
    aql_query = {
        "find": {
            "repo": {
                "$eq": "{}".format(str(remote_repo_name))
            }
        },
        "include": [
            "path", "name"
        ],
        "type": "items"
    }
    aql_result = make_aql_request(login_data, aql_query)
    logging.debug("AQL Query Result: %s", aql_result)

    # Call the Copy API for each item in the list.
    tmp_num_total = aql_result["range"]["total"]
    logging.info("Number of artifacts: %d", tmp_num_total)
    result = []
    for item in aql_result["results"]:
        # item["path"], item["name"]
        result.append({
            "repo": "{}".format(str(remote_repo_name)),
            "path": item["path"],
            "name": item["name"]
        })
    return result

### CLASSES ###
class ThreadWrapper:
    def __init__(self, input_queue, other_data, number_threads, thread_class):
        self.logger = logging.getLogger(type(self).__name__)
        self.input_queue = input_queue
        self.other_data = other_data
        self.number_threads = number_threads
        self.thread_class = thread_class
        self._threads = []

    def start_threads(self):
        self.logger.debug("Starting the threads.")
        for count in range(self.number_threads):
            self._threads.append(self.thread_class(self.input_queue, self.other_data))
        for thread in self._threads:
            thread.start()

    def stop_threads(self):
        self.logger.debug("Stopping the threads.")
        for thread in self._threads:
            thread.stop()

    def any_threads_alive(self):
        for thread in self._threads:
            if thread.is_alive():
                return True
        return False

    def join_threads(self):
        self.logger.debug("Joining threads and waiting for them to finish.")
        for thread in self._threads:
            thread.join()

class ArtifactMover(threading.Thread):
    def __init__(self, input_queue, login_data):
        super().__init__()
        self.logger = logging.getLogger(type(self).__name__)
        self.login_data = login_data
        self._shutdown = False
        # Input Queue Items: {"repo": "<repo_name>", "path": "<artifact_path>", "name": "<artifact_name>"}
        self._input_queue = input_queue

    def run(self):
        self.logger.debug("Starting the ArtifactMover thread.")
        while not self._shutdown:
            # Get a file_meta from the queue
            try:
                item = self._input_queue.get_nowait()
            except queue.Empty:
                self.logger.debug("No more work, shutting down.")
                self.stop()
                break # Force the while loop to end.

            old_artifact_path = "{}/{}/{}".format(item["repo"], item["path"], item["name"])
            new_artifact_path = "{}/{}/{}".format(self.login_data["move_to_repo"], item["path"], item["name"])
            new_directory = "{}/{}".format(self.login_data["move_to_repo"], item["path"])

            create_directory(self.login_data, new_directory)
            move_artifact(self.login_data, old_artifact_path, new_artifact_path)

            self._input_queue.task_done()
        self.logger.debug("Ending the ArtifactMover thread.")

    def stop(self):
        self.logger.debug("Shutting down the ArtifactMover thread.")
        self._shutdown = True

class ArtifactDeleter(threading.Thread):
    def __init__(self, input_queue, login_data):
        super().__init__()
        self.logger = logging.getLogger(type(self).__name__)
        self.login_data = login_data
        self._shutdown = False
        # Input Queue Items: {"repo": "<repo_name>", "path": "<artifact_path>", "name": "<artifact_name>"}
        self._input_queue = input_queue

    def run(self):
        self.logger.debug("Starting the ArtifactDeleter thread.")
        while not self._shutdown:
            # Get a file_meta from the queue
            try:
                item = self._input_queue.get_nowait()
            except queue.Empty:
                self.logger.debug("No more work, shutting down.")
                self.stop()
                break # Force the while loop to end.

            artifact_path = "{}/{}/{}".format(item["repo"], item["path"], item["name"])

            delete_artifact(self.login_data, artifact_path)

            self._input_queue.task_done()
        self.logger.debug("Ending the ArtifactDeleter thread.")

    def stop(self):
        self.logger.debug("Shutting down the ArtifactDeleter thread.")
        self._shutdown = True

### MAIN ###
def main():
    parser_description = "Move or delete the contents of remote repositories."

    parser = argparse.ArgumentParser(description = parser_description, formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action = "store_true")

    parser.add_argument("--dry-run", action = "store_true",
                        help = "Bypass the Delete API call for verification purposes.")

    parser.add_argument("--num-threads", default = os.getenv("NUM_THREADS", "3"),
                        help = "The number of threads to use for making API calls.  Default is 3")

    parser.add_argument("--token", default = os.getenv("ARTIFACTORY_TOKEN", ""),
                        help = "Artifactory auth token to use for requests.  Will use ARTIFACTORY_TOKEN if not specified.")
    parser.add_argument("--host", default = os.getenv("ARTIFACTORY_HOST", ""),
                        help = "Artifactory host URL (e.g. https://artifactory.example.com/) to use for requests.  Will use ARTIFACTORY_HOST if not specified.")

    parser.add_argument("--move-to-repo",
                        help = "Repository to move the contents of the remote repositories into.  If not specified, the contents will be deleted.")
    parser.add_argument("repos",
                        help = "Comma separated list of repositories to cleanup up.  If remote repos are to be cleaned up, please use the -cache repository.")

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG if args.verbose else logging.INFO
    )
    logging.debug("Args: %s", args)

    logging.info("Preparing Environment")

    config_data = {}
    config_data["dry_run"] = True if args.dry_run else False
    config_data["arti_token"] = args.token
    config_data["arti_host"] = args.host
    if args.move_to_repo:
        config_data["move_to_repo"] = str(args.move_to_repo)

    # Split the list of remote repos on commas and check number specified
    repo_list = str(args.repos).split(',')

    # Get the list of files in each of the caches in the remote repos
    artifacts_to_process = queue.Queue()
    for item in repo_list:
        remote_repo_artifacts = get_artifact_list(config_data, item.strip())
        for rral_item in remote_repo_artifacts:
            artifacts_to_process.put(rral_item)

    # Create the threads that will process the artifacts
    logging.debug("Starting threads.")
    wrapper = None
    if args.move_to_repo:
        wrapper = ThreadWrapper(artifacts_to_process, config_data, int(args.num_threads), ArtifactMover)
    else:
        wrapper = ThreadWrapper(artifacts_to_process, config_data, int(args.num_threads), ArtifactDeleter)
    wrapper.start_threads()

    # Idle while the threads are working.
    while wrapper.any_threads_alive():
        try:
            time.sleep(0.1)
        except KeyboardInterrupt:
            logging.warning("KeyboardInterrupt, stopping threads")
            wrapper.stop_threads()

    # Wait for the threads to finish
    logging.debug("Waiting for threads to finish.")
    wrapper.join_threads()
    logging.debug("Threads have completed.")

if __name__ == "__main__":
    main()
