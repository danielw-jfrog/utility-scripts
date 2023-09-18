#!/usr/bin/env python3

### IMPORTS ###
import psycopg2

### GLOBALS ###

### FUNCTIONS ###

### CLASSES ###

### MAIN ###
def main():
    conn = psycopg2.connect(
            database = "xraydb",
            host = "<HOST>",
            user = "xray",
            password = "<PASSWORD>",
            port = "5432")

    cursor = conn.cursor()

    cursor.execute("SELECT count(*) FROM public_vulnerabilities pv JOIN public_vulnerabilities_components pvc ON pv.id = pvc.public_vulns_tbl_id WHERE summary LIKE 'Malicious package %';")

    print("Malicious Package Component Count: {}".format(cursor.fetchone()[0]))

    cursor.execute("SELECT pv.id, pv.package_type, pvc.name FROM public_vulnerabilities pv JOIN public_vulnerabilities_components pvc ON pv.id = pvc.public_vulns_tbl_id WHERE pv.summary LIKE 'Malicious package %';")

    result = cursor.fetchall()

    for item in result:
        print("ID: {}, Package Type: {}, Component Name: {}".format(item[0], item[1], item[2]))

    conn.close()

if __name__ == '__main__':
    main()
