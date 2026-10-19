"""The bot's own SSH key on a server: put it into the login user's ``authorized_keys``, check it,
take it back off.

Passwords are not stored. After one login with a password the bot appends its own public key to
that login user's ~/.ssh/authorized_keys and checks that a FRESH login with only that key works
(``key_ok``); later logins use the key (sealed with VAULT_KEY in ``ops_keys``). Forgetting a server
takes the key back off it. Everything runs as the login user, not root: it is their file.
"""

from __future__ import annotations

import asyncio
import shlex
from dataclasses import dataclass

import asyncssh

from gozar.ops.errors import RemoteError
from gozar.ops.ssh import Server


def key_blob(public_key: str) -> str:
    """'ssh-ed25519 AAAA… comment' -> 'AAAA…' (what identifies the key in authorized_keys)."""
    parts = public_key.split()
    if len(parts) < 2:
        raise ValueError("not an OpenSSH public key")
    return parts[1]


# ======================================================================================
# authorized_keys of the login user (runs as that user, not root: it is their file)
# ======================================================================================

INSTALL_KEY = r"""
[ -n "$HOME" ] && [ -d "$HOME" ] || { echo "@@NOHOME"; exit 0; }
d="$HOME/.ssh"; f="$d/authorized_keys"
umask 077
mkdir -p "$d" || { echo "@@FAIL mkdir $d"; exit 0; }
chmod 700 "$d"
if [ -f "$f" ] && grep -F "$BLOB" "$f" >/dev/null 2>&1; then
  echo "@@HAD"
else
  # a last line without a newline would be glued to ours and break both keys
  if [ -s "$f" ] && [ -n "$(tail -c 1 "$f")" ]; then printf '\n' >> "$f" || { echo "@@FAIL write $f"; exit 0; }; fi
  printf '%s\n' "$KEY" >> "$f" || { echo "@@FAIL write $f"; exit 0; }
  echo "@@ADDED"
fi
chmod 600 "$f"
command -v restorecon >/dev/null 2>&1 && restorecon -R "$d" >/dev/null 2>&1
echo "@@KEYS $(grep -cvE '^[[:space:]]*(#|$)' "$f" 2>/dev/null)"
"""

REMOVE_KEY = r"""
f="$HOME/.ssh/authorized_keys"
[ -f "$f" ] || { echo "@@NOTHERE"; exit 0; }
grep -F "$BLOB" "$f" >/dev/null 2>&1 || { echo "@@NOTHERE"; exit 0; }
t=$(mktemp "$HOME/.ssh/.gozar.XXXXXX") || { echo "@@FAIL mktemp"; exit 0; }
grep -vF "$BLOB" "$f" > "$t"
cat "$t" > "$f"; rc=$?; rm -f "$t"      # cat > keeps the file's owner, mode and SELinux label
[ "$rc" = 0 ] && echo "@@REMOVED" || echo "@@FAIL write $f"
"""


@dataclass
class KeyInstall:
    added: bool  # False = it was there already
    keys_total: int  # usable lines in authorized_keys afterwards (ours included)


async def install_key(srv: Server, public_key: str) -> KeyInstall:
    script = (
        f"KEY={shlex.quote(public_key.strip())}\nBLOB={shlex.quote(key_blob(public_key))}\n"
        + INSTALL_KEY
    )
    r = await srv.run_user(script, what="نصب کلید ربات")
    if "@@NOHOME" in r.out:
        raise RemoteError(f"کاربر {srv.creds.username} پوشهٔ خانه ندارد؛ کلید نصب نشد")
    if "@@FAIL" in r.out or ("@@ADDED" not in r.out and "@@HAD" not in r.out):
        raise RemoteError("نوشتن ~/.ssh/authorized_keys نشد", r.tail(5))
    total = 0
    for line in r.out.splitlines():
        if line.startswith("@@KEYS "):
            v = line.split()[1] if len(line.split()) > 1 else ""
            total = int(v) if v.isdigit() else 0
    return KeyInstall(added="@@ADDED" in r.out, keys_total=total)


KEYS_INFO = r"""
f="$HOME/.ssh/authorized_keys"
n=$(grep -cvE '^[[:space:]]*(#|$)' "$f" 2>/dev/null); echo "@@KEYS ${n:-0}"
grep -F "$BLOB" "$f" >/dev/null 2>&1 && echo "@@OURS"
"""


async def keys_info(srv: Server, public_key: str) -> tuple[int, bool]:
    """(usable lines in the login user's authorized_keys, is the bot key one of them)."""
    r = await srv.run_user(
        f"BLOB={shlex.quote(key_blob(public_key))}\n" + KEYS_INFO, what="کلیدهای SSH"
    )
    total = 0
    for line in r.out.splitlines():
        if line.startswith("@@KEYS "):
            v = line.split()[-1]
            total = int(v) if v.isdigit() else 0
    return total, "@@OURS" in r.out


async def remove_key(srv: Server, public_key: str) -> bool:
    """True if the key was there and is gone now."""
    r = await srv.run_user(
        f"BLOB={shlex.quote(key_blob(public_key))}\n" + REMOVE_KEY, what="برداشتن کلید ربات"
    )
    if "@@FAIL" in r.out:
        raise RemoteError("برداشتن کلید از ~/.ssh/authorized_keys نشد", r.tail(5))
    return "@@REMOVED" in r.out


# ======================================================================================
# checks from outside (a new connection, like the admin's next login)
# ======================================================================================


async def key_login_works(
    host: str,
    port: int,
    user: str,
    key: asyncssh.SSHKey,
    host_key: asyncssh.SSHKey | None,
    timeout: int = 20,
) -> str | None:
    """None if a FRESH login with only this key works; otherwise why not."""
    known = ([host_key], [], []) if host_key is not None else None
    try:
        conn = await asyncio.wait_for(
            asyncssh.connect(
                host,
                port,
                username=user,
                client_keys=[key],
                password=None,
                agent_path=None,
                config=None,
                known_hosts=known,
                preferred_auth="publickey",
                connect_timeout=timeout,
            ),
            timeout + 5,
        )
    except asyncssh.PermissionDenied:
        return "سرور کلید ربات را قبول نکرد"
    except asyncssh.HostKeyNotVerifiable:
        return "کلید SSH سرور عوض شد"
    except TimeoutError:
        return "جواب نداد (timeout)"
    except (OSError, asyncssh.Error) as e:
        return f"وصل نشد: {e}"
    try:
        r = await conn.run("true", check=False, timeout=20)
        return None if r.exit_status == 0 else f"بعد از ورود دستور اجرا نشد (کد {r.exit_status})"
    except (OSError, asyncssh.Error) as e:
        return f"بعد از ورود قطع شد: {e}"
    finally:
        conn.close()
