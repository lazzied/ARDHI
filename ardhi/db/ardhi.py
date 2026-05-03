"""Repository helpers for the main ARDHI SQLite database and raster path lookups."""
import sqlite3

from engines.OCR_processing.models import InputLevel, IrrigationType, ScenarioConfig, Texture, WaterSupply, pH_level
from engines.global_engines.models import InputManagement


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


class ArdhiRepository:
    def __init__(self, conn: sqlite3.Connection):
        conn.row_factory = sqlite3.Row
        self.conn = conn
        self.cursor = self.conn.cursor()

    @staticmethod
    def _append_optional_irrigation(query: str, params: list, irrigation_type: IrrigationType | None) -> tuple[str, list]:
        if irrigation_type is None:
            query += " AND irrigation_type IS NULL"
        else:
            query += " AND irrigation_type = ?"
            params.append(_enum_value(irrigation_type))
        return query, params

    def _fetch_file_paths(self, table: str, key_column: str, filters: dict[str, object]) -> dict[str, str]:
        where_clause = " AND ".join(f"{column} = ?" for column in filters)
        query = f"SELECT {key_column}, file_path FROM {table} WHERE {where_clause}"
        rows = self.conn.execute(query, [_enum_value(value) for value in filters.values()]).fetchall()
        return {row[key_column]: row["file_path"] for row in rows}

    def _fetch_single_file_path(
        self,
        table: str,
        filters: dict[str, object],
        irrigation_type: IrrigationType | None = None,
    ) -> str | None:
        where_clause = " AND ".join(f"{column} = ?" for column in filters)
        query = f"SELECT file_path FROM {table} WHERE {where_clause}"
        params = [_enum_value(value) for value in filters.values()]
        query, params = self._append_optional_irrigation(query, params, irrigation_type)
        row = self.cursor.execute(query, params).fetchone()
        return row["file_path"].strip() if row else None

    def get_crops_tiff_paths(self, map_code: str, input_level: InputLevel, water_supply: WaterSupply) -> dict[str, str]:
        return self._fetch_file_paths(
            "tiff_files",
            "crop_code",
            {
                "map_code": map_code,
                "input_level": input_level,
                "water_supply": water_supply,
            },
        )

    def query_tiff_path(
        self,
        input_level: InputLevel,
        water_supply: WaterSupply,
        crop_code: str,
        map_code: str,
        irrigation_type: IrrigationType = None,
    ) -> str | None:
        return self._fetch_single_file_path(
            "tiff_files",
            {
                "input_level": input_level,
                "water_supply": water_supply,
                "crop_code": crop_code,
                "map_code": map_code,
            },
            irrigation_type=irrigation_type,
        )

    def calendar_query_tiff_path(
        self,
        crop_code: str,
        map_code: str,
        water_supply: WaterSupply,
        input_level: InputLevel,
        irrigation_type: IrrigationType = None,
    ) -> str | None:
        return self._fetch_single_file_path(
            "tiff_files",
            {
                "crop_code": crop_code,
                "map_code": map_code,
                "water_supply": water_supply,
                "input_level": input_level,
            },
            irrigation_type=irrigation_type,
        )

    def query_edaphic_path(
        self,
        scenario: ScenarioConfig,
        ph_level: pH_level,
        texture_class: Texture,
    ) -> str | None:
        return self._fetch_single_file_path(
            "edaphic_outputs",
            {
                "input_level": scenario.input_level,
                "water_supply": scenario.water_supply,
                "crop_name": scenario.crop_name,
                "ph_level": ph_level,
                "texture_class": texture_class,
            },
            irrigation_type=scenario.irrigation_type,
        )

    def query_crop_edaphic_paths(
        self,
        input_level: InputLevel,
        water_supply: WaterSupply,
        ph_level: pH_level,
        texture_class: Texture,
        irrigation_type: IrrigationType = None,
    ) -> dict:
        query = """
            SELECT crop_name, file_path
            FROM edaphic_outputs
            WHERE input_level = ?
            AND water_supply = ?
            AND ph_level = ?
            AND texture_class = ?
        """
        params = [
            input_level.value,
            water_supply.value,
            ph_level.value,
            texture_class.value,
        ]
        query, params = self._append_optional_irrigation(query, params, irrigation_type)
        rows = self.cursor.execute(query, params).fetchall()
        return {row["crop_name"]: row["file_path"] for row in rows}

    def _query_sq_file_paths(self, map_code: str, management: InputManagement) -> dict[str, str]:
        rows = self.cursor.execute(
            """
            SELECT sq_factor, file_path
            FROM tiff_files
            WHERE map_code = ? AND management = ?
            """,
            (map_code, management.value),
        ).fetchall()
        return {row["sq_factor"]: row["file_path"] for row in rows}

    def query_all_sq_file_paths(self, management: InputManagement):
        return self._query_sq_file_paths("SQX", management)

    def query_sqidx_file_path(self, management: InputManagement):
        return self._query_sq_file_paths("SQX-IDX", management)
