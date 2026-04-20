import pyodbc
import sqlite3
import pandas as pd

mdb_file = r"C:\Users\zied\Desktop\ARDHI\WCS\HWSD2.mdb"
sqlite_file = r"C:\Users\zied\Desktop\ARDHI\WCS\hwsd.db"

conn_str = (
    "Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
    f"Dbq={mdb_file};"
    "Uid=Admin;Pwd=;"
)

print("Connecting with:", conn_str)  # verify the string looks correct

access_conn = pyodbc.connect(conn_str)
cursor = access_conn.cursor()

tables = [row.table_name for row in cursor.tables(tableType='TABLE')]
print("Tables found:", tables)

sqlite_conn = sqlite3.connect(sqlite_file)

for table_name in tables:
    print(f"Converting table: {table_name}")
    df = pd.read_sql(f"SELECT * FROM [{table_name}]", access_conn)
    df.to_sql(table_name, sqlite_conn, if_exists='replace', index=False)

access_conn.close()
sqlite_conn.close()
print(f"Done! Saved as {sqlite_file}")