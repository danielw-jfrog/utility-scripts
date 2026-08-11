#!/usr/bin/env python3

### IMPORTS ###
import argparse
import datetime
import json
import logging
import os
import pathlib
import sys
import urllib.request
import urllib.error
import urllib.parse


### GLOBALS ###

### FUNCTIONS ###
def make_api_request(login_data, method, path, data=None, is_data_json=True, headers={}):
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

    request = urllib.request.Request(req_url, data=req_data, headers=req_headers, method=method)
    resp = None
    try:
        with urllib.request.urlopen(request) as response:
            # Check the status and log
            # NOTE: response.status for Python >=3.9, change to response.code if Python <=3.8
            resp = response.read().decode("utf-8")
            # logging.debug("  Response Status: %d, Response Body: %s", response.status, resp)
            logging.debug("  Response Status: %d", response.status)
            logging.debug("Repository operation successful")
    except urllib.error.HTTPError as ex:
        logging.warning("Error (%d) for repository operation", ex.code)
        logging.debug("  response body: %s", ex.read().decode("utf-8"))
    except urllib.error.URLError as ex:
        logging.error("Request Failed (URLError): %s", ex.reason)
    # FIXME: Should make the status code available to the calling method.
    return resp

# def get_artifacts_via_aql_with_pagination(login_data, repository_name):
#     """
#     Make a request to get the AQL API to get the list of all the artifacts to evaluate.
#
#     :param dict login_data: Dictionary containing "token" and "host" values.
#     :param str repository_name: String containing the name of the repository to work with.
#     :result tuple: Tuple containing a result list and a pagination information dictionary.
#     """
#     pass

def get_artifacts_last_n_days(login_data, repository_name, number_of_days):
    """
    Make a request to the API for searching by date range, set to 90 days.
    https://docs.jfrog.com/artifactory/reference/searchdates

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param str repository_name: String containing the name of the repository to work with.
    :result list: List containing the paths of the artifacts.
    """
    dt_then = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days = number_of_days)
    dt_then_urlencoded = urllib.parse.quote(dt_then.isoformat())
    req_url = "/artifactory/api/search/dates?from={}&dateFields=created%2ClastModified&repos={}".format(dt_then_urlencoded, repository_name)
    logging.debug("Getting list of artifacts since %s", dt_then_urlencoded)
    resp_str = make_api_request(login_data, "GET", req_url)
    # logging.debug("Result of get_artifacts_last_90_days: %s", resp_str)
    resp_list = json.loads(resp_str)["results"]
    return resp_list

def get_exposures_for_artifact_with_pagination(login_data, repository_name, artifact_path, page_number = 0, number_per_page = 100):
    """
    Make a request to the exposures API to get a list of all the exposures for the artifact.
    https://docs.jfrog.com/security/reference/get-exposure-result-list

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param str repository_name: String containing the name of the repository to work with.
    :param str artifact_path: String containing the path to the artifact for exposures.
    :param int page_number: Integer containing the page number to request.
    :param int number_per_page: Integer containing the number of results to request for the page to be returned.
    :result tuple: Tuple containing a result list and a pagination information dictionary.
    """
    # FIXME: Support the other types of exposures, probably use an enum
    exposure_type = "secrets"
    artifact_path_urlencoded = urllib.parse.quote(artifact_path) # dirone/dirtwo/artone.file -> dirone%2Fdirtwo%2Fartone.file
    req_url = "/xray/api/v1/{}/results?repo={}&path={}".format(exposure_type, repository_name, artifact_path_urlencoded)
    logging.debug("Getting list of exposures for artifact: %s - %s", repository_name, artifact_path_urlencoded)
    resp_str = make_api_request(login_data, "GET", req_url)
    logging.debug("Result of get_exposures_for_artifact_with_pagination: %s", resp_str)
    resp_dict = json.loads(resp_str)
    pagination_result = {
        "page_number": page_number,
        "number_per_page": number_per_page,
        "total_results": resp_dict["total_count"]
    }
    return (resp_dict["data"], pagination_result)


