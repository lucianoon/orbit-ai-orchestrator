import asyncio, tempfile, textwrap, os, sys, shutil
from settings import settings


def _make_runner(user_code_path: str, timeout: int, mem_mb: int, fsize_mb: int) -> str:
    """Creates a small runner script that applies rlimits then execs the user code."""
    runner_src = f"""
import resource, runpy, sys, signal
resource.setrlimit(resource.RLIMIT_CPU, ({timeout},{timeout}))
resource.setrlimit(resource.RLIMIT_AS, ({mem_mb*1024*1024},{mem_mb*1024*1024}))
resource.setrlimit(resource.RLIMIT_FSIZE, ({fsize_mb*1024*1024},{fsize_mb*1024*1024}))
resource.setrlimit(resource.RLIMIT_CORE, (0,0))
signal.signal(signal.SIGXCPU, lambda *args: sys.exit(124))
signal.signal(signal.SIGXFSZ, lambda *args: sys.exit(125))
runpy.run_path("{user_code_path}", run_name="__main__")
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(runner_src)
        return f.name


async def run_python(instruction: str):
    code = textwrap.dedent(instruction)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        user_code_path = f.name

    runner_path = _make_runner(
        user_code_path,
        timeout=max(1, settings.code_timeout),
        mem_mb=max(32, settings.code_mem_mb),
        fsize_mb=max(1, settings.code_fsize_mb),
    )

    use_nsjail = shutil.which("nsjail") is not None
    mem_bytes = max(32, settings.code_mem_mb) * 1024 * 1024
    fsize_bytes = max(1, settings.code_fsize_mb) * 1024 * 1024

    cmd = [
        sys.executable, runner_path
    ]

    if use_nsjail:
        cmd = [
            "nsjail",
            "--quiet",
            "--time_limit", str(settings.code_timeout),
            "--max_cpus", "1",
            "--rlimit_as", str(mem_bytes),
            "--rlimit_fsize", str(fsize_bytes),
            "--rlimit_core", "0",
            "--disable_proc",
            "--",
            sys.executable,
            user_code_path,
        ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        out, err = await asyncio.wait_for(proc.communicate(), timeout=settings.code_timeout + 2)
        output = out.decode() or err.decode() or "sem saída"
    except asyncio.TimeoutError:
        output = "timeout ao rodar código"
    finally:
        for p in (user_code_path, runner_path):
            try:
                os.remove(p)
            except OSError:
                pass
    if len(output) > 4000:
        output = output[:4000] + "...(truncado)"
    return output.strip(), [{"artifact": user_code_path}]
