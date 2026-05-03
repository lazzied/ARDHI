"""Repository helpers for reading crop metadata and ecology tables from EcoCrop."""
import sqlite3

from engines.global_engines.constants import CROP_COLUMNS, CULTIVATION_COLUMNS, ECOLOGY_COLUMNS


class EcoCropRepository:
    def __init__(self, conn: sqlite3.Connection):
        conn.row_factory = sqlite3.Row
        self.conn = conn
        self.cursor = self.conn.cursor()

    def _rows_to_named_mapping(self, rows, columns) -> dict:
        return {
            row["common_name"]: {
                col: row[col] for col in columns
            }
            for row in rows
        }

    def _query_joined_crop_table(self, table_name: str, columns: list[str]) -> dict:
        rows = self.cursor.execute(
            f"""
            SELECT source.*, c.common_name
            FROM {table_name} source
            JOIN crops c ON source.crop_id = c.id
            """
        ).fetchall()
        return self._rows_to_named_mapping(rows, columns)

    def query_from_crops(self):
        rows = self.cursor.execute("SELECT * FROM crops").fetchall()
        return {
            row["common_name"]: {
                col: row[col] for col in CROP_COLUMNS
            }
            for row in rows
        }

    def query_from_ecology(self):
        return self._query_joined_crop_table("crop_ecology", ECOLOGY_COLUMNS)

    def query_from_cultivation(self):
        return self._query_joined_crop_table("crop_cultivation", CULTIVATION_COLUMNS)

    def query_from_climate(self):
        return self._query_joined_crop_table("crop_cultivation", CULTIVATION_COLUMNS)

    def query_all_crop_info(self):
        return {
            "general_crops_info": self.query_from_crops(),
            "ecology_infos": self.query_from_ecology(),
            "cultivation_infos": self.query_from_cultivation(),
            "climate_infos": self.query_from_climate(),
        }
