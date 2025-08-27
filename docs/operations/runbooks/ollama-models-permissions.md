# Runbook: Fixing Ollama OLLAMA_MODELS permission errors on Linux

Symptom
- When starting the local Ollama server:
  - Example error:
    - `Error: mkdir /media/justin/Samsung_4TB1: permission denied: ensure path elements are traversable`
- Environment shows OLLAMA_MODELS points to a path you cannot write:
  - From ollama logs: `OLLAMA_MODELS:/media/justin/Samsung_4TB1/models/ollama`

Root cause
- The process user (e.g., `justin`) lacks write and/or execute (traverse) permission on one or more path elements:
  - The mountpoint (e.g., `/media/justin/Samsung_4TB1`) and/or its subdirectories do not allow traversal/write for your user
  - On NTFS/exFAT filesystems, ownership/permissions are controlled by mount options (uid/gid/umask)
  - On ext4/XFS, standard Unix permissions and ownership apply

Quick remediation (recommended)
- Point OLLAMA_MODELS to a path you already own and can write to (e.g., under `/mnt/samsung_4tb` or `$HOME`):
  - Session-only:
    - `export OLLAMA_MODELS=/mnt/samsung_4tb/models/ollama`
    - `mkdir -p "$OLLAMA_MODELS"`
  - Persistent (shell profile):
    - Add to your shell profile (`~/.bashrc` or `~/.zshrc`):
      - `export OLLAMA_MODELS=/mnt/samsung_4tb/models/ollama`
    - Then create it once: `mkdir -p /mnt/samsung_4tb/models/ollama`

Verification commands
- Check current value:
  - `echo "$OLLAMA_MODELS"`
- Check filesystem type (guides mount options below):
  - `stat -f -c %T "$(dirname "$OLLAMA_MODELS")"`
  - Common output:
    - `ext2/ext3/ext4` → native permissions (use `chown`/`chmod`)
    - `fuseblk` → NTFS (use mount options)
    - `exfat` → exFAT (use mount options)

Fixes by filesystem type

A) ext4/XFS (native Linux fs)
1) Ensure directory exists and is owned by your user:
   - `sudo mkdir -p /media/justin/Samsung_4TB1/models/ollama`
   - `sudo chown -R justin:justin /media/justin/Samsung_4TB1/models`
2) Ensure traverse (execute) permission on each path element:
   - `sudo chmod u+rwx /media/justin/Samsung_4TB1`
   - `sudo chmod -R u+rwX /media/justin/Samsung_4TB1/models`
3) Run:
   - `OLLAMA_MODELS=/media/justin/Samsung_4TB1/models/ollama ollama serve`

B) exFAT/NTFS (non-native; permissions via mount options)
1) Identify the device:
   - `findmnt /media/justin/Samsung_4TB1` or `lsblk -f`
2) Temporary remount with ownership to your user (uid/gid), and sane masks:
   - NTFS (fuseblk):
     - `sudo umount /media/justin/Samsung_4TB1`
     - `sudo mount -t ntfs3 -o uid=$(id -u),gid=$(id -g),umask=022 /dev/sdXN /media/justin/Samsung_4TB1`
   - exFAT:
     - `sudo umount /media/justin/Samsung_4TB1`
     - `sudo mount -t exfat -o uid=$(id -u),gid=$(id -g),umask=022 /dev/sdXN /media/justin/Samsung_4TB1`
   - Replace `/dev/sdXN` with your actual device from lsblk/findmnt
3) Create models directory:
   - `mkdir -p /media/justin/Samsung_4TB1/models/ollama`
4) Run:
   - `OLLAMA_MODELS=/media/justin/Samsung_4TB1/models/ollama ollama serve`
5) Persist across reboots (fstab example):
   - NTFS (kernel ntfs3 driver):
     - `/dev/sdXN  /media/justin/Samsung_4TB1  ntfs3  uid=1000,gid=1000,umask=022,defaults  0  0`
   - exFAT:
     - `/dev/sdXN  /media/justin/Samsung_4TB1  exfat  uid=1000,gid=1000,umask=022,defaults  0  0`
   - After editing `/etc/fstab`:
     - `sudo mount -a` (check for errors)

Alternative: use a home-local path (simplest)
- Avoid system mounts entirely:
  - `export OLLAMA_MODELS="$HOME/.ollama/models"`
  - `mkdir -p "$OLLAMA_MODELS"`
  - `ollama serve`

Systemd integration (optional, for system service)
- If running Ollama via systemd, set environment in a drop-in:
  - `sudo systemctl edit ollama`
  - Add:
    ```
    [Service]
    Environment=OLLAMA_MODELS=/mnt/samsung_4tb/models/ollama
    ```
  - Then:
    - `sudo systemctl daemon-reload`
    - `sudo systemctl restart ollama`
- Ensure the service user has write permission to the directory you configured

Sanity checks
- Confirm write/access on the final path:
  - `test -w "$OLLAMA_MODELS" && echo "writable" || echo "not writable"`
  - `touch "$OLLAMA_MODELS/.perm_check" && rm "$OLLAMA_MODELS/.perm_check"`
- Start the server and pull a small model:
  - `ollama serve` (in one terminal)
  - `ollama pull gemma3:4b` (in another)
- Then test Neuroca CLI:
  - `neuroca llm query "Say hello." --provider ollama --model gemma3:4b --no-memory --no-health --no-goals`

Notes
- Exposing your external drive under `/media/...` is fine, but permissions often default to root-owned; set uid/gid with mount options (exFAT/NTFS) or use chown (ext4/XFS).
- If you see “permission denied: ensure path elements are traversable,” fix permissions for each parent directory in the path — a single non-executable (no +x) directory in the chain will block traversal.

Related Docs
- Neuroca Quickstart: ['_Neuroca/docs/guides/local-llm-quickstart.md'](_Neuroca/docs/guides/local-llm-quickstart.md:1)