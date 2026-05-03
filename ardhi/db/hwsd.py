"""Repository helpers for querying HWSD soil-unit and layer data."""
import logging
import sqlite3


logger = logging.getLogger(__name__)


class HwsdRepository:
    def __init__(self, conn: sqlite3.Connection):
        conn.row_factory = sqlite3.Row
        self.conn = conn
        self.cursor = self.conn.cursor()

    def _fetch_layer_row(self, smu_id, fao_90_class: str, layer: str, columns: list[str]):
        cols_sql = ", ".join(columns)
        self.cursor.execute(
            f"SELECT {cols_sql} FROM HWSD2_LAYERS WHERE HWSD2_SMU_ID = ? AND LAYER = ? AND FAO90 = ?",
            (smu_id, layer, fao_90_class),
        )
        return self.cursor.fetchone()

    def _fetch_fao_rows(self, smu_id: int):
        self.cursor.execute(
            """
            SELECT FAO90, SHARE
            FROM HWSD2_SMU
            WHERE HWSD2_SMU_ID = ?
            ORDER BY SHARE DESC, FAO90 ASC
            """,
            (smu_id,),
        )
        return self.cursor.fetchall()

    def get_layer_attribute(self, smu_id, attribute: str, fao_90_class: str, layer: str = "D1"):
        row = self._fetch_layer_row(smu_id, fao_90_class, layer, [attribute])
        return row[attribute] if row else None

    def get_layer_attributes(self, smu_id, attributes: list[str], fao_90_class: str, layer: str = "D1") -> dict | None:
        row = self._fetch_layer_row(smu_id, fao_90_class, layer, attributes)
        return dict(zip(attributes, row)) if row else None

    def get_code_value(self, attribute, code):
        table_name = f"D_{attribute}"
        self.cursor.execute(f"SELECT VALUE FROM {table_name} WHERE CODE = ?", (code,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def get_SMU_attribute(self, smu_id: int, attribute: str, fao_90_class: str):
        self.cursor.execute(
            f"SELECT {attribute} FROM HWSD2_SMU WHERE HWSD2_SMU_ID = ? AND FAO90 = ?",
            (smu_id, fao_90_class),
        )
        row = self.cursor.fetchone()
        return row[attribute] if row else None

    def get_single_layer_attributes(
        self,
        columns: list,
        fao_90_class: str,
        layer: str,
        smu_id: str,
    ) -> dict:
        row = self._fetch_layer_row(smu_id, fao_90_class, layer, columns)
        return dict(row) if row else {}

    def get_fao_90(self, smu_id: int) -> str | None:
        rows = self._fetch_fao_rows(smu_id)
        row = rows[0] if rows else None
        return row["FAO90"].strip() if row else None

    def get_fao_90_candidates(self, smu_id: int) -> list[dict]:
        rows = self._fetch_fao_rows(smu_id)
        return [
            {
                "fao_90": row["FAO90"].strip(),
                "share": float(row["SHARE"] or 0),
            }
            for row in rows
            if row["FAO90"]
        ]

    def get_soter_texture_class(self, smu_id, fao_90):
        row = self._fetch_layer_row(smu_id, fao_90, "D1", ["TEXTURE_SOTER"])
        return row["TEXTURE_SOTER"].strip() if row else None

    def debug_query(self, smu_id, fao_90_class, layer="D1"):
        self.cursor.execute("SELECT COUNT(*) FROM HWSD2_LAYERS WHERE HWSD2_SMU_ID = ?", (smu_id,))
        logger.debug("Rows with smu_id: %s", self.cursor.fetchone()[0])

        self.cursor.execute("SELECT COUNT(*) FROM HWSD2_LAYERS WHERE HWSD2_SMU_ID = ? AND LAYER = ?", (smu_id, layer))
        logger.debug("Rows with smu_id + layer: %s", self.cursor.fetchone()[0])

        self.cursor.execute(
            "SELECT COUNT(*) FROM HWSD2_LAYERS WHERE HWSD2_SMU_ID = ? AND LAYER = ? AND FAO90 = ?",
            (smu_id, layer, fao_90_class),
        )
        logger.debug("Rows with all 3 conditions: %s", self.cursor.fetchone()[0])

        self.cursor.execute("SELECT DISTINCT FAO90, LAYER FROM HWSD2_LAYERS WHERE HWSD2_SMU_ID = ?", (smu_id,))
        logger.debug("Actual FAO90/LAYER combos: %s", self.cursor.fetchall())
