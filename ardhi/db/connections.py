import sqlite3
from ardhi.config import ARDHI_DB_PATH, HWSD_DB_PATH

def get_hwsd_connection()-> sqlite3.Connection:
    conn = sqlite3.connect(HWSD_DB_PATH)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn

def get_ardhi_connection()-> sqlite3.Connection:
    conn = sqlite3.connect(ARDHI_DB_PATH)
    conn.row_factory = sqlite3.Row  # Access columns by name
       
    return conn

def close_connection(conn: sqlite3.Connection) -> None:
    if conn:
        try:
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            print(f"Error closing connection: {e}")