def get_exposure_details(login_data, repository_name, artifact_path, result_id):
    """
    Make a request to the exposures details API to get the details of an esposure.
    https://docs.jfrog.com/security/reference/get-exposure-result-details

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param str repository_name: String containing the name of the repository to work with.
    :param str artifact_path: String containing the path to the artifact for exposures.
    :param str result_id: String containing the identifier for the exposure to get more data.
    :result dict: Dictionary containing the result information.
    """
    # FIXME: Support the other types of exposures, probably use an enum
    exposure_type = "secrets"
    artifact_path_urlencoded = urllib.parse.quote(artifact_path) # dirone/dirtwo/artone.file -> dirone%2Fdirtwo%2Fartone.file
    req_url = "/xray/api/v1/{}/results/details?repo={}&path={}&id={}".format(exposure_type, repository_name, artifact_path_urlencoded, result_id)
    logging.debug("Getting detauks of exposure for artifact: %s - %s - %s", repository_name, artifact_path_urlencoded, result_id)
    resp_str = make_api_request(login_data, "GET", req_url)
    logging.debug("Result of get_exposure_details: %s", resp_str)
    resp_dict = json.loads(resp_str)
    return resp_dict

def get_findings_for_exposure_for_artifact(login_data, repository_name, artifact_path, result_id):
    """
    Make a request to the exposures API to get a list of all the exposures for the artifact.
    https://docs.jfrog.com/security/reference/get-exposure-result-list

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param str repository_name: String containing the name of the repository to work with.
    :param str artifact_path: String containing the path to the artifact for exposures.
    :param str result_id: String containing the identifier for the exposure to get more data.
    :result list: List containing the findings information.
    """
    # FIXME: Support the other types of exposures, probably use an enum
    exposure_type = "secrets"
    artifact_path_urlencoded = urllib.parse.quote(artifact_path) # dirone/dirtwo/artone.file -> dirone%2Fdirtwo%2Fartone.file
    req_url = "/xray/api/v1/{}/results/details/findings?repo={}&path={}&id={}&first_finding_idx=0".format(exposure_type, repository_name, artifact_path_urlencoded, result_id)
    logging.debug("Getting list of findings for exposure for artifact: %s - %s - %s", repository_name, artifact_path_urlencoded, result_id)
    resp_str = make_api_request(login_data, "GET", req_url)
    logging.debug("Result of get_findings_for_exposure_for_artifact: %s", resp_str)
    resp_list = json.loads(resp_str)
    return resp_list

def get_evidences_for_finding_for_exposure_for_artifact(login_data, repository_name, artifact_path, result_id, finding_id, evidence_count):
    """
    Make a request to the exposures API to get a list of all the exposures for the artifact.
    https://docs.jfrog.com/security/reference/get-exposure-result-list

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param str repository_name: String containing the name of the repository to work with.
    :param str artifact_path: String containing the path to the artifact for exposures.
    :param str result_id: String containing the identifier for the exposure to get more data.
    :param str finding_id: String containing the identifier for the finding to get more data.
    :param str evidence_count: String containing the number of evidences to return.
    :result list: List containing the evidences information.
    """
    # FIXME: Support the other types of exposures, probably use an enum
    exposure_type = "secrets"
    artifact_path_urlencoded = urllib.parse.quote(artifact_path) # dirone/dirtwo/artone.file -> dirone%2Fdirtwo%2Fartone.file
    req_url = "/xray/api/v1/{}/results/details/findings/evidences?repo={}&path={}&id={}&finding_idx={}&first_evidence_idx=0&evidence_count={}".format(
        exposure_type, repository_name, artifact_path_urlencoded, result_id, finding_id, evidence_count)
    logging.debug("Getting list of evidences for finding for exposure for artifact: %s - %s - %s - %s", repository_name, artifact_path_urlencoded, result_id, finding_id)
    resp_str = make_api_request(login_data, "GET", req_url)
    logging.debug("Result of get_evidences_for_finding_for_exposure_for_artifact: %s", resp_str)
    resp_list = json.loads(resp_str)
    return resp_list

