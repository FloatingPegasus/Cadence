from pathlib import Path
import fcntl
import os


class RuntimeLockError(RuntimeError):
    pass


class RuntimeLock:
    def __init__(self, path: Path):
        self.path = path.expanduser().resolve()
        self._descriptor: int | None = None

    def acquire(self) -> None:
        if self._descriptor is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(
                descriptor,
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
            os.ftruncate(descriptor, 0)
            os.write(descriptor, str(os.getpid()).encode())
        except BlockingIOError as error:
            os.close(descriptor)
            raise RuntimeLockError(
                "Cadence is running. Stop the API before restoring."
            ) from error
        self._descriptor = descriptor

    def release(self) -> None:
        if self._descriptor is None:
            return
        fcntl.flock(self._descriptor, fcntl.LOCK_UN)
        os.close(self._descriptor)
        self._descriptor = None

    def __enter__(self) -> "RuntimeLock":
        self.acquire()
        return self

    def __exit__(self, *_args: object) -> None:
        self.release()
