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
        self._table_columns_cache: dict[str, set[str]] = {}

    def _table_has_column(self, table: str, column: str) -> bool:
        if table not in self._table_columns_cache:
            rows = self.conn.execute(f"PRAGMA table_info({table})").fetchall()
            self._table_columns_cache[table] = {row["name"] for row in rows}
        return column in self._table_columns_cache[table]

    @staticmethod
    def _append_optional_irrigation(query: str, params: list, irrigation_type: IrrigationType | None) -> tuple[str, list]:
        if irrigation_type is None:
            query += " AND irrigation_type IS NULL"
        else:
            query += " AND irrigation_type = ?"
            params.append(_enum_value(irrigation_type))
        return query, params

    @staticmethod
    def _normalize_water_context(
        water_supply: WaterSupply,
        irrigation_type: IrrigationType | None,
    ) -> tuple[WaterSupply, IrrigationType | None]:
        if _enum_value(water_supply) == WaterSupply.IRRIGATED.value and _enum_value(irrigation_type) == IrrigationType.SPRINKLER.value:
            return WaterSupply.RAINFED, None
        return water_supply, irrigation_type

    def _fetch_file_paths(
        self,
        table: str,
        key_column: str,
        filters: dict[str, object],
        irrigation_type: IrrigationType | None = None,
    ) -> dict[str, str]:
        where_clause = " AND ".join(f"{column} = ?" for column in filters)
        query = f"SELECT {key_column}, file_path FROM {table} WHERE {where_clause}"
        params = [_enum_value(value) for value in filters.values()]
        if self._table_has_column(table, "irrigation_type"):
            query, params = self._append_optional_irrigation(query, params, irrigation_type)
        rows = self.conn.execute(query, params).fetchall()
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
        if self._table_has_column(table, "irrigation_type"):
            query, params = self._append_optional_irrigation(query, params, irrigation_type)
        row = self.cursor.execute(query, params).fetchone()
        return row["file_path"].strip() if row else None

    def get_crops_tiff_paths(
        self,
        map_code: str,
        input_level: InputLevel,
        water_supply: WaterSupply,
        irrigation_type: IrrigationType | None = None,
    ) -> dict[str, str]:
        water_supply, irrigation_type = self._normalize_water_context(water_supply, irrigation_type)
        return self._fetch_file_paths(
            "tiff_files",
            "crop_code",
            {
                "map_code": map_code,
                "input_level": input_level,
                "water_supply": water_supply,
            },
            irrigation_type=irrigation_type,
        )

    def query_tiff_path(
        self,
        input_level: InputLevel,
        water_supply: WaterSupply,
        crop_code: str,
        map_code: str,
        irrigation_type: IrrigationType = None,
    ) -> str | None:
        water_supply, irrigation_type = self._normalize_water_context(water_supply, irrigation_type)
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
        water_supply, irrigation_type = self._normalize_water_context(water_supply, irrigation_type)
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
        water_supply, irrigation_type = self._normalize_water_context(
            scenario.water_supply,
            scenario.irrigation_type,
        )
        return self._fetch_single_file_path(
            "edaphic_outputs",
            {
                "input_level": scenario.input_level,
                "water_supply": water_supply,
                "crop_name": scenario.crop_name,
                "ph_level": ph_level,
                "texture_class": texture_class,
            },
            irrigation_type=irrigation_type,
        )

    def query_crop_edaphic_paths(
        self,
        input_level: InputLevel,
        water_supply: WaterSupply,
        ph_level: pH_level,
        texture_class: Texture,
        irrigation_type: IrrigationType = None,
    ) -> dict:
        water_supply, irrigation_type = self._normalize_water_context(water_supply, irrigation_type)
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
        if self._table_has_column("edaphic_outputs", "irrigation_type"):
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
