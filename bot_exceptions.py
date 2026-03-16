class BotExitException(Exception):
    pass


class ResetRaise(BotExitException):
    pass


class RestartRaise(BotExitException):
    pass


class StopBottingRaise(BotExitException):
    pass
