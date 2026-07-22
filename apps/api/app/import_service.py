"""XLSX import service for career units.

Parses XLSX files and imports job descriptions into the database,
with automatic capability extraction from JD text.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .database import Database
from .vectorization import normalize_label, pack_vector


# XLSX column mapping (based on the provided XLSX structure)
COLUMN_MAPPING = {
    "公司": "company",
    "岗位": "job_title",
    "城市": "city",
    "薪资": "salary",
    "经验": "experience",
    "学历": "education",
    "链接": "url",
    "公司猎聘网址": "liepin_url",
    "收录时间": "collected_at",
    "JD描述": "jd_description",
    "数据来源": "data_source",
    "其他信息": "other_info",
    "来源平台": "source_platform",
}


@dataclass
class ImportResult:
    """Result of an XLSX import operation."""
    batch_id: int
    batch_code: str
    total_count: int = 0
    success_count: int = 0
    skip_count: int = 0
    fail_count: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    capabilities_created: int = 0
    aliases_created: int = 0


@dataclass
class ExtractedCapability:
    """A capability extracted from JD text."""
    name: str
    normalized: str
    evidence_text: str
    confidence: float = 1.0


class CapabilityExtractor:
    """Extract capabilities from JD text using dictionary matching."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._load_dictionary()

    def _load_dictionary(self) -> None:
        """Load capability dictionary from database."""
        self.aliases: dict[str, tuple[int, int, str]] = {}  # normalized -> (alias_id, capability_id, alias_name)
        rows = self.conn.execute("""
            SELECT ca.id, ca.capability_id, ca.alias_name, ca.normalized_alias
            FROM capability_aliases ca
            JOIN capabilities c ON c.id = ca.capability_id
        """).fetchall()
        for row in rows:
            self.aliases[row["normalized_alias"]] = (
                row["id"], row["capability_id"], row["alias_name"]
            )

    def extract(self, text: str) -> list[ExtractedCapability]:
        """Extract capabilities from text using dictionary matching."""
        if not text:
            return []

        results: list[ExtractedCapability] = []
        text_lower = text.lower()

        # Match against dictionary
        for normalized, (alias_id, cap_id, alias_name) in self.aliases.items():
            if normalized and normalized in text_lower:
                results.append(ExtractedCapability(
                    name=alias_name,
                    normalized=normalized,
                    evidence_text=self._extract_context(text, alias_name),
                    confidence=1.0,
                ))

        # Extract potential new capabilities (technical terms in English or Chinese)
        new_caps = self._extract_potential_capabilities(text)
        results.extend(new_caps)

        return results

    def _extract_context(self, text: str, term: str, context_len: int = 50) -> str:
        """Extract surrounding context for a matched term."""
        idx = text.lower().find(term.lower())
        if idx < 0:
            return term
        start = max(0, idx - context_len)
        end = min(len(text), idx + len(term) + context_len)
        return text[start:end].strip()

    def _extract_potential_capabilities(self, text: str) -> list[ExtractedCapability]:
        """Extract potential new capabilities using pattern matching."""
        results: list[ExtractedCapability] = []

        # English technical terms (capitalized words, acronyms)
        en_patterns = [
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',  # CamelCase or multi-word
            r'\b([A-Z]{2,}[0-9]*)\b',  # Acronyms like ROS, SLAM, AI
        ]
        for pattern in en_patterns:
            for match in re.finditer(pattern, text):
                term = match.group(1)
                normalized = normalize_label(term)
                if normalized and len(normalized) >= 2 and normalized not in self.aliases:
                    results.append(ExtractedCapability(
                        name=term,
                        normalized=normalized,
                        evidence_text=self._extract_context(text, term),
                        confidence=0.7,
                    ))

        return results


