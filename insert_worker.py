#!/usr/bin/env python3
"""
store_worker_and_launchers.py
• Ensures llm_queue_worker (full code) is in automation_scripts
• Ensures run_worker_bash / run_worker_ps point to it via parent_script_id
"""

import sqlite3, textwrap, sys

DB = "neuroca_temporal_analysis.db"

# ─────────────────── FULL WORKER CODE (v1.1.0) ───────────────────
worker_code = textwrap.dedent("""\
    \"\"\"llm_queue_worker.py – drains llm_write_queue
       Supports target_table = component_usage_analysis | component_issues | component_dependencies
       Version 1.1.0
    \"\"\"
    import json, sqlite3, time, traceback, sys

    DB        = "neuroca_temporal_analysis.db"
    POLL_SEC  = 2          # seconds between polling cycles
    BATCH     = 25         # rows per cycle

    # ──────────────────────────────────────────────────────────────
    def process_row(cur, row):
        \"\"\"Apply queue entry and update its status\"\"\"
        qid, target, op, payload, created_by = row
        try:
            data   = json.loads(payload)
            cid    = data.get("component_id")            # always required
            fields = data.get("fields", {})

            # ── Component Usage Analysis ──────────────────────────
            if target == "component_usage_analysis":
                if op == "INSERT":
                    cur.execute("SELECT 1 FROM component_usage_analysis WHERE component_id=?", (cid,))
                    if cur.fetchone():
                        raise ValueError("component_id already exists")
                    cols, vals = zip(*fields.items()) if fields else ((), ())
                    cur.execute(
                        f"INSERT INTO component_usage_analysis "
                        f"(component_id{(','+','.join(cols)) if cols else ''}) "
                        f"VALUES (?{(','+','.join('?'*len(vals))) if vals else ''})",
                        (cid, *vals))
                elif op == "UPDATE":
                    if not fields:
                        raise ValueError("UPDATE requires fields")
                    set_sql = ",".join([f"{k}=?" for k in fields])
                    cur.execute(
                        f"UPDATE component_usage_analysis SET {set_sql} WHERE component_id=?",
                        (*fields.values(), cid))

            # ── Component Issues ─────────────────────────────────
            elif target == "component_issues":
                if op == "INSERT":
                    required = {"issue_description", "severity"}
                    if not required.issubset(fields):
                        raise ValueError(f"INSERT requires {required}")
                    cur.execute(
                        \"\"\"INSERT INTO component_issues
                               (component_id, issue_description, severity, issue_type,
                                created_by, resolved, is_active)
                               VALUES (?,?,?,?,?,0,1)\"\"\", (
                               cid,
                               fields["issue_description"],
                               fields["severity"],
                               fields.get("issue_type", "bug"),
                               created_by))
                elif op == "UPDATE":
                    iid = fields.pop("issue_id", None)
                    if iid is None:
                        raise ValueError("UPDATE requires issue_id")
                    if not fields:
                        raise ValueError("No columns to update")
                    set_sql = ",".join([f"{k}=?" for k in fields])
                    cur.execute(
                        f"UPDATE component_issues SET {set_sql} WHERE issue_id=?",
                        (*fields.values(), iid))

            # ── Component Dependencies ───────────────────────────
            elif target == "component_dependencies":
                if op == "INSERT":
                    if "depends_on" not in fields:
                        raise ValueError("INSERT requires depends_on")
                    cur.execute(
                        \"\"\"INSERT INTO component_dependencies
                               (component_id, depends_on, dependency_type,
                                created_by, is_active)
                               VALUES (?,?,?,?,1)\"\"\", (
                               cid,
                               fields["depends_on"],
                               fields.get("dependency_type", "requires"),
                               created_by))
                elif op == "UPDATE":
                    did = fields.pop("dependency_id", None)
                    if did is None:
                        raise ValueError("UPDATE requires dependency_id")
                    if not fields:
                        raise ValueError("No columns to update")
                    set_sql = ",".join([f"{k}=?" for k in fields])
                    cur.execute(
                        f"UPDATE component_dependencies SET {set_sql} WHERE dependency_id=?",
                        (*fields.values(), did))

            else:
                raise ValueError("unknown target_table")

            # mark success
            cur.execute(
                "UPDATE llm_write_queue SET status='applied', processed_at=CURRENT_TIMESTAMP "
                "WHERE queue_id=?", (qid,))

        except Exception as e:
            # capture failure reason
            cur.execute(
                "UPDATE llm_write_queue SET status='error', error_msg=? WHERE queue_id=?",
                (str(e)[:400], qid))
            traceback.print_exc()

    # ───────────────────────── main loop ─────────────────────────
    def main():
        while True:
            with sqlite3.connect(DB) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    \"\"\"SELECT queue_id, target_table, op_type,
                              payload_json, created_by
                         FROM llm_write_queue
                         WHERE status='pending'
                         ORDER BY queue_id
                         LIMIT ?\"\"\", (BATCH,))
                for row in cur.fetchall():
                    process_row(cur, row)
                conn.commit()
            time.sleep(POLL_SEC)

    if __name__ == "__main__":
        sys.exit(main())
""")