def get_rows_for_evidence_for_finding_for_exposure_for_artifact(login_data, repository_name, artifact_path, result_id, finding_id, evidence_id, evidence_count, row_count):
    """
    Make a request to the exposures API to get a list of all the exposures for the artifact.
    https://docs.jfrog.com/security/reference/get-exposure-result-list

    :param dict login_data: Dictionary containing "token" and "host" values.
    :param str repository_name: String containing the name of the repository to work with.
    :param str artifact_path: String containing the path to the artifact for exposures.
    :param str result_id: String containing the identifier for the exposure to get more data.
    :param str finding_id: String containing the identifier for the finding to get more data.
    :param str evidence_id: String containing the identifier for the evidece to get more data.
    :param str row_count: String containing the number of evidence rows to return.
    :result list: List containing the evidence rows information.
    """
    # FIXME: Support the other types of exposures, probably use an enum
    exposure_type = "secrets"
    artifact_path_urlencoded = urllib.parse.quote(artifact_path) # dirone/dirtwo/artone.file -> dirone%2Fdirtwo%2Fartone.file
    req_url = "/xray/api/v1/{}/results/details/findings/evidences?repo={}&path={}&id={}&finding_idx={}&evidence_idx={}&first_evidence_idx=0&evidence_count={}&first_row_idx=0&rows_count={}".format(
        exposure_type, repository_name, artifact_path_urlencoded, result_id, finding_id, evidence_id, evidence_count, row_count)
    logging.debug("Getting list of rows for evidence for finding for exposure for artifact: %s - %s - %s - %s - %s", repository_name, artifact_path_urlencoded, result_id, finding_id, evidence_id)
    resp_str = make_api_request(login_data, "GET", req_url)
    logging.debug("Result of get_rows_for_evidence_for_finding_for_exposure_for_artifact: %s", resp_str)
    resp_list = json.loads(resp_str)
    return resp_list

### CLASSES ###

class Writer:
    def open(self, filename):
        self.filename = pathlib.Path(filename)
        self.fd = open(self.filename, 'w')

    def write(self, input_str):
        self.fd.write(input_str)
        self.fd.flush()

    def close(self):
        self.fd.close()

class ExposuresCSVWriter(Writer):
    """
    This class is speciallized to write the specific data for the Exposures to the file one line at a time.  This is
    used instead of the normal built-in to Python CSV Writer class to save the memory and flush to file for each
    entry written to the file.  This is less quick, but uses less memory overall.

    keys for the input dictionary:
        "repository",
        "path",
        "exposure_id",
        "cwe_id",
        "cwe_name",
        "description",
        "severity",
        "finding_id",
        "finding_text",
        "finding_meaning",
        "evidence_id",
        "evidence_text",
        "evidence_row_number",
        "evidence_row_path",
        "evidence_row_evidence",
        "evidence_row_line_number"
    """

    # FIXME: Figure out how to do this with CSVWriter if possible, or figure out
    #        a better way to handle the dicts and possible quote characters.

    def open(self, filename):
        super().open(filename)
        super().write("repository,path,exposure_id,cwe_id,cwe_name,description,severity,finding_id,finding_text,finding_meaning,evidence_id,evidence_text,evidence_row\n")

    def write(self, line_data_dict):
        # format line data to string
        line = "{},{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
            line_data_dict["repository"],
            line_data_dict["path"],
            line_data_dict["exposure_id"],
            line_data_dict["cwe_id"],
            line_data_dict["cwe_name"],
            line_data_dict["description"],
            line_data_dict["severity"],
            line_data_dict["finding_id"],
            line_data_dict["finding_text"],
            line_data_dict["finding_meaning"],
            line_data_dict["evidence_id"],
            line_data_dict["evidence_text"],
            line_data_dict["evidence_row"]
        )
        super().write( str(line) )

    def close(self):
        super().close()

# class ExposuresJSONWriter(Writer):
    # """
    # This class is specialized to write the specific data for the Exposures to the file one line at a time.  This is
    # used instead of the normal built-in to Python JSON Writer class to save the memory and flush to file for each
    # entry written to the file.  This is less quick, but uses less memory overall.
    # """

    # def open(self, filename):
        # super().open(filename)
        # super().write( ?? start of file ?? )

    # def write(self, line_data):
        # format line data to string
        # super().write( string )

    # def close(self):
        # super?? write( ?? end of file ?? )
        # super().close()


