#!/usr/bin/env python3

# This script requires the 'oracledb' driver that can be installed via 'pip install --upgrade oracledb'

# The following is the query that this script is based around:
#   SELECT b.build_name, b.build_number, b.build_date
#   FROM builds as b
# 	JOIN build_modules as bm ON bm.build_id = b.build_id
# 	JOIN build_artifacts as ba ON ba.module_id = bm.module_id
# 	WHERE NOT EXISTS (
# 		SELECT '?' FROM nodes n WHERE n.md5_actual = ba.md5
# 	);

### IMPORTS ###
import argparse
import logging
import os
import queue
import threading
import time
import urllib.request
import urllib.error

import oracledb

### GLOBALS ###

### FUNCTIONS ###
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

def get_empty_builds(config_data):
    statement = """
SELECT b.build_name, b.build_number, b.build_date
FROM builds as b
JOIN build_modules as bm ON bm.build_id = b.build_id
JOIN build_artifacts as ba ON ba.module_id = bm.module_id
WHERE NOT EXISTS (
    SELECT '?' FROM nodes n WHERE n.md5_actual = ba.md5
)
"""
    dbconn = config_data["db_connection"]
    cursor = dbconn.cursor()
    cursor.execute(statement)
    rows = cursor.fetchmany(size = 10000)
    logging.debug("Empty Builds: %s", rows)
    result = []
    for row in rows:
        result.append({
            "name": row.build_name,
            "number": row.build_number,
            "date": row.build_date
        })
    return result

def reorganise_builds(builds_to_delete_list):
    # Reorganise the list to make the API calls more efficient
    builds_to_delete = {}
    for item in builds_to_delete_list:
        if item["name"] not in builds_to_delete:
            builds_to_delete[item["name"]] = {
                "name": item["name"],
                "numbers": set()
            }
        builds_to_delete[item["name"]]["numbers"].add(str(item["number"]))
    return builds_to_delete

def del_empty_build(login_data, build_to_delete):
    # build_to_delete contains a dict: { "name": "<build_name>", "numbers": "<set_of_numbers>" }
    number_str = ",".join(build_to_delete["numbers"])

    req_url = "/artifactory/api/build/{}?buildNumbers={}".format(build_to_delete["name"], number_str)
    logging.debug("Deleting builds %s %s", build_to_delete["name"], number_str)
    resp_str = make_api_request(login_data, "DELETE", req_url)
    logging.debug("Result of delete builds request: %s", resp_str)

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

class BuildDeleter(threading.Thread):
    def __init__(self, input_queue, login_data):
        super().__init__()
        self.logger = logging.getLogger(type(self).__name__)
        self.login_data = login_data
        self._shutdown = False
        # Input Queue Items: {"name": "<build_name>", "numbers": "<build_number_set>"}
        self._input_queue = input_queue

    def run(self):
        self.logger.debug("Starting the BuildDeleter thread.")
        while not self._shutdown:
            # Get a file_meta from the queue
            tmp_file_meta = None
            try:
                item = self._input_queue.get_nowait()
            except queue.Empty:
                self.logger.debug("No more work, shutting down.")
                self.stop()
                break # Force the while loop to end.

            del_empty_build(self.login_data, item)

            self._input_queue.task_done()
        self.logger.debug("Ending the BuildDeleter thread.")

    def stop(self):
        self.logger.debug("Shutting down the BuildDeleter thread.")
        self._shutdown = True

### MAIN ###
def main():
    parser_description = "Clean up builds with missing artifacts."

    parser = argparse.ArgumentParser(description = parser_description, formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action = "store_true")

    parser.add_argument("--num-threads", default = os.getenv("NUM_THREADS", "3"),
                        help = "The number of threads to use for making API calls.  Default is 3")

    parser.add_argument("--oracle-user", default = os.getenv("ORACLE_USER", ""),
                        help = "The username to authenticate to the Oracle Database.")
    parser.add_argument("--oracle-pass", default = os.getenv("ORACLE_PASS", ""),
                        help = "The password to authenticate to the Oracle Database.")
    parser.add_argument("--oracle-host", default = os.getenv("ORACLE_HOST", "localhost"),
                        help = "The hostname of the Oracle server.")
    parser.add_argument("--oracle-port", default = os.getenv("ORACLE_PORT", "1521"),
                        help = "The port of the Oracle server.")
    parser.add_argument("--oracle-dbname", default = os.getenv("ORACLE_DBNAME", ""),
                        help = "The name of the database on the Oracle server.")

    parser.add_argument("--artifactory-token", default = os.getenv("ARTIFACTORY_TOKEN", ""),
                        help = "Artifactory auth token to use for requests.  Will use ARTIFACTORY_TOKEN if not specified.")
    parser.add_argument("--artifactory-host", default = os.getenv("ARTIFACTORY_HOST", ""),
                        help = "Artifactory host URL (e.g. https://artifactory.example.com/) to use for requests.  Will use ARTIFACTORY_HOST if not specified.")

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
    config_data["oracle_user"] = str(args.oracle_user)
    config_data["oracle_pass"] = str(args.oracle_pass)
    config_data["oracle_host"] = str(args.oracle_host)
    config_data["oracle_port"] = int(args.oracle_port)
    config_data["oracle_dbname"] = str(args.oracle_dbname)
    logging.debug("Config Data: %s", config_data)

    # Adding a connection to the config data so we only pass one around
    logging.debug("Getting a list of builds to clean up.")
    logging.debug("Opening database connection.")
    config_data["db_connection"] = oracledb.connect(
        user = config_data["oracle_user"],
        password = config_data["oracle_pass"],
        host = config_data["oracle_host"],
        port = config_data["oracle_port"],
        service_name = config_data["oracle_dbname"]
    )

    # Get the list of builds to delete
    builds_to_delete_list = get_empty_builds(config_data)

    # Clean up database connection
    logging.debug("Closing database connection.")
    config_data["db_connection"].close()
    config_data["db_connection"] = None

    # Queue up the build items to delete
    logging.debug("Queuing the data for the threads.")
    work_queue = queue.Queue()
    builds_to_delete = reorganise_builds(builds_to_delete_list)
    for item in builds_to_delete:
        work_queue.put(item)

    # Run the threads
    logging.debug("Starting threads.")
    wrapper = ThreadWrapper(work_queue, config_data, int(args.num_threads), BuildDeleter)
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
