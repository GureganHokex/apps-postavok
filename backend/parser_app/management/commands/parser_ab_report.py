"""
Сравнение legacy и v2 парсинга для конкретного файла.
Запуск: python manage.py parser_ab_report --file-id 3 [--supplier-type distributor]
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from parser_app.models import File
from parser_app.parsers import ExcelParser
from parser_app.pipeline_v2 import ExcelPipelineV2


class Command(BaseCommand):
    help = "Генерирует A/B отчёт по количеству и покрытиям полей (legacy vs v2)"

    def add_arguments(self, parser):
        parser.add_argument("--file-id", type=int, required=True, help="ID файла из таблицы File")
        parser.add_argument("--supplier-type", type=str, default=None, help="supplier_type для parse kwargs")
        parser.add_argument("--brewery-name", type=str, default=None, help="brewery_name для parse kwargs")
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Путь для сохранения JSON отчёта (по умолчанию в backend/media/reports)",
        )

    def _coverage(self, items):
        if not items:
            return {}
        tracked = ["brewery", "beer_name", "style", "abv", "price", "volume", "format_type", "stock"]
        total = len(items)
        out = {}
        for field in tracked:
            filled = sum(1 for item in items if item.get(field) not in (None, "", []))
            out[field] = round(filled / total, 4)
        return out

    def handle(self, *args, **options):
        file_id = options["file_id"]
        try:
            file_obj = File.objects.get(pk=file_id)
        except File.DoesNotExist as exc:
            raise CommandError(f"Файл с id={file_id} не найден") from exc

        if file_obj.file_type != "excel":
            raise CommandError("A/B отчёт сейчас поддержан только для excel-файлов")

        file_path = Path(settings.MEDIA_ROOT) / file_obj.file_path
        parse_kwargs = {}
        if options.get("supplier_type"):
            parse_kwargs["supplier_type"] = options["supplier_type"]
        if options.get("brewery_name"):
            parse_kwargs["brewery_name"] = options["brewery_name"]

        legacy_items = ExcelParser(str(file_path)).parse(**parse_kwargs)
        v2_result = ExcelPipelineV2(str(file_path)).run(**parse_kwargs)

        report = {
            "file_id": file_id,
            "file_name": file_obj.original_filename,
            "pipeline_legacy_items": len(legacy_items),
            "pipeline_v2_items": len(v2_result.items),
            "delta_items": len(v2_result.items) - len(legacy_items),
            "legacy_coverage": self._coverage(legacy_items),
            "v2_coverage": self._coverage(v2_result.items),
            "v2_status": v2_result.status,
            "v2_warnings": [w.to_dict() for w in v2_result.warnings],
            "v2_errors": [e.to_dict() for e in v2_result.errors],
        }

        output = options.get("output")
        if output:
            out_path = Path(output)
        else:
            out_dir = Path(settings.MEDIA_ROOT) / "reports"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"parser-ab-report-file-{file_id}.json"
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        self.stdout.write(self.style.SUCCESS(f"A/B отчёт сохранён: {out_path}"))

