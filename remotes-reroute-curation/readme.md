Remotes ReRoute for Curation
============================

This folder contains a few scripts to help with rerouting Artifactory remotes to
connect to an Artifactory instance with Curation enabled.  There are many
options, including `--dry-run`, so run the `--help` option to see them.

Steps
-----
 * Get the list of remote repositories to convert into the correct format.  If
   the list is in CSV format, the `csv-to-json.py` script can help convert it.
 * Run the `create-remotes.py` script with the host and token set for the
   Artifactory instance with Curation enabled.  This will output another JSON
   file with the URLs updated for that Artifactory instance.  The filename will
   end with `_new_remotes.json`.
 * Run the `update-remotes.py` script with the host and token set for the
   Artifactory instance with the remotes that need to be updated.  Use the
   `_new_remotes.json` file as the input.  This will update all of the remotes
   listed in that JSON file and then output another JSON with all of the
   original setting for the same remotes.  The file with the original settings
   will end with `_old_remotes.json`.  This can be used in place of the
   `_new_remotes.json` file to revert the changes. 

JSON Input Format
-----------------

The input JSON format for these scripts is a list of dictionaries with certain
values:
 * `key` - name of the repository
 * `type` - should always be `REMOTE` for these scripts
 * `url` - URL that will be applied
 * `packageType` - type of packages the repository holds (e.g. `npm` or `pypi`)
 * `description` - optional and should be an empty string (`""`) if no values is
   desired

Below is an example JSON segment:
```
[
   { "key": "...", "type": "REMOTE", "url": "...", "packageType": "...", "description": "...optional..." },
   { "key": "...", "type": "REMOTE", "url": "...", "packageType": "...", "description": "...optional..." },
   { "key": "...", "type": "REMOTE", "url": "...", "packageType": "...", "description": "...optional..." },
   ...
]
```
