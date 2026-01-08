from theodore.models.base import meta, DB 
from theodore.models.configs import Configs_table
from theodore.models.downloads import file_downloader
from theodore.models.other_models import Queues, File_logs
from theodore.models.tasks import Tasks
from theodore.models.weather import Current, Forecasts, Alerts

# alembic revision --autogenerate -m "Initial Migration"