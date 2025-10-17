#!/usr/bin/env python3

### IMPORTS ###
import argparse
import datetime
import json
import logging
import os
import pathlib
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

def list_conditions(login_data):
    """
    Make a request to the conditions list API.

    :param dict login_data: Dictionary containing "token" and "host" values.
    :return list: List of curation conditions.
    """

    # FIXME: Does this need to handle pagination or forcing a large number of rows?
    # FIXME: Default row count is 15 (way too low), so setting high for now.
    req_url = "/xray/api/v1/curation/conditions?num_of_rows=1000"
    logging.debug("Getting conditions list")
    resp_str = make_api_request(login_data, "GET", req_url)
    logging.debug("Result of list_conditions request: %s", resp_str)
    resp_list = json.loads(resp_str)["data"]
    return resp_list

def compare_conditions(input_list, current_list):
    """
    Compare the lists of conditions:
     - If in the input list and in the current list, check if changes and add updated version to update list if changes.
     - If in the input list and not in the current list, add to create list.

    :param input_list: list of condition dictionaries
    :param current_list: list of condition dictionaries
    :return list, list: list of condition dictionaries to update, list of conditions dictionaries to create
    """
    update_conditions = []
    create_conditions = []
    for input_condition in input_list:
        # FIXME: There's a better way, but I just need to get this search done
        # NOTE: Condition name is assumed to be unique.
        current_conditions = [x for x in current_list if x["name"] == input_condition["name"]]
        if len(current_conditions) > 1:
            logging.error("More than one condition with name: %s, name should be unique", input_condition["name"])
        elif len(current_conditions) == 0:
            logging.debug("Found new condition with name: %s", input_condition["name"])
            create_conditions.append(input_condition)
        else:
            logging.debug("Comparing conditions with name: %s", input_condition["name"])
            update = False
            current_condition = current_conditions[0]
            if input_condition["condition_template_id"] != current_condition["condition_template_id"]:
                logging.debug("  condition_template_id different: %s %s", input_condition["condition_template_id"],current_conditions[0]["condition_template_id"])
                current_condition["condition_template_id"] = input_condition["condition_template_id"]
                update = True
            for input_param in input_condition["param_values"]:
                current_params = [x for x in current_condition["param_values"] if x["param_id"] == input_param["param_id"]]
                if len(current_params) > 1:
                    logging.error("More than one param with param_id: %s, param_id should be unique, updating params", input_param["param_id"])
                    current_condition["param_values"] = input_condition["param_values"]
                    update = True
                    break
                if len(current_params) == 0:
                    logging.debug("New param: %s, updating params", input_param)
                    current_condition["param_values"] = input_condition["param_values"]
                    update = True
                    break
                if input_param["value"] != current_params[0]["value"]:
                    logging.debug("Param changed: %s, updating params", input_param)
                    current_condition["param_values"] = input_condition["param_values"]
                    update = True
                    break
            if update == True:
                update_conditions.append(current_condition)

    return update_conditions, create_conditions

def create_condition(login_data, condition):
    """
    Make a request to the conditions create API.

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param dict condition: Dictionary containing the condition object to create.
    """

    req_url = "/xray/api/v1/curation/conditions"
    logging.debug("Creating condition: %s", condition)
    resp = make_api_request(login_data, "POST", req_url, json.dumps(condition))
    logging.debug("Result of create_condition request: %s", resp)

def update_condition(login_data, condition):
    """
    Make a request to the conditions update API.

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param dict condition: Dictionary containing the condition object to update.
    """

    req_url = "/xray/api/v1/curation/conditions/{}".format(condition["id"])
    logging.debug("Updating condition: %s", condition)
    resp = make_api_request(login_data, "PUT", req_url, json.dumps(condition))
    logging.debug("Result of update_condition request: %s", resp)

def list_policies(login_data):
    """
    Make a request to the policies list API.

    :param dict login_data: Dictionary containing "token" and "host" values.
    :return list: List of curation policies.
    """

    # FIXME: Does this need to handle pagination or forcing a large number of rows?
    # FIXME: Default row count is 15 (way too low), so setting high for now.
    req_url = "/xray/api/v1/curation/policies?num_of_rows=1000"
    logging.debug("Getting policies list")
    resp_str = make_api_request(login_data, "GET", req_url)
    logging.debug("Result of list_policies request: %s", resp_str)
    resp_list = json.loads(resp_str)["data"]
    return resp_list

