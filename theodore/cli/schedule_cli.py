import click
import struct
import json

from theodore.cli.async_click import AsyncCommand
from theodore.ai.dispatch import WORKER, DISPATCH

class KeyValueParse(click.ParamType):
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

@click.command(cls=AsyncCommand)
@click.option("--key", required=True, type=str)
@click.option("--func_args", "--args", type=KV_PAIRS, help="key=value comma separated arguments 'key1=val1,key2=val2'")
@click.option("--trigger", "-t", type=click.Choice(["cron", "interval"]), default="interval")
@click.option("--seconds", "-s", type=DEFAULT_TYPE)
@click.option("--min", "-m", type=DEFAULT_TYPE)
@click.option("--hour", "-h", type=DEFAULT_TYPE)
@click.option("-dow", type=click.Choice([1, 2, 3, 4, 5, 6, 7]), default=None)
@click.option("--profiling_enabled", is_flag=True, default=True)
@click.pass_context
async def schedule(
    ctx: click.Context,
    **kwargs
    ):
    """
    Automate ETL tasks, File downloads File organization etc with Scheduler.
    Apscheduler API Integration comming soon.
    """
    worker = WORKER
    package = {
        "cmd": "START-ETL",
        "file_args": ctx.params
    }
    
    packed = json.dumps(package).encode()
    header = struct.pack("!I", len(packed))
    await DISPATCH.dispatch_cli(worker.send_signal, header=header, message=packed)