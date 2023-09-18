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

    print("ID, Package Type, Component Name")

    cursor.execute("SELECT pv.id, pv.package_type, pvc.name FROM public_vulnerabilities pv JOIN public_vulnerabilities_components pvc ON pv.id = pvc.public_vulns_tbl_id WHERE pv.summary LIKE 'Malicious package %';")

    result = cursor.fetchall()

    for item in result:
        print("{}, {}, {}".format(item[0], item[1], item[2]))

    conn.close()

if __name__ == '__main__':
    main()
