#!/usr/bin/env python3

### IMPORTS ###
import argparse
import csv
import json
import logging
import pathlib

### GLOBALS ###

### FUNCTIONS ###
# The CSV format is a list of the values: repo_key, repo_type, remote_url, package_type, description
# Returns list of dicts containing the needed values.
def read_csv(filename):
    logging.debug("read_csv filename: %s", filename)

    result = []
    with open(filename, newline='') as csvfile:
        csvr = csv.DictReader(csvfile)
        for row in csvr:
            # FIXME: Does there need to be dict key conversion here?
            result.append(row)

    return result

# The data format is a list of dictionaries containing the values
# [
#   { key: string, type: string, url: string, packageType: string },
#   { key: string, type: string, url: string, packageType: string },
#   ...
# ]
def write_json(filename, data):
    logging.debug("write_json filename: %s, data: %s", filename, data)

    with open(filename, 'w') as jsonfile:
        json.dump(data, jsonfile, indent = 2)

### CLASSES ###

### MAIN ###
def main():
    parser_description = "Parse the CSV to a JSON."

    parser = argparse.ArgumentParser(description = parser_description, formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action = "store_true")

    parser.add_argument("csv_path", help = "Path to CSV file.")

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG if args.verbose else logging.INFO
    )
    logging.debug("Args: %s", args)

    # Set up the config data
    logging.debug("Preparing the environment.")
    fcsv_path = pathlib.Path(args.csv_path)
    fjson_path = "{}.json".format(fcsv_path.stem)

    # Import the CSV file
    data = read_csv(fcsv_path)
    logging.debug("Imported data: %s", data)

    # Export the CSV file
    write_json(fjson_path, data)

if __name__ == "__main__":
    main()
