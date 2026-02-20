from datetime import datetime
from pathlib import Path
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create timestamped SQLite database backup"

    def handle(self, *args, **options):
        db_path = Path(settings.DATABASES["default"]["NAME"])
        if not db_path.exists():
            self.stdout.write(self.style.WARNING("Database file not found; skipping backup."))
            return

        backup_root = Path(settings.DB_BACKUP_DIR)
        backup_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_root / f"db_backup_{timestamp}.sqlite3"
        shutil.copy2(db_path, backup_file)
        self.stdout.write(self.style.SUCCESS(f"Backup created: {backup_file}"))
