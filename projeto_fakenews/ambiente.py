"""
Coleta a configuração experimental (processador, núcleos, RAM, SO, Python)
exigida pela proposta e salva em resultados/ambiente.json.

Uso:  python ambiente.py
"""

import json
import os
import platform
import sys


def nome_processador():
    if sys.platform == "win32":
        try:
            import winreg
            chave = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                   r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return winreg.QueryValueEx(chave, "ProcessorNameString")[0].strip()
        except OSError:
            pass
    elif os.path.exists("/proc/cpuinfo"):
        with open("/proc/cpuinfo") as f:
            for linha in f:
                if linha.startswith("model name"):
                    return linha.split(":", 1)[1].strip()
    return platform.processor()


def nucleos_fisicos():
    if sys.platform == "win32":
        import subprocess
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_Processor | Measure-Object NumberOfCores -Sum).Sum"],
                capture_output=True, text=True, timeout=20).stdout.strip()
            return int(out)
        except Exception:
            return None
    try:
        with open("/proc/cpuinfo") as f:
            ids = {l for l in f if l.startswith("core id")}
        return len(ids) or None
    except OSError:
        return None


def memoria_gb():
    if sys.platform == "win32":
        import ctypes

        class MEMSTAT(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MEMSTAT()
        m.dwLength = ctypes.sizeof(MEMSTAT)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return round(m.ullTotalPhys / 2 ** 30, 1)
    try:
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30, 1)
    except (ValueError, OSError):
        return None


def coletar():
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()
    return {
        "processador": nome_processador(),
        "nucleos_fisicos": nucleos_fisicos(),
        "nucleos_logicos": os.cpu_count(),
        "memoria_ram_gb": memoria_gb(),
        "sistema_operacional": f"{platform.system()} {platform.release()} ({platform.version()})",
        "arquitetura": platform.machine(),
        "linguagem": "Python",
        "interpretador": f"{platform.python_implementation()} {platform.python_version()}",
        "gil_ativo": gil,
        "ambiente_execucao": "processos locais; comunicação TCP via loopback (127.0.0.1)",
    }


if __name__ == "__main__":
    info = coletar()
    pasta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados")
    os.makedirs(pasta, exist_ok=True)
    with open(os.path.join(pasta, "ambiente.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)
    for k, v in info.items():
        print(f"{k:<22}: {v}")