def fix_policy_condition_ids(input_policies, input_conditions):
    """
    Update the condition id in the policies from a name (if string) to an id (number)

    :param input_list: list of policy dictionaries
    :return list: list of updated policy dictionaries
    """

    for policy in input_policies:
        logging.debug("Fixing policy: %s", policy)
        # FIXME: Need to handle a string with a number (e.g. "13")
        if type(policy["condition_id"]) == type("string"):
            current_conditions = [x for x in input_conditions if x["name"] == policy["condition_id"]]
            if len(current_conditions) > 1:
                logging.error("More than one condition with name: %s, name should be unique", policy["condition_id"])
                # FIXME: What's the right thing to do?
                continue
            elif len(current_conditions) == 0:
                logging.debug("Don't have a condition with name: %s", policy["condition_id"])
                # FIXME: What's the right thing to do?
                continue
            # This one needs to be a number in a string, not just a number.
            policy["condition_id"] = str(int(current_conditions[0]["id"]))
        elif type(policy["condition_id"]) == type(1):
            policy["condition_id"] = str(policy["condition_id"])
    return input_policies

def compare_policies(input_list, current_list):
    """
    Compare the lists of policies:
     - If in the input list and in the current list, check if changes and add updated version to update list if changes.
     - If in the input list and not in the current list, add to create list.

    :param input_list: list of policy dictionaries
    :param current_list: list of policy dictionaries
    :return list, list: list of policy dictionaries to update, list of policy dictionaries to create
    """
    update_policies = []
    create_policies = []
    for input_policy in input_list:
        # FIXME: There's a better way, but I just need to get this search done
        # NOTE: Policy name is assumed to be unique.
        logging.debug("input policy: %s", input_policy)
        current_policies = [x for x in current_list if x["name"] == input_policy["name"]]
        if len(current_policies) > 1:
            logging.error("More than one policy with name: %s, name should be unique", input_policy["name"])
        elif len(current_policies) == 0:
            logging.debug("Found new policy with name: %s", input_policy["name"])
            create_policies.append(input_policy)
        else:
            logging.debug("Comparing policies with name: %s", input_policy["name"])
            update = False
            current_policy = current_policies[0]
            if input_policy["enabled"] != current_policy["enabled"]:
                logging.debug("  changed policy %s enabled, updating policy", input_policy["name"])
                current_policy["enabled"] = input_policy["enabled"]
                update = True
            if input_policy["scope"] != current_policy["scope"]:
                logging.debug("  changed policy %s scope, updating policy", input_policy["name"])
                current_policy["scope"] = input_policy["scope"]
                update = True
            if "repo_exclude" in input_policy and "repo_exclude" not in current_policy:
                logging.debug("  changed policy %s repo_exclude, updating policy", input_policy["name"])
                current_policy["repo_exclude"] = input_policy["repo_exclude"]
                update = True
            # NOTE: Converting the lists of strings into sets to make comparison work
            if "repo_exclude" in input_policy and "repo_exclude" in current_policy and set(input_policy["repo_exclude"]) != set(current_policy["repo_exclude"]):
                logging.debug("  changed policy %s repo_exclude, updating policy", input_policy["name"])
                current_policy["repo_exclude"] = input_policy["repo_exclude"]
                update = True
            if "repo_include" in input_policy and "repo_include" not in current_policy:
                logging.debug("  changed policy %s repo_include, updating policy", input_policy["name"])
                current_policy["repo_include"] = input_policy["repo_exclude"]
                update = True
            if "repo_include" in input_policy and "repo_include" in current_policy and set(input_policy["repo_include"]) != set(current_policy["repo_include"]):
                logging.debug("  changed policy %s repo_include, updating policy", input_policy["name"])
                current_policy["repo_include"] = input_policy["repo_include"]
                update = True
            if "pkg_types_include" in input_policy and "pkg_types_include" not in current_policy:
                logging.debug("  changed policy %s pkg_types_include, updating policy", input_policy["name"])
                current_policy["pkg_types_include"] = input_policy["pkg_types_include"]
                update = True
            if "pkg_types_include" in input_policy and "pkg_types_include" in current_policy and set(input_policy["pkg_types_include"]) != set(current_policy["pkg_types_include"]):
                logging.debug("  changed policy %s pkg_types_include, updating policy", input_policy["name"])
                current_policy["pkg_types_include"] = input_policy["pkg_types_include"]
                update = True
            if input_policy["policy_action"] != current_policy["policy_action"]:
                logging.debug("  changed policy %s policy_action, updating policy", input_policy["name"])
                current_policy["policy_action"] = input_policy["policy_action"]
                update = True
            if input_policy["condition_id"] != current_policy["condition_id"]:
                logging.debug("  changed policy %s condition_id, updating policy", input_policy["name"])
                current_policy["condition_id"] = input_policy["condition_id"]
                update = True
            if "waivers" in input_policy:
                for waiver in input_policy["waivers"]:
                    current_waivers = [x for x in current_policy["waivers"] if x["id"] == waiver["id"]]
                    if len(current_waivers) > 1:
                        logging.error("More than one waiver with id: %s, id should be unique, updating waivers", waiver["id"])
                        current_policy["waivers"] = input_policy["waivers"]
                        update = True
                        break
                    if len(current_waivers) == 0:
                        logging.debug("New waiver: %s, updating waivers", waiver)
                        current_policy["waivers"] = input_policy["waivers"]
                        update = True
                        break
                    if (waiver["pkg_type"] != current_waivers[0]["pkg_type"] and
                        waiver["pkg_name"] != current_waivers[0]["pkg_name"] and
                        waiver["all_versions"] != current_waivers[0]["all_versions"] and
                        set(waiver["pkg_versions"]) != set(current_waivers[0]["pkg_versions"]) and
                        waiver["justification"] != current_waivers[0]["justification"] and
                        waiver["created_by"] != current_waivers[0]["created_by"] and
                        waiver["created_at"] != current_waivers[0]["created_at"]):
                        logging.debug("waiver changed: %s, updating waivers", waiver)
                        current_policy["waivers"] = input_policy["waivers"]
                        update = True
                        break
            if "label_waivers" in input_policy:
                for label_waiver in input_policy["label_waivers"]:
                    current_label_waivers = [x for x in current_policy["label_waivers"] if x["id"] == label_waiver["id"]]
                    if len(current_label_waivers) > 1:
                        logging.error("More than one label_waiver with id: %s, id should be unique, updating label_waivers", label_waiver["id"])
                        current_policy["label_waivers"] = input_policy["label_waivers"]
                        update = True
                        break
                    if len(current_label_waivers) == 0:
                        logging.debug("New label_waiver: %s, updating label_waivers", label_waiver)
                        current_policy["label_waivers"] = input_policy["label_waivers"]
                        update = True
                        break
                    if (label_waiver["label"] != current_label_waivers[0]["label"] and
                        label_waiver["justification"] != current_label_waivers[0]["justification"] and
                        label_waiver["created_by"] != current_label_waivers[0]["created_by"] and
                        label_waiver["created_at"] != current_label_waivers[0]["created_at"]):
                        logging.debug("label_waiver changed: %s, updating label_waivers", label_waiver)
                        current_policy["label_waivers"] = input_policy["label_waivers"]
                        update = True
                        break
            if "notify_emails" in input_policy and "notify_emails" not in current_policy:
                logging.debug("  changed policy %s notify_emails, updating policy", input_policy["name"])
                current_policy["notify_emails"] = input_policy["notify_emails"]
                update = True
            if "notify_emails" in input_policy and "notify_emails" in current_policy and set(input_policy["notify_emails"]) != set(current_policy["notify_emails"]):
                logging.debug("  changed policy %s notify_emails, updating policy", input_policy["name"])
                current_policy["notify_emails"] = input_policy["notify_emails"]
                update = True
            if input_policy["waiver_request_config"] != current_policy["waiver_request_config"]:
                logging.debug("  changed policy %s waiver_request_config, updating policy", input_policy["name"])
                current_policy["waiver_request_config"] = input_policy["waiver_request_config"]
                update = True
            if "decision_owners" in input_policy and "decision_owners" not in current_policy:
                logging.debug("  changed policy %s decision_owners, updating policy", input_policy["name"])
                current_policy["decision_owners"] = input_policy["decision_owners"]
                update = True
            if "decision_owners" in input_policy and "decision_owners" in current_policy and set(input_policy["decision_owners"]) != set(current_policy["decision_owners"]):
                logging.debug("  changed policy %s decision_owners, updating policy", input_policy["name"])
                current_policy["decision_owners"] = input_policy["decision_owners"]
                update = True

            if update == True:
                update_policies.append(current_policy)
    return update_policies, create_policies

