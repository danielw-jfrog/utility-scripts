#!/usr/bin/env python3

### IMPORTS ###
import argparse
import json
import logging
import pathlib

### GLOBALS ###

### FUNCTIONS ###

### CLASSES ###
# The data format is a list of dictionaries containing the values
# [
#   { key: string, type: string, url: string, packageType: string },
#   { key: string, type: string, url: string, packageType: string },
#   ...
# ]
def gen_csv(filename, data):
    logging.debug("genCSV filename: %s, data: %s", filename, data)
    data_keys = list(data[0].keys())
    logging.debug("genCSV data_keys: %s", data_keys)
    with open(filename, 'w', encoding="utf-8") as csv_file:
        # Write the header:
        csv_file.write("\"{}\"".format(data_keys[0]))
        for i in range(1, len(data_keys)):
            csv_file.write(",\"{}\"".format(data_keys[i]))
        csv_file.write("\n")
        # Write the data from each object
        for item in data:
            csv_file.write("\"{}\"".format(item[data_keys[0]]))
            for i in range(1, len(data_keys)):
                try:
                    csv_file.write(",\"{}\"".format(item[data_keys[i]]))
                except KeyError:
                    csv_file.write(",\"\"")
            csv_file.write("\n")

### MAIN ###
def main():
    parser_description = "Parse the F-JSON to a CSV."

    parser = argparse.ArgumentParser(description = parser_description, formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-v", "--verbose", action = "store_true")

    parser.add_argument("fjson_path", help = "Path to F-JSON file.")

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG if args.verbose else logging.INFO
    )
    logging.debug("Args: %s", args)

    # Set up the config data
    logging.debug("Preparing the environment.")
    fjson_path = pathlib.Path(args.fjson_path)
    fcsv_path = "{}.csv".format(fjson_path.stem)

    # Import the F-JSON file
    with open(args.fjson_path, 'r') as json_file:
        data = json.load(json_file)
    logging.debug("Imported data: %s", data)

    # Export the CSV file
    gen_csv(fcsv_path, data)

if __name__ == "__main__":
    main()