### MAIN ###
def main():
    parser_description = """
    Generate a JFrog Advanced Security Exposures Report the hard way.  This can be used when very large reports need to
    be generated, causing problems with the built-in report tool.
    
    NOTE: This should be used only when the built-in report tool is failing.  This will take a long time to run and make
          a lot of API calls.
    """

    parser = argparse.ArgumentParser(description = parser_description, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action = "store_true")
    parser.add_argument("--log-output-file", help="File to output logging.")

    parser.add_argument("--artifactory-token", default = os.getenv("ARTIFACTORY_TOKEN", ""),
                        help = "Artifactory auth token to use for requests.  Will use ARTIFACTORY_TOKEN environ if not specified.")
    parser.add_argument("--artifactory-host", default = os.getenv("ARTIFACTORY_HOST", ""),
                        help = "Artifactory host URL (e.g. https://artifactory.example.com/) to use for requests.  Will use ARTIFACTORY_HOST environ if not specified.")

    parser.add_argument("--repository-name",
                        help = "The name of the repository for which the report should be generated.")
    parser.add_argument("--number-of-days", default = 90, type = int,
                        help = "The number of days back the report should cover.")
    parser.add_argument("--output-format", default = "CSV",
                        help = "The output format, either 'CSV' or 'JSON'.  'CSV' is the default.")
                        # FIXME: Make this choose from an enum/list and "lower case" the option.
    parser.add_argument("--output-filename",
                        help = "The path and filename of the output file.")

    args = parser.parse_args()

    # Set up logging
    log_format = "%(asctime)s:%(levelname)s:%(name)s.%(funcName)s: %(message)s"
    log_root = logging.getLogger()
    log_root.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    log_handler = None
    if args.log_output_file:
        log_handler = logging.FileHandler(args.log_output_file, 'w', 'utf-8')
    else:
        log_handler = logging.StreamHandler(sys.stdout)
    log_handler.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    log_handler.setFormatter(logging.Formatter(log_format))
    log_root.addHandler(log_handler)

    logging.debug("Args: %s", args)

    # Set up the config data
    logging.debug("Preparing the environment.")
    config_data = {}
    config_data["token"] = str(args.artifactory_token)
    config_data["host"] = str(args.artifactory_host)
    logging.debug("Config Data: %s", config_data)

    # Open the CSV or JSON file for writing
    # FIXME: Make this work on a list of repository names.
    # For each repo:
    # - Get the list of artifacts (pagination should be used as these will be huge lists - 100,000+ files)
    # - For each artifact:
    #   - Get the list of exposures with type secret (https://docs.jfrog.com/security/reference/get-exposure-result-list)
    #   - For each exposure:
    #     - Get the details of the exposure (if more detail is needed on top of the list entry)
    #     - Append the exposure to the results file (CSV or JSON - may need to manually create the CSV or JSON file to save memory)
    # Close the CSV or JSON file

    writer = None
    if(args.output_format == 'JSON'):
        pass
    else:
        writer = ExposuresCSVWriter()
    writer.open(args.output_filename)

    repository_name = args.repository_name
    number_of_days = args.number_of_days
    logging.debug(" --> Repository Name: '%s', Number of Days: %d", repository_name, number_of_days)

    artifact_list = get_artifacts_last_n_days(config_data, str(repository_name), int(number_of_days))
    # logging.debug("Artifact List: %s", artifact_list)

    uri_front = "{}/artifactory/api/storage/{}".format(config_data['host'], repository_name)
    logging.debug("uri_front: %s", uri_front)

    for artifact_entry in artifact_list:
        # Remove the host and repo to get the path
        tmp_entry = str(artifact_entry['uri']).replace(uri_front, "")
        logging.debug("Artifact Path: %s", tmp_entry)

        result_dict = {
            "repository": repository_name,
            "path": tmp_entry,
            "exposure_id": "",
            "cwe_id": "",
            "cwe_name": "",
            "description": "",
            "severity": "",
            "finding_id": "",
            "finding_text": "",
            "finding_meaning": "",
            "evidence_id": "",
            "evidence_text": "",
            "evidence_row": ""
        }

        # Get the list of exposures
        (exposure_list, pagination_dict) =  get_exposures_for_artifact_with_pagination(config_data, repository_name, tmp_entry, page_number=0, number_per_page=100)
        logging.debug("Exposure List: %s", exposure_list)
        logging.debug("Pagination Dict: %s", pagination_dict)

        # {
        #   'status': 'ok',
        #   'jfrog_severity': 'high',
        #   'id': 'EXP-1687-47363',
        #   'description': 'Hardcoded secrets were found',
        #   'abbreviation': 'REQ.SECRET.JSON',
        #   'cwe': {'cwe_id': 'CWE-256', 'cwe_name': 'Plaintext Storage of a Password'},
        #   'outcomes': ['Credential extraction', 'Data collection'],
        #   'fix_cost': 'medium',
        #   'sha256': 'c0e46aba09657249bf10e8b3dc3076654f1d081a6bfe0f1a7a285a80101cc8f9',
        #   'origin': 'jfrog'
        # }

        for exposure_entry in exposure_list:
            result_dict['exposure_id'] = exposure_entry['id']
            result_dict['cwe_id'] = exposure_entry['cwe']['cwe_id']
            result_dict['cwe_name'] = exposure_entry['cwe']['cwe_name']
            result_dict['description'] = exposure_entry['description']
            result_dict['severity'] = exposure_entry['jfrog_severity']

            detail_dict = get_exposure_details(config_data, repository_name, tmp_entry, exposure_entry['id'])
            logging.debug("Exposure Details: %s", detail_dict)

            # {
            #   'status': 'ok',
            #   'jfrog_severity': 'high',
            #   'id': 'EXP-1687-47538',
            #   'description': 'Hardcoded secrets were found',
            #   'abbreviation': 'REQ.SECRET.JSON',
            #   'cwe': {
            #     'cwe_id': 'CWE-256',
            #     'cwe_name': 'Plaintext Storage of a Password',
            #     'cwe_link': 'https://cwe.mitre.org/data/definitions/256.html'
            #   },
            #   'fix_cost': 'medium',
            #   'outcomes_details': [
            #     {
            #       'name': 'Credential extraction',
            #       'description': "Attackers obtain credentials from the device's network communications or from the device itself - typically by using firmware analysis or after obtaining shell access or code execution. User credentials enable attackers to impersonate one or more of the device's users. Credentials belonging to the device itself enable the attackers to impersonate this device to other hosts in the system. If device credentials are shared, then the attackers can impersonate all devices in the same group."
            #     }, {
            #       'name': 'Data collection',
            #       'description': "Attackers extract private, sensitive, restricted, or otherwise valuable data from the target device. This is typically done using firmware analysis or after obtaining shell access or code execution. The extracted data can belong to the user, in which case this can violate the user's privacy, or to the vendor, in which case it can be used for further attacks against the vendor's devices and infrastructure."
            #     }
            #   ],
            #   'findings': {
            #     'explanation': '<p>Secrets are defined as passwords or tokens that can grant elevated privileges to the holder of the secret.<br />\nIn many instances, secrets are kept hardcoded in source code or binary artifacts, even though it is a bad practice that can be avoided by using safer storage locations.<br />\nThe scanner identifies suspicious pairs of variables and values, where the variable name is indicative of a secret, and the value is a high-entropy string indicative of a random password or token.</p>',
            #     'justification': '<p>Storing hardcoded secrets in your source code or binary artifact could lead to several risks. </p>\n<p>If the secret is associated with a wide scope of privileges, attackers could extract it from the source code or binary artifact and use it maliciously to attack many targets. For example, if the hardcoded password gives high-privilege access to an AWS account, the attackers may be able to query/modify company-wide sensitive data without per-user authentication.</p>',
            #     'mitigation': '<h1>Safe storage</h1>\n<p>Use safe storage when storing high-privilege secrets such as passwords and tokens, for example -</p>\n<h2>Environment Variables</h2>\n<p>Environment variables are set outside of the application code, and can be dynamically passed to the application only when needed, for example -<br />\n<code>SECRET_VAR=MySecret ./my_application</code><br />\nThis way, <code>MySecret</code> does not have to be hardcoded into <code>my_application</code>.</p>\n<p>Note that if your entire binary artifact is published (ex. a Docker container published to Docker Hub), the value for the environment variable must not be stored in the artifact itself (ex. inside the <code>Dockerfile</code> or one of the container\'s files) but rather must be passed dynamically, for example in the <code>docker run</code> call as an argument.</p>\n<h2>Secret management services</h2>\n<p>External vendors offer cloud-based secret management services, that provide proper access control to each secret. The given access to each secret can be dynamically modified or even revoked. Some examples include -</p>\n<ul>\n<li><a target="_blank" href="https://www.vaultproject.io">Hashicorp Vault</a></li>\n<li><a target="_blank" href="https://aws.amazon.com/kms">AWS KMS</a> (Key Management Service)</li>\n<li><a target="_blank" href="https://cloud.google.com/security-key-management">Google Cloud KMS</a></li>\n</ul>\n<h1>Least-privilege principle</h1>\n<p>Storing a secret in a hardcoded manner can be made safer, by making sure the secret grants the least amount of privilege as needed by the application.<br />\nFor example - if the application needs to read a specific table from a specific database, and the secret grants access to perform this operation <strong>only</strong> (meaning - no access to other tables, no write access at all) then the damage from any secret leaks is mitigated.<br />\nThat being said, it is still not recommended to store secrets in a hardcoded manner, since this type of storage does not offer any way to revoke or moderate the usage of the secret.</p>',
            #     'total_findings': 1
            #   },
            #   'origin': 'standard'
            # }

            if detail_dict['findings']['total_findings'] > 0:
                # Get the findings
                findings_list = get_findings_for_exposure_for_artifact(config_data, repository_name, tmp_entry, exposure_entry['id'])
                logging.debug("Findings List: %s", findings_list)

                # [
                #   {
                #     'finding_idx': 0,
                #     'finding_text': 'Hardcoded secrets were not found',
                #     'finding_meaning': 'ok'
                #   }
                # ]

                for finding_entry in findings_list:
                    result_dict['finding_id'] = finding_entry['finding_idx']
                    result_dict['finding_text'] = finding_entry['finding_text']
                    result_dict['finding_meaning'] = finding_entry['finding_meaning']

                    if 'total_evidences' in finding_entry:
                        evidences_list = get_evidences_for_finding_for_exposure_for_artifact(config_data, repository_name, tmp_entry, exposure_entry['id'], finding_entry['finding_idx'], finding_entry['total_evidences'])
                        logging.debug("Evidences List: %s", evidences_list)

                        for evidence_entry in evidences_list:
                            result_dict['evidence_id'] = evidence_entry["evidence_idx"]
                            result_dict['evidence_text'] = evidence_entry["evidence_text"]

                            rows_list = get_rows_for_evidence_for_finding_for_exposure_for_artifact(config_data, repository_name, tmp_entry, exposure_entry['id'], finding_entry['finding_idx'], evidence_entry['evidence_idx'], finding_entry['total_evidences'], evidence_entry['total_rows'])
                            logging.debug("Evidence Rows List: %s", rows_list)

                            # [
                            #   {
                            #     'evidence_idx': 0,
                            #     'evidence_text': '',
                            #     'column_names': ['Path', 'Provider', 'Evidence', 'Line Number'],
                            #     'cell_type': 'values_only',
                            #     'total_rows': 1,
                            #     'rows': [
                            #       ['/bad_stuff/.aws/cli/cache/36c0348e027b522a55df7f3b50677d1035b67660.json', 'aws_access', 'o+8zZ**********', '1']
                            #     ]
                            #   }
                            # ]

                            # FIXME: This is dumping the values.  The should be converted into a class/object and values gathered via that.
                            result_dict['evidence_row'] = str(rows_list[0]['rows'][0])
                            result_dict['evidence_row'] = result_dict['evidence_row'].replace('"', '')
                            result_dict['evidence_row'] = "\"{}\"".format(result_dict['evidence_row'])

                            writer.write(result_dict)
                    else:
                        writer.write(result_dict)
            else:
                writer.write(result_dict)

        # FIXME: Handle the pagination for result sets larger than 100
        if pagination_dict["total_results"] > 100:
            logging.error("FIXME: Handle the pagination for result sets larger than 100")

    writer.close()

if __name__ == "__main__":
    main()
