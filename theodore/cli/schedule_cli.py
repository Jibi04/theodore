import rich_click as click
from click_option_group import optgroup, RequiredMutuallyExclusiveOptionGroup


from theodore.cli.async_click import AsyncCommand
from theodore.core.transporter import send_command
from theodore.core.informers import user_info

class KeyValueParse(click.ParamType):
    """
    Parsing function arguments into dictionary objects, making it transport ready fast.
    """
    name = "KV_PAIRS"

    def convert(self, value, param, ctx):
        try:
            if value is None:
                return {}
            return {
                (parts := item.split('='))[0]: parts[1]
                for item in value.split(',')
                if "=" in item
            }
        except ValueError:
            self.fail(message="Invalid Argument Expected 'key1=val1,key2=val2'", param=param, ctx=ctx)

class Dtype(click.ParamType):
    """
    First Line of Data Validation before processing.
    Integers < 0 and or > 60 not raises ValueError then raises Value or TypeError depending on the Violation
    """
    name = "type_alias"

    def convert(self, value, param: click.Parameter | None, ctx: click.Context | None):
        if value == "*":
            return "*"
        try:
            if 0 <= (val:= int(value)) <=60:
                return val
            self.fail(
                message=f"Value {value} is out of bounds (0-60)",
                param=param,
                ctx=ctx
                )
        except (ValueError, TypeError):
            self.fail(
                    message=f"Expected integer or '*' got {value}",
                    param=param,
                    ctx=ctx
                    )
        return value

KV_PAIRS = KeyValueParse()
DEFAULT_TYPE = Dtype()

@click.group()
def scheduler():
    """Manage, and create new Jobs."""
    ...

@scheduler.command(cls=AsyncCommand)
async def start_jobs():
    """Start all currently queued jobs"""
    msg = await send_command("START-JOBS", {})
    user_info(msg)

@scheduler.command(cls=AsyncCommand)
async def stop_jobs():
    """Stop all job executions (running and queued)"""
    msg = await send_command("STOP-JOBS", {})
    user_info(msg)

@scheduler.command(cls=AsyncCommand)
@optgroup.group("Required one", cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option("--key", "-k", type=str)
@optgroup.option("--all", "-a", is_flag=True)
async def job_info(key, all):
    """List All pending Jobs"""
    from theodore.managers.scheduler import get_table
    from theodore.core.theme import console
    import json

    data_str = await send_command("JOB-INFO", {"key": key, "all": all})
    data = json.loads(data_str)
    table = get_table(data)
    console.print(table)

@scheduler.command(cls=AsyncCommand)
@click.option("--key", "-k", type=str, required=True)
async def delete_job(key):
    """Delete / remove a job from jobstore"""
    msg = await send_command("REMOVE-JOB", {"key": key})
    user_info(msg)

@scheduler.command(cls=AsyncCommand)
@click.option("--key", "-k", type=str, required=True)
async def pause_job(key):
    """set pause flag on a job (pending or already running)"""
    msg = await send_command("PAUSE-JOB", {"key": key})
    user_info(msg)

@scheduler.command(cls=AsyncCommand)
@click.option("--key", "-k", type=str, required=True)
async def resume_job(key):
    """resume job flagged pause"""
    msg = await send_command("RESUME-JOB", {"key": key})
    user_info(msg)

@scheduler.command(cls=AsyncCommand)
@click.option("--key", "-k", required=True, type=str)
@click.option("--func_args", "--args", type=KV_PAIRS, help="key=value comma separated arguments 'key1=val1,key2=val2'")
@click.option("--func_path", "-p", type=str)
@click.option("--trigger", "-t", type=click.Choice(["cron", "interval"]), default="interval")
@click.option("--second", "-s", type=DEFAULT_TYPE)
@click.option("--minute", "-m", type=DEFAULT_TYPE)
@click.option("--hour", "-h", type=DEFAULT_TYPE)
@click.option("-dow", type=click.Choice([1, 2, 3, 4, 5, 6, 7]), default=None)
@click.option("--week", "-w", type=int)
@click.option("--month", type=int)
@click.option("--year", "-y", type=int)
@click.option("--day", "-d", type=int)
@click.option("--profiling_enabled", is_flag=True, default=True)
@click.pass_context
async def new_job(
    ctx: click.Context,
    **kwargs
    ):
    """
    
    Automate ETL tasks, File downloads File organization etc with apscheduler.

    """
    package = {
        "intent": "NEW-JOB",
        "file_args": ctx.params
    }

    msg = await send_command(**package)  
    user_info(msg)  