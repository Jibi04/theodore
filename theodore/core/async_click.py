import asyncio
import click

# 1. Custom Command Class:
# This class executes the final command's callback asynchronously.
class AsyncCommand(click.Command):
    """A custom command that executes async callbacks using asyncio.run."""
    def invoke(self, ctx):
        func = self.callback
        
        # Check if the callback for this *specific command* is a coroutine
        if asyncio.iscoroutinefunction(func):
            # This is where the command's async function is run.
            # Your original debug prints:
            print(f'Caught a call {func.__name__}')
            print(f'{func.__name__} is coroutine running it.')
            
            # Start the event loop and run the coroutine
            try:
                # Use ctx.params to pass all resolved arguments
                return asyncio.run(func(**ctx.params))
            except RuntimeError as e:
                # If the loop is already running (e.g., in a nested call), 
                # a more complex async library is needed. For now, raise 
                # a helpful error, as the outer group should manage the loop.
                raise click.ClickException(
                    f"Async function '{func.__name__}' failed to run. "
                    "Cannot start a new event loop inside an existing one."
                ) from e
        
        # Your original debug prints:
        print(f'{func.__name__} Not async invoking normally')
        return super().invoke(ctx)
    

# 2. Custom Group Class:
# This class ensures async subcommands are wrapped and handles its own async callback (like 'config').
class AsyncGroup(click.Group):
    """A custom group that supports async commands, using AsyncCommand for subcommands."""

    def invoke(self, ctx):
        # Fixes the 'RuntimeWarning: coroutine 'config' was never awaited'
        # by running the group's *own* async callback inside an event loop.
        
        if asyncio.iscoroutinefunction(self.callback):
            
            # The core of the fix: We wrap the synchronous Click invocation
            # inside an async function and run that using asyncio.run().
            async def async_run():
                # We let the base class perform all argument parsing, subcommand resolution, 
                # and group callback forwarding. Since we are now in an async context, 
                # any coroutine returned by the chain will be awaited.
                result = super().invoke(ctx)
                
                if asyncio.iscoroutine(result):
                    return await result
                return result

            try:
                # Start the single top-level event loop here for the whole command chain.
                return asyncio.run(async_run())
            except RuntimeError:
                 # This should only happen if you have a nested AsyncGroup or are in an async environment.
                 pass

        # If the group's own callback is synchronous, or if the async call failed, 
        # delegate to the base class, which will resolve the subcommand (and eventually
        # hit AsyncCommand.invoke if the subcommand is async).
        return super().invoke(ctx)


    def get_command(self, ctx, name):
        """Overrides the command lookup to ensure async commands are wrapped with AsyncCommand."""
        cmd = super().get_command(ctx, name)
        
        if cmd is None:
            return 

        # Your original debug prints:
        print(cmd.name, "made it here About to call it")

        # Check if the command/group callback is a coroutine.
        if asyncio.iscoroutinefunction(cmd.callback):
            # Your original debug prints:
            print(cmd.name, " Is a couroutine running it to command asyncio")
            # Convert it to an AsyncCommand so its `invoke` method is used later.
            return AsyncCommand(
                name=cmd.name, 
                callback=cmd.callback, 
                params=cmd.params, 
                help=cmd.help
            )
        
        # Your original debug prints:
        print(cmd.name, " Not a couroutine")
        return cmd