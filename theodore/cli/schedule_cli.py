import click
import struct
import json

from theodore.core.lazy import get_worker, get_dispatch

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

@click.command()
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
def schedule(
    ctx: click.Context,
    **kwargs
    ):
    """
    
    Automate ETL tasks, File downloads File organization etc with apscheduler.

    """
    package = {
        "cmd": "START-ETL",
        "file_args": ctx.params
    }
    
    packed = json.dumps(package).encode()
    header = struct.pack("!I", len(packed))
    get_dispatch().dispatch_cli(get_worker().send_signal, header=header, message=packed)