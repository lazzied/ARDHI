import sqlite3
import logging
from ardhi.config import ARDHI_DB_PATH, ECOCROP_DB_PATH, HWSD_DB_PATH


logger = logging.getLogger(__name__)

def get_hwsd_connection()-> sqlite3.Connection:
    conn = sqlite3.connect(HWSD_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn

def get_ardhi_connection()-> sqlite3.Connection:
    conn = sqlite3.connect(ARDHI_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Access columns by name
       
    return conn

def get_ecocrop_connection()-> sqlite3.Connection:
    conn = sqlite3.connect(ECOCROP_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def close_connection(conn: sqlite3.Connection) -> None:
    if conn:
        try:
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.warning("Error closing connection: %s", e)
            
            
