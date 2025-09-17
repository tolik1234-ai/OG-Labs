# src/config.py
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple
from dotenv import load_dotenv

load_dotenv()

def _env(name: str, default: str = "") -> str:
    v = os.getenv(name, default).strip()
    return v

def _env_float(name: str, default: float) -> float:
    v = _env(name)
    return float(v) if v else float(default)

def _env_int(name: str, default: int) -> int:
    v = _env(name)
    return int(v) if v else int(default)

def _env_bool(name: str, default: bool) -> bool:
    v = _env(name)
    if not v:
        return default
    return v.lower() in ("1","true","yes","y","on")

def _env_csv(name: str) -> List[str]:
    raw = _env(name)
    if not raw: return []
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]

OG_RPC = _env("OG_RPC")

PRIVATE_KEYS: List[str] = _env_csv("PRIVATE_KEYS")

# Uniswap V3 addresses на Jaine (как мы уже использовали в логах)
ROUTER = _env("ROUTER", "0xb95B5953FF8ee5D5d9818CdbEfE363ff2191318c")
POS_MANAGER = _env("POS_MANAGER", "0x44f24B66b3BAa3A784dBeee9bFE602f15A2Cc5d9")
V3_FACTORY = _env("V3_FACTORY", "0x7453582657F056ce5CfcEeE9E31E4BC390fa2b3c")
V3_FEE = _env_int("V3_FEE", 500)  # 0.05%

# Токены (стандартные из твоих логов) — можно переопределить через .env, но и так ок
TOKENS: Dict[str,str] = {
    "WETH": _env("TOKEN_WETH", "0x0fE9B43625fA7EdD663aDcEC0728DD635e4AbF7c"),
    "USDC": _env("TOKEN_USDC", "0x3eC8A8705bE1D5ca90066b37ba62c4183B024ebf"),
    "TKN1": _env("TOKEN_TKN1","0x36f6414FF1df609214dDAbA71c84f18bcf00F67d"),
    "TKN2": _env("TOKEN_TKN2","0x78A8D4014000dF30b49eB0c29822B6C7C79D68cA"),
    "TKN3": _env("TOKEN_TKN3","0xba2aE6c8cddd628a087D7e43C1Ba9844c5Bf9638"),
    "TKN4": _env("TOKEN_TKN4","0x14d2F76020c1ECb29BcD673B51d8026C6836a66A"),
    "wAOGI": _env("wAOGI","0x006921B4B6DAc59342EA5e7d62f8351aeB65EEA8"),
}

# === Normalize TOKENS to a single shape and build reverse map ===
# Допускаем формы:
# - "SYM": {"address": "...", "decimals": 18}
# - "SYM": "0xADDRESS"                          (decimals берём из ENV <SYM>_DECIMALS или 18)
# - "SYM": ("0xADDRESS", 6) / ["0xADDRESS", 6]

def _to_int(x, default=18):
    try:
        return int(x)
    except Exception:
        return default

def _normalize_tokens(tokens: dict) -> dict:
    norm = {}
    for sym, meta in (tokens or {}).items():
        addr = None
        dec = 18
        if isinstance(meta, dict):
            addr = meta.get("address") or meta.get("addr")
            dec  = _to_int(meta.get("decimals", 18), 18)
        elif isinstance(meta, str):
            addr = meta
            dec  = _to_int(os.getenv(f"{sym}_DECIMALS", 18), 18)
        elif isinstance(meta, (list, tuple)) and len(meta) >= 1:
            addr = meta[0]
            dec  = _to_int(meta[1], _to_int(os.getenv(f"{sym}_DECIMALS", 18), 18)) if len(meta) > 1 else _to_int(os.getenv(f"{sym}_DECIMALS", 18), 18)
        # пропускаем битые записи без адреса
        if addr:
            norm[sym] = {"address": addr, "decimals": dec}
    return norm

# 1) нормализуем то, что уже есть в TOKENS
TOKENS = _normalize_tokens(TOKENS)

