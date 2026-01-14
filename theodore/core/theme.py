from rich.console import Console
from rich.theme import Theme

def cli_defaults():
    import rich_click as cl
    from rich.traceback import install

    cl.rich_click.STYLE_COMMANDS_TABLE_SHOW_LINES = False
    cl.rich_click.MAX_WIDTH = 100
    cl.rich_click.STYLE_OPTION = "bold cyan"
    cl.rich_click.STYLE_COMMANDS_PANEL = "bold yellow"

    install(console=console, word_wrap=True, show_locals=True)

    return

custom_theme = Theme(styles={"error": "bold red", "success": "green", "warning": "bold magenta"})
console = Console(theme=custom_theme)