import os
import re
import json
import time
import random
import requests
from typing import Any, Dict, Tuple
from .util import get_logger, short
log = get_logger()

# --- Config from ENV with sane defaults ---
NOUS_API_KEY = os.getenv("NOUS_API_KEY", "")
NOUS_BASE_URL = os.getenv("NOUS_BASE_URL", "https://api.nousresearch.com/v1")
NOUS_MODEL = os.getenv("NOUS_MODEL", "hermes-3-llama-3.1-70b")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nousresearch/hermes-3-llama-3.1-70b")

LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))

ALLOWED_TYPES = {"erc20_fixed", "erc20_mintable", "erc20_capped_burnable"}

SYSTEM_PROMPT = (
    "You generate compact JSON token specs. Output STRICT JSON only. "
    "Schema: {\"kind\": one of ['erc20_fixed','erc20_mintable','erc20_capped_burnable'], "
    "\"params\": {\"name\": str, \"symbol\": str, \"decimals\": int, "
    "\"initial_supply\": str, \"cap\": str (opt)}}"
)

# -------------------- LLM helpers --------------------
def _safe_post(url: str, headers: dict, payload: dict, timeout: int, retries: int = 3, backoff: float = 0.8):
    for i in range(retries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if r.status_code >= 400:
                try:
                    body = r.json()
                except Exception:
                    body = {"text": r.text[:1000]}
                # Auto-fix invalid model id for OpenRouter
                body_dump = json.dumps(body)
                if r.status_code == 400 and "not a valid model ID" in body_dump and "model" in payload:
                    bad = payload.get("model")
                    fallback = "nousresearch/hermes-3-llama-3.1-70b"
                    print(f"[LLM] invalid model '{bad}', fallback to {fallback}")
                    payload["model"] = fallback
                    continue
                print(f"[LLM] HTTP {r.status_code} {url} body={body}")
                r.raise_for_status()
            return r.json()
        except requests.exceptions.ConnectionError as e:
            print(f"[LLM] network error: {e} (attempt {i+1}/{retries})")
            if i == retries - 1:
                raise
            time.sleep(backoff * (2 ** i))
        except Exception:
            raise

def _call_nous(user: str) -> Dict[str, Any]:
    if not NOUS_API_KEY:
        raise RuntimeError("NOUS_API_KEY not set")
    url = f"{NOUS_BASE_URL}/chat/completions"
    payload = {
        "model": NOUS_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "temperature": 0.6,
        "max_tokens": 256,
    }
    headers = {"Authorization": f"Bearer {NOUS_API_KEY}"}
    return _safe_post(url, headers, payload, LLM_TIMEOUT)

def _call_openrouter(user: str) -> Dict[str, Any]:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    url = f"{OPENROUTER_BASE_URL}/chat/completions"
    model = OPENROUTER_MODEL or "openrouter/auto"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "temperature": 0.6,
        "max_tokens": 256,
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://local.dev",
        "X-Title": "og-auto",
        "Content-Type": "application/json",
    }
    return _safe_post(url, headers, payload, LLM_TIMEOUT)

def _local_fallback(owner_addr: str) -> Dict[str, Any]:
    return {
        "kind": "erc20_capped_burnable",
        "params": {
            "name": f"Farm{random.randint(100,999)}",
            "symbol": f"F{random.randint(10,99)}",
            "decimals": 18,
            "initial_supply": "1000000000000000000000",
            "cap": "100000000000000000000000",
        }
    }

def selection_from_llm(owner_addr: str) -> Dict[str, Any]:
    prompt = f"Owner: {owner_addr}. Generate ERC20 spec JSON only."
    sel = None
    try:
        data = _call_nous(prompt)
        content = data["choices"][0]["message"]["content"]
        sel = json.loads(content)
        print("[LLM] provider=nous ok")
    except Exception as e:
        print("[LLM] nous failed, fallback to openrouter:", e)
        try:
            data = _call_openrouter(prompt)
            content = data["choices"][0]["message"]["content"]
            sel = json.loads(content)
            print("[LLM] provider=openrouter ok")
        except Exception as e2:
            print("[LLM] openrouter failed, using local defaults:", e2)
            sel = _local_fallback(owner_addr)

    # sanitize & defaults
    kind = sel.get("kind", "")
    if kind not in ALLOWED_TYPES:
        sel["kind"] = "erc20_capped_burnable"
    p = sel.setdefault("params", {})
    p.setdefault("name", f"Farm{random.randint(100,999)}")
    p.setdefault("symbol", f"F{random.randint(10,99)}")
    try:
        p["decimals"] = max(0, min(18, int(p.get("decimals", 18))))
    except Exception:
        p["decimals"] = 18
    if not isinstance(p.get("initial_supply"), str):
        p["initial_supply"] = str(int(p.get("initial_supply", 10**18)))
    if sel["kind"] == "erc20_capped_burnable" and not isinstance(p.get("cap"), str):
        p["cap"] = str(int(p.get("cap", 10**23)))
    return sel

# -------------------- Solidity generation --------------------
SOLC_VERSION = os.getenv("SOLC_VERSION", "0.8.20")

