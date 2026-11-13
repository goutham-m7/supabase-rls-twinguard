"""Own a private, disposable PostgreSQL server; never accept an external DSN."""

from contextlib import contextmanager
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from uuid import uuid4

import psycopg
from psycopg import sql


def binary_directory() -> Path:
    explicit = os.environ.get("PG_BIN")
    if explicit:
        directory = Path(explicit)
    elif Path("/opt/homebrew/opt/postgresql@16/bin/postgres").is_file():
        directory = Path("/opt/homebrew/opt/postgresql@16/bin")
    else:
        config = shutil.which("pg_config")
        if not config:
            raise RuntimeError("Set PG_BIN to a PostgreSQL 16+ bin directory")
        directory = Path(subprocess.check_output([config, "--bindir"], text=True).strip())
    for executable in ("initdb", "pg_ctl", "postgres", "pg_dump"):
        if not (directory / executable).is_file():
            raise RuntimeError(
                "PostgreSQL binaries missing; set PG_BIN to a PostgreSQL 16+ bin directory"
            )
    version = subprocess.check_output([str(directory / "postgres"), "--version"], text=True)
    major = re.search(r"(\d+)\.", version)
    if major is None or int(major[1]) < 16:
        raise RuntimeError("PostgreSQL 16+ required; set PG_BIN to a supported binary directory")
    return directory


class Cluster:
    def __enter__(self):
        self.bin = binary_directory()
        self.temporary = tempfile.TemporaryDirectory(prefix="twinguard-", dir="/tmp")
        self.directory = self.temporary.name
        self.data = Path(self.directory) / "data"
        self.started = False
        try:
            self._run(
                "initdb",
                "-D",
                str(self.data),
                "-A",
                "trust",
                "-U",
                "postgres",
                "--no-locale",
                "-E",
                "UTF8",
            )
            self._run(
                "pg_ctl",
                "-D",
                str(self.data),
                "-l",
                str(Path(self.directory) / "server.log"),
                "-o",
                f"-F -k {self.directory} -h '' -p 55439 -c max_connections=20",
                "-w",
                "start",
            )
            self.started = True
            with self.connect() as conn:
                for role in ("authenticated", "anon", "fixture_owner"):
                    conn.execute(
                        sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT").format(
                            sql.Identifier(role)
                        )
                    )
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def _run(self, executable: str, *args: str):
        result = subprocess.run(
            [str(self.bin / executable), *args], capture_output=True, text=True, timeout=30
        )
        if result.returncode:
            raise RuntimeError(
                f"{executable} failed: {result.stderr.strip()} {result.stdout.strip()}"
            )

    def connect(self, database="postgres", user="postgres"):
        return psycopg.connect(
            host=self.directory,
            port=55439,
            dbname=database,
            user=user,
            connect_timeout=5,
            options="-c statement_timeout=5000 -c lock_timeout=1000",
        )

    @contextmanager
    def database(self):
        name = "attempt_" + uuid4().hex
        with self.connect() as conn:
            conn.autocommit = True
            conn.execute(
                sql.SQL("CREATE DATABASE {} OWNER fixture_owner").format(sql.Identifier(name))
            )
        try:
            with self.connect(name) as conn:
                conn.execute("CREATE SCHEMA auth")
                conn.execute("""CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
                    SELECT (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')::uuid
                    $$""")
                conn.execute("GRANT USAGE ON SCHEMA auth TO authenticated, anon, fixture_owner")
            yield name
        finally:
            with self.connect() as conn:
                conn.autocommit = True
                conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))

    def __exit__(self, *_):
        try:
            if self.started:
                self._run("pg_ctl", "-D", str(self.data), "-m", "immediate", "-w", "stop")
        finally:
            self.temporary.cleanup()