# ─────────────────── bash launcher ───────────────────
bash_launcher = textwrap.dedent(r'''\
#!/usr/bin/env bash
DB="neuroca_temporal_analysis.db"
code=$(sqlite3 "$DB" \
  "SELECT script_code FROM automation_scripts \
    WHERE script_name='llm_queue_worker' AND is_active=1 \
    ORDER BY created_at DESC LIMIT 1;")
[[ -z "$code" ]] && { echo "worker not found" >&2; exit 1; }
tmp=$(mktemp --suffix=.py)
printf "%s\n" "$code" > "$tmp"
python "$tmp"
''')

# ───────────────── PowerShell launcher ─────────────────
ps_launcher = textwrap.dedent(r'''\
$DB = "neuroca_temporal_analysis.db"
$code = & sqlite3 $DB \
  "SELECT script_code FROM automation_scripts WHERE script_name='llm_queue_worker' AND is_active=1 ORDER BY created_at DESC LIMIT 1;"
if (-not $code) { Write-Error "worker not found"; exit 1 }
$tmp = [System.IO.Path]::GetTempFileName() + ".py"
$code | Out-File -Encoding UTF8 -FilePath $tmp
python $tmp
''')

# ─────────────────── insert / update rows ───────────────────
conn = sqlite3.connect(DB)
cur  = conn.cursor()

# 1️⃣  upsert worker, grab its script_id
cur.execute("""
    INSERT INTO automation_scripts (
        script_name, script_description, script_code,
        script_type, is_active, created_by, parent_script_id
    )
    VALUES ('llm_queue_worker',
            'Queue consumer v1.1.0 – CUA, Issues, Deps',
            ?, 'python', 1, 'schema_sync:loader', NULL)
    ON CONFLICT(script_name) DO UPDATE SET
        script_code        = excluded.script_code,
        script_description = excluded.script_description,
        is_active          = 1,
        created_by         = 'schema_sync:loader'
    RETURNING script_id;
""", (worker_code,))
worker_id = cur.fetchone()[0]

# 2️⃣  helper to upsert launchers linked to worker_id
def upsert(name, descr, code, stype):
    cur.execute("""
        INSERT INTO automation_scripts (
            script_name, script_description, script_code,
            script_type, is_active, created_by, parent_script_id
        )
        VALUES (?,?,?,?,1,'schema_sync:loader',?)
        ON CONFLICT(script_name) DO UPDATE SET
            script_code       = excluded.script_code,
            script_description= excluded.script_description,
            parent_script_id  = excluded.parent_script_id,
            is_active         = 1;
    """, (name, descr, code, stype, worker_id))

upsert("run_worker_bash", "bash launcher for llm_queue_worker",
       bash_launcher, "bash")
upsert("run_worker_ps", "PowerShell launcher for llm_queue_worker",
       ps_launcher, "powershell")

conn.commit()
conn.close()
print(f"✓ worker (id={worker_id}) and launchers stored & linked")