class ImportService:
    """Service for importing XLSX files into the database."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def import_xlsx(self, file_path: Path, sub_direction_id: int | None = None) -> ImportResult:
        """Import an XLSX file into the database.

        Args:
            file_path: Path to the XLSX file
            sub_direction_id: Default sub-direction ID for imported units (optional)

        Returns:
            ImportResult with statistics and errors
        """
        try:
            import openpyxl
        except ImportError:
            raise RuntimeError("openpyxl is required for XLSX import. Install with: pip install openpyxl")

        # Generate batch code
        batch_code = f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        with self.database.write() as conn:
            # Create import batch
            cursor = conn.execute("""
                INSERT INTO import_batches (batch_code, source_file, status)
                VALUES (?, ?, 'running')
            """, (batch_code, file_path.name))
            batch_id = cursor.lastrowid

            result = ImportResult(batch_id=batch_id, batch_code=batch_code)

            try:
                # Load workbook
                wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
                ws = wb.active

                # Parse header row
                headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
                col_indices = self._map_columns(headers)

                if not col_indices.get("job_title"):
                    raise ValueError("XLSX must contain a '岗位' column")

                # Initialize capability extractor
                extractor = CapabilityExtractor(conn)

                # Process rows
                for row_num, row in enumerate(ws.iter_rows(min_row=2), start=2):
                    result.total_count += 1
                    try:
                        self._process_row(
                            conn, row, col_indices, row_num,
                            sub_direction_id, extractor, result
                        )
                    except Exception as e:
                        result.fail_count += 1
                        result.errors.append({
                            "row": row_num,
                            "error": str(e),
                        })

                wb.close()

                # Update batch status
                conn.execute("""
                    UPDATE import_batches
                    SET status = 'completed',
                        completed_at = datetime('now'),
                        total_count = ?,
                        success_count = ?,
                        skip_count = ?,
                        fail_count = ?
                    WHERE id = ?
                """, (result.total_count, result.success_count,
                      result.skip_count, result.fail_count, batch_id))

            except Exception as e:
                conn.execute("""
                    UPDATE import_batches
                    SET status = 'failed', error_details = ?
                    WHERE id = ?
                """, (str(e), batch_id))
                raise

        return result

    def _map_columns(self, headers: list[str | None]) -> dict[str, int]:
        """Map XLSX headers to internal column names."""
        indices: dict[str, int] = {}
        for idx, header in enumerate(headers):
            if header and header in COLUMN_MAPPING:
                indices[COLUMN_MAPPING[header]] = idx
        return indices

    def _process_row(
        self,
        conn: sqlite3.Connection,
        row: tuple,
        col_indices: dict[str, int],
        row_num: int,
        default_sub_direction_id: int | None,
        extractor: CapabilityExtractor,
        result: ImportResult,
    ) -> None:
        """Process a single XLSX row."""
        def get_value(key: str) -> str | None:
            idx = col_indices.get(key)
            if idx is None or idx >= len(row):
                return None
            val = row[idx].value
            return str(val).strip() if val is not None else None

        job_title = get_value("job_title")
        if not job_title:
            result.skip_count += 1
            return

        company_name = get_value("company")
        company_id = self._get_or_create_company(conn, company_name) if company_name else None

        # Get JD description for capability extraction
        jd_description = get_value("jd_description") or ""

        # Extract capabilities
        extracted = extractor.extract(jd_description)

        # Create career unit
        cursor = conn.execute("""
            INSERT INTO career_units (
                sub_direction_id, company_id, job_title, city, salary,
                experience, education, url, jd_description, other_info,
                data_source, source_platform, collected_at, capability_requirements
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            default_sub_direction_id,
            company_id,
            job_title,
            get_value("city"),
            get_value("salary"),
            get_value("experience"),
            get_value("education"),
            get_value("url"),
            jd_description,
            get_value("other_info"),
            get_value("data_source"),
            get_value("source_platform"),
            get_value("collected_at"),
            self._format_capability_requirements(extracted),
        ))
        career_unit_id = cursor.lastrowid

        # Create capability links
        for cap in extracted:
            alias_id = self._get_or_create_capability(conn, cap, result)
            if alias_id:
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO job_capability_links
                        (career_unit_id, capability_alias_id, extraction_method, confidence, evidence_text)
                        VALUES (?, ?, ?, ?, ?)
                    """, (career_unit_id, alias_id, "dictionary", cap.confidence, cap.evidence_text))
                except sqlite3.IntegrityError:
                    pass

        result.success_count += 1

    def _get_or_create_company(self, conn: sqlite3.Connection, name: str) -> int:
        """Get or create a company record."""
        normalized = normalize_label(name)
        row = conn.execute(
            "SELECT id FROM companies WHERE normalized_name = ?", (normalized,)
        ).fetchone()
        if row:
            return row["id"]

        cursor = conn.execute("""
            INSERT INTO companies (name, normalized_name, display_name)
            VALUES (?, ?, ?)
        """, (name, normalized, name))
        return cursor.lastrowid

    def _get_or_create_capability(
        self,
        conn: sqlite3.Connection,
        extracted: ExtractedCapability,
        result: ImportResult,
    ) -> int | None:
        """Get or create a capability alias, returning the alias ID."""
        # Check if alias already exists
        row = conn.execute(
            "SELECT id FROM capability_aliases WHERE normalized_alias = ?",
            (extracted.normalized,)
        ).fetchone()
        if row:
            return row["id"]

        # Find a matching capability by name similarity, or create new
        cap_row = conn.execute("""
            SELECT id FROM capabilities
            WHERE name = ? OR code = ?
            LIMIT 1
        """, (extracted.name, extracted.normalized)).fetchone()

        if cap_row:
            capability_id = cap_row["id"]
        else:
            # Create new capability in the first category (default)
            cat_row = conn.execute(
                "SELECT id FROM capability_categories ORDER BY sort_order LIMIT 1"
            ).fetchone()
            if not cat_row:
                return None

            cursor = conn.execute("""
                INSERT INTO capabilities (category_id, name, code)
                VALUES (?, ?, ?)
            """, (cat_row["id"], extracted.name, extracted.normalized))
            capability_id = cursor.lastrowid
            result.capabilities_created += 1

        # Create alias
        cursor = conn.execute("""
            INSERT INTO capability_aliases
            (capability_id, alias_name, normalized_alias, alias_type, confidence)
            VALUES (?, ?, ?, 'synonym', ?)
        """, (capability_id, extracted.name, extracted.normalized, extracted.confidence))
        result.aliases_created += 1
        return cursor.lastrowid

    def _format_capability_requirements(self, extracted: list[ExtractedCapability]) -> str:
        """Format extracted capabilities as JSON for storage."""
        import json
        return json.dumps([
            {"name": cap.name, "confidence": cap.confidence}
            for cap in extracted
        ], ensure_ascii=False)

    def get_import_status(self, batch_id: int) -> dict[str, Any] | None:
        """Get the status of an import batch."""
        with self.database.read() as conn:
            row = conn.execute("""
                SELECT * FROM import_batches WHERE id = ?
            """, (batch_id,)).fetchone()
            if not row:
                return None
            return dict(row)
