import os
import signal
import subprocess
import time


def _log(logger, message):
    if logger and hasattr(logger, "info"):
        logger.info(message)
    else:
        print(message)


def list_note_monitor_processes(script_paths):
    normalized_paths = {
        os.path.normcase(os.path.normpath(path))
        for path in script_paths
        if path
    }
    if not normalized_paths:
        return []

    try:
        output = subprocess.check_output(
            ["ps", "-axo", "pid=,ppid=,command="],
            text=True,
        )
    except Exception:
        return []

    processes = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        command = parts[2]
        command_norm = os.path.normcase(os.path.normpath(command))
        matched_path = None
        for path in normalized_paths:
            if path in command_norm:
                matched_path = path
                break
        if matched_path is None:
            continue
        processes.append(
            {
                "pid": pid,
                "ppid": ppid,
                "command": command,
                "script_path": matched_path,
            }
        )
    return processes


def terminate_note_monitor_processes(
    script_paths,
    keep_pids=None,
    logger=None,
    grace_seconds=3.0,
):
    keep_pids = set(keep_pids or [])
    victims = [
        proc
        for proc in list_note_monitor_processes(script_paths)
        if proc["pid"] not in keep_pids and proc["pid"] != os.getpid()
    ]
    if not victims:
        return []

    for proc in victims:
        try:
            _log(
                logger,
                f"🧹 [NoteMonitor] 清理残留监听器 PID={proc['pid']} PPID={proc['ppid']}",
            )
            os.kill(proc["pid"], signal.SIGTERM)
        except ProcessLookupError:
            continue
        except Exception as e:
            _log(logger, f"⚠️ [NoteMonitor] 发送 SIGTERM 失败 PID={proc['pid']}: {e}")

    deadline = time.time() + max(grace_seconds, 0)
    remaining = {proc["pid"]: proc for proc in victims}
    while remaining and time.time() < deadline:
        time.sleep(0.1)
        for pid in list(remaining):
            try:
                os.kill(pid, 0)
            except OSError:
                remaining.pop(pid, None)

    for pid, proc in list(remaining.items()):
        try:
            _log(logger, f"💀 [NoteMonitor] 强制结束残留监听器 PID={pid}")
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception as e:
            _log(logger, f"⚠️ [NoteMonitor] 发送 SIGKILL 失败 PID={pid}: {e}")

    return victims
