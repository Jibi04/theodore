from theodore.ai.rules import RouteResult

commands = {
    "cmd": {"func": "", "requirements": ""}
}

def dispatch(ctx: RouteResult):
    intent = ctx.intent
    if (register:=commands.get(intent)) is None:
        raise ValueError("Command Not Understood")
    
    metadata = ctx.metadata.model_dump()
    required_metadata = {}

    for requirement in register["requirements"]:
        required_metadata[requirement] = metadata[requirement]
    
    func = register['func']

    response = func(**required_metadata)

