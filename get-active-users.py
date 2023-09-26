#!/usr/bin/env python3

### IMPORTS ###
import argparse
import datetime
import json
import logging
import os
import urllib.request
import urllib.error

### GLOBALS ###

### FUNCTIONS ###
def make_api_request(login_data, method, path, data = None, is_data_json = True):
    """
    Send the request to the JFrog Artifactory API.

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param str method: One of "GET", "PUT", or "POST".
    :param str url: URL of the API sans the "host" part.
    :param str data: String containing the data serialized into JSON format.
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
    return resp

def get_user_list(login_data):
    """
    Make a request to the user list API.

    :param dict login_data: Dictionary containing "token" and "host" values.
    :return list: List of user dictionaries.
    """
    # Might need `?limit=99999` for a longer list.
    req_url = "/access/api/v2/users"
    logging.debug("Getting user list")
    resp_str = make_api_request(login_data, "GET", req_url)
    logging.debug("Result of get_user_list request: %s", resp_str)
    resp_list = json.loads(resp_str)["users"]
    return resp_list

def get_last_logged_in(login_data, username):
    """
    Make a request to the user details api and return the last_logged_in time

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param str username: String with the username to get the last_logged_in time
    :return datetime: last_logged_in time converted to a datatime object
    """
    req_url = "/access/api/v2/users/{}".format(username)
    logging.debug("Getting user list")
    resp_str = make_api_request(login_data, "GET", req_url)
    logging.debug("Result of get_user_details request: %s", resp_str)
    resp_dict = json.loads(resp_str)
    last_str = resp_dict["last_logged_in"]
    if last_str == "1970-01-01T00:00:00.000Z":
        return None
    if last_str[-1:] == 'Z':
        # NOTE: For some reason, the python method doesn't support the 'Z' timezone marker and milliseconds simultaneously.
        last_str = last_str[0:-1]
    last_datetime = datetime.datetime.fromisoformat(last_str)
    return last_datetime

### CLASSES ###

### MAIN ###
def main():
    parser_description = """
    Get a list of active users and if desired count how many have logged in within the specified number of days.
    """

    parser = argparse.ArgumentParser(description = parser_description, formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action = "store_true")
    parser.add_argument("--token", default = os.getenv("ARTIFACTORY_TOKEN", ""),
                        help = "Artifactory auth token to use for requests.  Will use ARTIFACTORY_TOKEN if not specified.")
    parser.add_argument("--host", default = os.getenv("ARTIFACTORY_HOST", ""),
                        help = "Artifactory host URL (e.g. https://artifactory.example.com/) to use for requests.  Will use ARTIFACTORY_HOST if not specified.")

    parser.add_argument("--days", type = int, default = 0, help = "Count the number of users that have logged in the specified number of days.")

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG if args.verbose else logging.INFO
    )
    logging.debug("Args: %s", args)

    logging.info("Preparing Environment")

    tmp_login_data = {}
    tmp_login_data["token"] = args.token
    tmp_login_data["host"] = args.host

    # Get the list of users
    logging.info("Gathering user list")
    user_list = get_user_list(tmp_login_data)

    # For each enabled user, get the "last logged in" time
    logging.info("Get the \"last logged in\" time for each enabled user")
    for user_item in user_list:
        if user_item["status"] == "enabled":
            user_item["last-logged-in"] = get_last_logged_in(tmp_login_data, user_item["username"])
            logging.info("Username: %s, Last Logged In: %s", user_item["username"], user_item["last-logged-in"])

    # Count the users that have logged in since the specified number of days
    if args.days > 0:
        logging.info("Count the recently logged in users")
        count = 0
        cmp_datetime = datetime.datetime.now() - datetime.timedelta(days = args.days)
        for user_item in user_list:
            # CHECK THE LAST LOGGED IN
            if (user_item["status"] == "enabled") and (user_item["last-logged-in"] is not None) and (user_item["last-logged-in"] > cmp_datetime):
                count = count + 1
        logging.info("Number of active users: %d", count)

if __name__ == "__main__":
    main()