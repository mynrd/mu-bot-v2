import time
import io
import sys
import threading
import traceback
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime


def console_log_with_ign(ign: str, *args, **kwargs):
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"{ign}_{today}.log")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = " ".join(str(arg) for arg in args)
    if kwargs:
        message += " " + " ".join(f"{k}={v}" for k, v in kwargs.items())

    full_message = f"[{timestamp}] [{ign}] {message}"
    print(full_message)

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(full_message + "\n")


def console_log(*args, **kwargs):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    local_kwargs = kwargs.copy()
    file_arg = local_kwargs.pop("file", None)

    buf = io.StringIO()
    print(*args, file=buf, **local_kwargs)
    printed_body = buf.getvalue().rstrip("\n")

    if file_arg is not None:
        print(f"[{timestamp}]", *args, file=file_arg, **local_kwargs)
    else:
        print(f"[{timestamp}]", *args, **local_kwargs)

    try:
        logger = logging.getLogger("mu_bot")
        if printed_body:
            logger.info(printed_body)
        else:
            logger.info("")
    except Exception:
        try:
            bot_log_name = os.path.join("logs", f"bot_{time.strftime('%Y-%m-%d')}" + ".log")
            os.makedirs(os.path.dirname(bot_log_name), exist_ok=True)
            with open(bot_log_name, "a", encoding="utf-8") as f:
                if printed_body:
                    f.write(f"[{timestamp}] {printed_body}\n")
                else:
                    f.write(f"[{timestamp}]\n")
        except Exception:
            pass


def setup_logging(bot_log=None, error_log=None, max_bytes=5_000_000, backup_count=3):
    logger = logging.getLogger("mu_bot")
    logger.setLevel(logging.INFO)

    if bot_log is None:
        bot_log = os.path.join("logs", f"bot_{time.strftime('%Y-%m-%d')}" + ".log")
    if error_log is None:
        error_log = os.path.join("logs", f"error_{time.strftime('%Y-%m-%d')}" + ".log")

    try:
        logs_dir = os.path.dirname(bot_log) or "logs"
        if logs_dir:
            os.makedirs(logs_dir, exist_ok=True)
    except Exception:
        pass

    if any(isinstance(h, RotatingFileHandler) and h.baseFilename.endswith(bot_log) for h in getattr(logger, "handlers", [])):
        return

    fmt = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    info_handler = RotatingFileHandler(bot_log, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(fmt)

    error_handler = RotatingFileHandler(error_log, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(fmt)

    logger.addHandler(info_handler)
    logger.addHandler(error_handler)


def log_exception(exc_type, exc_value, tb=None, context=None):
    try:
        if tb is None and hasattr(exc_value, "__traceback__"):
            tb = exc_value.__traceback__
        formatted = "".join(traceback.format_exception(exc_type, exc_value, tb))

        context_msg = None
        if isinstance(context, dict):
            context_msg = context.get("message")

        if context_msg:
            console_log("UNHANDLED EXCEPTION:", context_msg)
        console_log("UNHANDLED EXCEPTION:\n", formatted)

        try:
            logger = logging.getLogger("mu_bot")
            if context_msg:
                logger.error(context_msg + "\n" + formatted)
            else:
                logger.error(formatted)
        except Exception:
            pass

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        try:
            error_log_name = os.path.join("logs", f"error_{time.strftime('%Y-%m-%d')}" + ".log")
            os.makedirs(os.path.dirname(error_log_name), exist_ok=True)
            with open(error_log_name, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] ")
                if context_msg:
                    f.write(context_msg + "\n")
                f.write(formatted)
                f.write("\n")
        except Exception:
            pass
    except Exception:
        pass


_original_sys_excepthook = sys.excepthook
_original_threading_excepthook = getattr(threading, "excepthook", None)


def _sys_excepthook(exc_type, exc_value, tb):
    log_exception(exc_type, exc_value, tb)
    try:
        if _original_sys_excepthook and _original_sys_excepthook is not sys.__excepthook__:
            _original_sys_excepthook(exc_type, exc_value, tb)
    except Exception:
        pass


def _threading_excepthook(args):
    log_exception(args.exc_type, args.exc_value, args.exc_traceback)
    try:
        if _original_threading_excepthook:
            _original_threading_excepthook(args)
    except Exception:
        pass


def _asyncio_exception_handler(loop, context):
    exc = context.get("exception")
    if exc is not None:
        log_exception(type(exc), exc, getattr(exc, "__traceback__", None), context)
    else:
        msg = context.get("message", "Asyncio exception")
        log_exception(Exception, Exception(msg), None, context)


def setup_global_error_handlers(enable_asyncio=True):
    try:
        sys.excepthook = _sys_excepthook
    except Exception:
        pass
    try:
        if hasattr(threading, "excepthook"):
            threading.excepthook = _threading_excepthook
    except Exception:
        pass
    if enable_asyncio:
        try:
            loop = asyncio.get_event_loop()
            loop.set_exception_handler(_asyncio_exception_handler)
        except Exception:
            pass


try:
    setup_logging()
    setup_global_error_handlers()
except Exception:
    pass
