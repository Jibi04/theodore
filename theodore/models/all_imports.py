from theodore.models.base import meta, DB 
from theodore.models.configs import ConfigTable
from theodore.models.downloads import DownloadTable
from theodore.models.other_models import Queues, FileLogsTable
from theodore.models.tasks import TasksTable
from theodore.models.weather import Current, Forecasts, Alerts

# alembic revision --autogenerate -m "Initial Migration"