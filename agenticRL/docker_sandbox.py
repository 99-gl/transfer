"""Docker implementation of Slime's small agent Sandbox protocol.

Each instance creates one detached, disposable container from a task image.
The task image must already contain a clean repository and its test dependencies.
"""

from __future__ import annotations

import asyncio
import io
import os
import tarfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slime.agent.sandbox import ExecResult, FileContent


class DockerSandbox:
    """A fresh local Docker container usable by Slime's coding-agent harness."""

    def __init__(self, image: str) -> None:
        self.image = image
        self.network = os.environ.get("SLIME_AGENT_DOCKER_NETWORK", "bridge")
        self.pull = os.environ.get("SLIME_AGENT_DOCKER_PULL", "0") == "1"
        self._client = None
        self._container = None
        self.sandbox_id = ""

    async def __aenter__(self) -> "DockerSandbox":
        import docker

        self._client = docker.from_env()
        await asyncio.to_thread(self._client.ping)
        if self.pull:
            await asyncio.to_thread(self._client.images.pull, self.image)
        # host.docker.internal reaches the Ray worker that owns this adapter.
        # Docker 20.10+ resolves host-gateway on Linux.
        self._container = await asyncio.to_thread(
            self._client.containers.run,
            self.image,
            command=["sleep", "infinity"],
            detach=True,
            user="root",
            network=self.network,
            extra_hosts={"host.docker.internal": "host-gateway"},
            labels={"slime.agentic_rl": "true"},
        )
        self.sandbox_id = self._container.short_id
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._container is not None:
            try:
                await asyncio.to_thread(self._container.remove, force=True)
            finally:
                self._container = None
        if self._client is not None:
            await asyncio.to_thread(self._client.close)
            self._client = None

    def _require_container(self):
        if self._container is None:
            raise RuntimeError("DockerSandbox is not active")
        return self._container

    async def exec(
        self,
        cmd: str,
        *,
        user: str = "root",
        env: dict[str, str] | None = None,
        timeout: int = 120,
        check: bool = False,
    ) -> "ExecResult":
        """Run bash in the container; enforce timeout from the host side."""
        container = self._require_container()

        def run():
            return container.exec_run(
                ["/bin/bash", "-lc", cmd],
                user=user,
                environment=env,
                demux=True,
            )

        try:
            result = await asyncio.wait_for(asyncio.to_thread(run), timeout=timeout)
        except TimeoutError:
            message = f"docker exec timed out after {timeout}s: {cmd[:160]}"
            if check:
                raise RuntimeError(message) from None
            return 124, "", message

        stdout, stderr = result.output or (b"", b"")
        out = (stdout or b"").decode("utf-8", errors="replace")
        err = (stderr or b"").decode("utf-8", errors="replace")
        if check and result.exit_code != 0:
            raise RuntimeError(f"docker exec failed (exit={result.exit_code}): {cmd[:160]}\n{err[:400]}")
        return result.exit_code, out, err

    async def write_file(self, sandbox_path: str, content: "FileContent", *, user: str = "root") -> None:
        container = self._require_container()
        data = Path(content).read_bytes() if isinstance(content, Path) else content.encode() if isinstance(content, str) else content
        parent = str(Path(sandbox_path).parent)
        filename = Path(sandbox_path).name

        def put() -> None:
            archive = io.BytesIO()
            with tarfile.open(fileobj=archive, mode="w") as tf:
                info = tarfile.TarInfo(filename)
                info.size = len(data)
                info.mode = 0o644
                tf.addfile(info, io.BytesIO(data))
            archive.seek(0)
            container.put_archive(parent, archive.read())

        await self.exec(f"mkdir -p {parent}", user="root", check=True)
        await asyncio.to_thread(put)
        if user != "root":
            await self.exec(f"chown {user}:{user} {sandbox_path}", user="root", check=True)

    async def read_file(self, sandbox_path: str, *, user: str = "root") -> str:
        # Docker's archive API is root-scoped; all files written by this workflow
        # are readable by root. The user argument remains for Sandbox compatibility.
        del user
        container = self._require_container()

        def read() -> str:
            stream, _ = container.get_archive(sandbox_path)
            raw = b"".join(stream)
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as tf:
                member = tf.next()
                if member is None:
                    return ""
                fp = tf.extractfile(member)
                return (fp.read() if fp is not None else b"").decode("utf-8", errors="replace")

        try:
            return await asyncio.to_thread(read)
        except Exception:
            return ""
