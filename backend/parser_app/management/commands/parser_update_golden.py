"""
Обновляет golden-эталон по результату legacy parser для выбранного файла.
Запуск: python manage.py parser_update_golden --file-id 3
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from parser_app.models import File
from parser_app.parsers import ExcelParser


class Command(BaseCommand):
    help = "Обновляет golden JSON для regression-harness по выбранному excel-файлу"

    def add_arguments(self, parser):
        parser.add_argument("--file-id", type=int, required=True, help="ID файла из таблицы File")
        parser.add_argument("--supplier-type", type=str, default=None, help="supplier_type для parse kwargs")
        parser.add_argument("--brewery-name", type=str, default=None, help="brewery_name для parse kwargs")
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Куда сохранить golden (по умолчанию backend/media/golden/file-<id>.json)",
        )

    def handle(self, *args, **options):
        file_id = options["file_id"]
        try:
            file_obj = File.objects.get(pk=file_id)
        except File.DoesNotExist as exc:
            raise CommandError(f"Файл с id={file_id} не найден") from exc

        if file_obj.file_type != "excel":
            raise CommandError("Golden обновление поддержано только для excel-файлов")

        parse_kwargs = {}
        if options.get("supplier_type"):
            parse_kwargs["supplier_type"] = options["supplier_type"]
        if options.get("brewery_name"):
            parse_kwargs["brewery_name"] = options["brewery_name"]

        file_path = Path(settings.MEDIA_ROOT) / file_obj.file_path
        items = ExcelParser(str(file_path)).parse(**parse_kwargs)

        output = options.get("output")
        if output:
            out_path = Path(output)
        else:
            out_dir = Path(settings.MEDIA_ROOT) / "golden"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"file-{file_id}.json"

        payload = {
            "file_id": file_id,
            "file_name": file_obj.original_filename,
            "items_count": len(items),
            "items": items,
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        self.stdout.write(self.style.SUCCESS(f"Golden обновлён: {out_path} (items={len(items)})"))