def create_policy(login_data, policy):
    """
    Make a request to the policy create API.

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param dict condition: Dictionary containing the policy object to create.
    """

    req_url = "/xray/api/v1/curation/policies"
    logging.debug("Creating policy: %s", policy)
    resp = make_api_request(login_data, "POST", req_url, json.dumps(policy))
    logging.debug("Result of create_policy request: %s", resp)

def update_policy(login_data, policy):
    """
    Make a request to the policy update API.

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param dict condition: Dictionary containing the policy object to update.
    """

    req_url = "/xray/api/v1/curation/policies/{}".format(policy["id"])
    logging.debug("Updating policy: %s", policy)
    resp = make_api_request(login_data, "PUT", req_url, json.dumps(policy))
    logging.debug("Result of update_policy request: %s", resp)


### CLASSES ###

### MAIN ###
def main():
    parser_description = """
    Apply a set of conditions and policies for Curation.
    """

    parser = argparse.ArgumentParser(description = parser_description, formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action = "store_true")
    parser.add_argument("--token", default = os.getenv("ARTIFACTORY_TOKEN", ""),
                        help = "Artifactory auth token to use for requests.  Will use ARTIFACTORY_TOKEN if not specified.")
    parser.add_argument("--host", default = os.getenv("ARTIFACTORY_HOST", ""),
                        help = "Artifactory host URL (e.g. https://artifactory.example.com/) to use for requests.  Will use ARTIFACTORY_HOST if not specified.")

    parser.add_argument("policies_file", help = "JSON file containing the curation policies to apply.")

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

    # Load the contents of the JSON file
    with open(pathlib.Path(args.policies_file), 'r') as json_file:
        input_data = json.load(json_file)

    # List 'current conditions'
    current_conditions = list_conditions(tmp_login_data)

    # Compare 'conditions to apply' to 'current conditions'
    conditions_to_update, conditions_to_create = compare_conditions(input_data["conditions"], current_conditions)
    logging.info("Conditions to Update: %s", conditions_to_update)
    logging.info("Conditions to Create: %s", conditions_to_create)

    # Create or Update conditions as needed
    for upcond in conditions_to_update:
        update_condition(tmp_login_data, upcond)
    for crcond in conditions_to_create:
        create_condition(tmp_login_data, crcond)

    # List 'current conditions' again (if any created) to get valid ids
    current_conditions = list_conditions(tmp_login_data)

    # List 'current policies'
    current_policies = list_policies(tmp_login_data)

    # Update the 'policies to apply' with the 'condition id's of the current conditions
    updated_input_policies = fix_policy_condition_ids(input_data["policies"], current_conditions)

    # Compare 'policies to apply' to 'current policies'
    policies_to_update, policies_to_create = compare_policies(updated_input_policies, current_policies)
    logging.info("Policies to Update: %s", policies_to_update)
    logging.info("Policies to Create: %s", policies_to_create)

    # Create or Update policies as needed
    for uppol in policies_to_update:
        update_policy(tmp_login_data, uppol)
    for crpol in policies_to_create:
        create_policy(tmp_login_data, crpol)

    # List 'current policies' again (if any created) to get valid ids
    current_policies = list_policies(tmp_login_data)

if __name__ == "__main__":
    main()