# 2) (опционально) поддержка добавления токена через ENV
EXTRA_TOKEN_SYMBOL  = os.getenv("EXTRA_TOKEN_SYMBOL")
EXTRA_TOKEN_ADDRESS = os.getenv("EXTRA_TOKEN_ADDRESS")
EXTRA_TOKEN_DECIMALS = os.getenv("EXTRA_TOKEN_DECIMALS")
if EXTRA_TOKEN_SYMBOL and EXTRA_TOKEN_ADDRESS:
    TOKENS[EXTRA_TOKEN_SYMBOL] = {
        "address": EXTRA_TOKEN_ADDRESS,
        "decimals": _to_int(EXTRA_TOKEN_DECIMALS, 18),
    }

# 3) обратная мапа: address(lower) -> symbol
def _addr_norm(x: str) -> str:
    return (x or "").lower()

ADDRESS_TO_SYMBOL = {
    _addr_norm(meta.get("address")): sym
    for sym, meta in TOKENS.items()
    if isinstance(meta, dict) and meta.get("address")
}

# --- fast maps ---
SYMBOL_TO_ADDRESS = {sym: meta["address"] for sym, meta in TOKENS.items()}
SYMBOL_TO_DECIMALS = {sym: int(meta["decimals"]) for sym, meta in TOKENS.items()}

# Параметры батча / логики
MAX_WALLETS_PER_BATCH = _env_int("MAX_WALLETS_PER_BATCH", 5)
RANDOM_SKIP_PROB      = _env_float("RANDOM_SKIP_PROB", 0.0)

SWAPS_MIN = _env_int("SWAPS_MIN", 2)
SWAPS_MAX = _env_int("SWAPS_MAX", 4)

TRANSFERS_MIN = _env_int("TRANSFERS_MIN", 1)
TRANSFERS_MAX = _env_int("TRANSFERS_MAX", 3)

LP_PROBABILITY      = _env_float("LP_PROBABILITY", 0.6)
DEPLOY_PROBABILITY  = _env_float("DEPLOY_PROBABILITY", 0.4)

# Сна/джиттер
SLEEP_BETWEEN: Tuple[int,int] = (
    _env_int("SLEEP_BETWEEN_MIN", 40),
    _env_int("SLEEP_BETWEEN_MAX", 120),
)

# --- Паузы между действиями (внутри одного кошелька) ---
ACTION_SLEEP_BASE: int = int(os.getenv("ACTION_SLEEP_BASE", "40"))
ACTION_SLEEP_JITTER: int = int(os.getenv("ACTION_SLEEP_JITTER", "80"))

# Газ
GAS_LIMIT_DEFAULT = _env_int("GAS_LIMIT_DEFAULT", 400_000)

# LLM (Nous + OpenRouter)
NOUS_API_KEY   = _env("NOUS_API_KEY")
NOUS_BASE_URL  = _env("NOUS_BASE_URL", "https://api.nousresearch.com/v1")
NOUS_MODEL     = _env("NOUS_MODEL", "Hermes-4-70B")

OPENROUTER_API_KEY  = _env("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = _env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL    = _env("OPENROUTER_MODEL", "nousresearch/hermes-3-llama-70b")

LLM_TIMEOUT = _env_int("LLM_TIMEOUT", 30)

# Вкл/выкл деплой (по умолчанию выключен, чтобы не городить солц/байткод)
ENABLE_DEPLOY = _env_bool("ENABLE_DEPLOY", False)

# sanity лог
print(f"[config] PRIVATE_KEYS loaded: {len(PRIVATE_KEYS)} шт.")
# ---- Logging flags ----
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()  # DEBUG/INFO/WARN/ERROR
LOG_COLOR = os.getenv("LOG_COLOR", "1") not in ("0","false","False")
LOG_JSON  = os.getenv("LOG_JSON", "0") in ("1","true","True")
DEBUG     = os.getenv("DEBUG", "0") in ("1","true","True")