import click
import anyio

class AsyncCommand(click.Command):
    def invoke(self, ctx: click.Context):
        return anyio.run(self._invoke, ctx)
    
    async def _invoke(self, ctx: click.Context):
        return await super().invoke(ctx)