def _esc(s: str) -> str:
    return str(s).replace("\\", "\\\\").replace('"', '\\"')

IDENT_FALLBACK = "Token"
def _to_contract_identifier(s: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", s or "")
    if not parts:
        return IDENT_FALLBACK
    camel = "".join(p.capitalize() for p in parts)
    if not re.match(r"[A-Za-z_]", camel[0]):
        camel = "X" + camel
    return camel

def _build_source(sel: Dict[str, Any]) -> Tuple[str, str, int, str]:
    p = sel.get("params", {})
    token_name_str = _esc(p.get("name", "FarmToken"))
    symbol = _esc(p.get("symbol", "FARM"))
    decimals = max(0, min(18, int(p.get("decimals", 18))))
    initial = int(p.get("initial_supply", str(10**18)))
    kind = sel.get("kind", "erc20_fixed")

    contract_name = _to_contract_identifier(token_name_str)
    pragma = SOLC_VERSION

    base = f"""// SPDX-License-Identifier: MIT
pragma solidity {pragma};

contract {contract_name} {{
    string public name = "{token_name_str}";
    string public symbol = "{symbol}";
    uint8  public decimals = {decimals};
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    constructor(uint256 initialSupply) {{
        totalSupply = initialSupply;
        balanceOf[msg.sender] = initialSupply;
        emit Transfer(address(0), msg.sender, initialSupply);
    }}

    function transfer(address to, uint256 value) public returns (bool) {{
        require(balanceOf[msg.sender] >= value, "insufficient");
        unchecked {{ balanceOf[msg.sender] -= value; }}
        balanceOf[to] += value;
        emit Transfer(msg.sender, to, value);
        return true;
    }}

    function approve(address spender, uint256 value) public returns (bool) {{
        allowance[msg.sender][spender] = value;
        emit Approval(msg.sender, spender, value);
        return true;
    }}

    function transferFrom(address from, address to, uint256 value) public returns (bool) {{
        require(balanceOf[from] >= value, "insufficient");
        require(allowance[from][msg.sender] >= value, "allowance");
        unchecked {{ allowance[from][msg.sender] -= value; balanceOf[from] -= value; }}
        balanceOf[to] += value;
        emit Transfer(from, to, value);
        return true;
    }}
}}
"""

    if kind == "erc20_mintable":
        ext = """
function mint(address to, uint256 amount) public returns (bool) {
    totalSupply += amount;
    balanceOf[to] += amount;
    emit Transfer(address(0), to, amount);
    return true;
}
"""
        source = base.replace("}\n}", ext + "}")
    elif kind == "erc20_capped_burnable":
        cap = int(p.get("cap", str(10**23)))
        ext = f"""
uint256 public cap = {cap};
function mint(address to, uint256 amount) public returns (bool) {{
    require(totalSupply + amount <= cap, "cap exceeded");
    totalSupply += amount;
    balanceOf[to] += amount;
    emit Transfer(address(0), to, amount);
    return true;
}}
function burn(uint256 amount) public returns (bool) {{
    require(balanceOf[msg.sender] >= amount, "insufficient");
    unchecked {{ balanceOf[msg.sender] -= amount; totalSupply -= amount; }}
    emit Transfer(msg.sender, address(0), amount);
    return true;
}}
"""
        source = base.replace("}\n}", ext + "}")
    else:
        source = base

    return source, contract_name, initial, token_name_str

# -------------------- Compile & deploy --------------------
from web3 import Web3
from solcx import compile_standard, set_solc_version, install_solc

try:
    set_solc_version(SOLC_VERSION)
except Exception:
    install_solc(SOLC_VERSION)
    set_solc_version(SOLC_VERSION)

def deploy_token_from_selection(w3: Web3, acct, sel: Dict[str, Any]) -> Dict[str, Any]:
    source, contract_name, initial, display_name = _build_source(sel)
    std = {
        "language": "Solidity",
        "sources": {f"{contract_name}.sol": {"content": source}},
        "settings": {"outputSelection": {"*": {"*": ["abi","evm.bytecode.object"]}}}
    }
    out = compile_standard(std, solc_version=SOLC_VERSION)
    key = list(out["contracts"][f"{contract_name}.sol"].keys())[0]
    abi = out["contracts"][f"{contract_name}.sol"][key]["abi"]
    bytecode = out["contracts"][f"{contract_name}.sol"][key]["evm"]["bytecode"]["object"]

    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = w3.eth.get_transaction_count(acct.address)
    tx = Contract.constructor(initial).build_transaction({
        "from": acct.address,
        "nonce": nonce,
        "gas": int(os.getenv("DEPLOY_GAS_LIMIT", "800000")),
        "gasPrice": w3.eth.gas_price
    })
    signed = acct.sign_transaction(tx)
    txh = w3.eth.send_raw_transaction(signed.rawTransaction)
    rec = w3.eth.wait_for_transaction_receipt(txh, timeout=int(os.getenv("DEPLOY_TIMEOUT", "180")))
    addr = rec.contractAddress
    log.info(f"deploy {contract_name} address={address} tx={short(txh.hex())}")
    return {"address": addr, "tx": txh.hex(), "abi": abi, "name": contract_name, "display_name": display_name}