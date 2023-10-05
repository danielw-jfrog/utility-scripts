#!/usr/bin/env python3

### IMPORTS ###
import psycopg2

### GLOBALS ###

### FUNCTIONS ###

### CLASSES ###

### MAIN ###
def main():
    conn = psycopg2.connect(
            database = "artifactory",
            host = "<HOST>",
            user = "artifactory",
            password = "<PASSWORD>",
            port = "5432")

    cursor = conn.cursor()

    cursor.execute("SELECT count(*) FROM access_users")
    count_users = int(cursor.fetchone()[0])
    print("Users Count: {}".format(count_users))

    cursor.execute("SELECT count(*) FROM access_groups")
    count_groups = int(cursor.fetchone()[0])
    print("Groups Count: {}".format(count_groups))

    cursor.execute("SELECT count(*) FROM access_permissions")
    count_permissions = int(cursor.fetchone()[0])
    print("Permissions Count: {}".format(count_permissions))

    print("Total Count: {}".format(count_users + count_groups + count_permissions))

    conn.close()

if __name__ == '__main__':
    main()
