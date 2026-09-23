"""Arena receipts harness — kev hash, MOTH rows, JEV decisions. stdlib only."""
import json, subprocess, time, pathlib

def kev(data) -> str:
    if not isinstance(data, (str, bytes)):
        data = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if isinstance(data, str):
        data = data.encode()
    h = 0xcbf29ce484222325
    for b in data:
        h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"0x{h:016x}"

def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def moth_row(kind: str, content: dict, severity: str = "INFO", path: str = "moth.jsonl") -> dict:
    """Append a MOTH ledger row (FINDING | VERDICT | REFUSAL). Returns the row."""
    row = {"kind": kind, "severity": severity, "content": content,
           "content_hash": kev(canonical(content)), "recorded": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    p = pathlib.Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f: f.write(canonical(row) + "\n")
    return row

def jev_decide(prompt: str, receipt_path: str, model: str = "jev-1.13.0") -> dict:
    """Route a design choice through the JEV proxy. ALWAYS writes the raw receipt.
    Falls back to a labeled UNVERIFIED mock if the proxy is unreachable."""
    receipt = {"model": model, "prompt": prompt, "ts": time.time()}
    try:
        out = subprocess.run(["curl", "-sS", "-m", "30", "-X", "POST",
            "https://ai-writings.pages.dev/api/jev/decide",
            "-H", "content-type: application/json",
            "-d", json.dumps({"model": model, "prompt": prompt})],
            capture_output=True, text=True, timeout=40)
        receipt["raw"] = out.stdout; receipt["stderr"] = out.stderr; receipt["rc"] = out.returncode
        # Non-2xx body is NOT a live verdict — the Registrar caught this marking
        # 400 error pages LIVE (HARNESS-JEV-LIVE-MISLABEL). Parse and gate on the
        # actual HTTP status before blessing anything.
        try:
            parsed = json.loads(out.stdout) if out.stdout.strip() else {}
        except Exception:
            parsed = {}
        http_st = parsed.get("status_code")
        if http_st is None:
            import re as _re
            m = _re.search(r'"status_code"\s*:\s*(\d+)', out.stdout)
            http_st = int(m.group(1)) if m else 0
        receipt["status"] = "LIVE" if (out.returncode == 0 and out.stdout.strip()
                                       and 200 <= int(http_st) < 300) else "UNVERIFIED"
    except Exception as e:
        receipt["raw"] = None; receipt["status"] = "UNVERIFIED"; receipt["error"] = repr(e)
    p = pathlib.Path(receipt_path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(receipt, indent=1))
    return receipt

# self-test vector (bytes-law): kev("café Δ 日本語") == 0x024a555471370b18d
if __name__ == "__main__":
    assert kev("café Δ 日本語") == "0x24a555471370b18d", kev("café Δ 日本語")
    print("receipts harness OK — café Δ 日本語 =", kev("café Δ 日本語"))
