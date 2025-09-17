# src/util.py
import random, time
from typing import Dict
from eth_account import Account
from web3 import Web3

# --- pretty logging utils ---
import logging, sys, math
from typing import Optional
from .config import LOG_LEVEL, LOG_COLOR, LOG_JSON, DEBUG

RESET = "\x1b[0m"
COLORS = {
    "DEBUG": "\x1b[38;5;245m",
    "INFO":  "\x1b[38;5;39m",
    "WARN":  "\x1b[38;5;214m",
    "ERROR": "\x1b[38;5;203m",
}

class _HumanFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname
        msg = record.getMessage()
        if LOG_COLOR:
            color = COLORS.get(level, "")
            return f"{color}{level.lower():>5}{RESET} {msg}"
        return f"{level.lower():>5} {msg}"

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        import json, time
        payload = {
            "ts": round(time.time(), 3),
            "level": record.levelname.lower(),
            "msg": record.getMessage(),
            "logger": record.name,
        }
        if DEBUG and record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

_log = None

def get_logger(name="og"):
    global _log
    return _log if _log else init_logging(name)

def init_logging(name="og"):
    global _log
    log = logging.getLogger(name)
    log.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    h = logging.StreamHandler(sys.stdout)
    h.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    h.setFormatter(_JsonFormatter() if LOG_JSON else _HumanFormatter())
    # avoid duplicate handlers
    log.handlers[:] = [h]
    log.propagate = False
    _log = log
    return log

# --- pretty helpers ---
def short(x: object, keep: int = 6) -> str:
    if x is None:
        return "-"
    s = str(x)
    if s.startswith("0x") and len(s) > 2*keep+2:
        return f"{s[:2+keep]}…{s[-keep:]}"
    if len(s) > keep*2:
        return f"{s[:keep]}…{s[-keep:]}"
    return s

def fmt_amount(raw_amount: int, decimals: int) -> str:
    if decimals <= 0:
        return str(raw_amount)
    q = 10 ** decimals
    whole = raw_amount // q
    frac = raw_amount % q
    if frac == 0:
        return f"{whole}"
    # trim trailing zeros, limit length
    s = f"{frac:0{decimals}d}".rstrip("0")
    s = s[:8]  # keep short
    return f"{whole}.{s}"


def symbol_by_address(addr_like: object, address_to_symbol: dict) -> str:
    """
    Принимает адрес (str '0x...') ИЛИ словарь {'address': '0x...'} ИЛИ что-то ещё.
    Возвращает удобочитаемый символ, а если его нет — короткий адрес/строку.
    """
    try:
        if isinstance(addr_like, dict):
            addr = (addr_like.get("address") or "").lower()
        elif isinstance(addr_like, str):
            addr = addr_like.lower()
        else:
            # любой другой тип — в строку и укоротим
            return short(addr_like)
        if addr.startswith("0x"):
            sym = address_to_symbol.get(addr)
            return sym or short(addr)
        return short(addr)
    except Exception:
        return short(addr_like)

def on_error(log, msg: str, exc: Exception = None):
    if DEBUG and exc:
        log.exception(msg)
    else:
        log.error(f"{msg}: {exc}" if exc else msg)

def to_checksum(w3: Web3, addr: str) -> str:
    return Web3.to_checksum_address(addr)

def jitter(min_s: int, max_s: int) -> None:
    t = random.randint(min_s, max_s)
    time.sleep(t)

def make_account(pk: str):
    return Account.from_key(pk)

def build_tx_base(w3: Web3, from_addr: str, gas_limit: int):
    return {
        "from": from_addr,
        "nonce": w3.eth.get_transaction_count(from_addr),
        "gasPrice": w3.eth.gas_price,
        "gas": gas_limit,
    }

def erc20_min_abi():
    # balanceOf, decimals, symbol, approve, allowance, transfer
    return [
        {"constant":True,"inputs":[{"name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
        {"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
        {"constant":True,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},
        {"constant":False,"inputs":[{"name":"spender","type":"address"},{"name":"value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},
        {"constant":True,"inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"},
        {"constant":False,"inputs":[{"name":"to","type":"address"},{"name":"value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"},
    ]

def swap_router_v3_abi():
    # exactInputSingle
    return [
      {
        "name":"exactInputSingle","type":"function","stateMutability":"payable",
        "inputs":[{"name":"params","type":"tuple","components":[
          {"name":"tokenIn","type":"address"},
          {"name":"tokenOut","type":"address"},
          {"name":"fee","type":"uint24"},
          {"name":"recipient","type":"address"},
          {"name":"deadline","type":"uint256"},
          {"name":"amountIn","type":"uint256"},
          {"name":"amountOutMinimum","type":"uint256"},
          {"name":"sqrtPriceLimitX96","type":"uint160"}
        ]}],
        "outputs":[{"name":"amountOut","type":"uint256"}]
      }
    ]

def v3_factory_abi():
    # getPool(tokenA, tokenB, fee)
    return [
      {"name":"getPool","type":"function","stateMutability":"view",
       "inputs":[{"name":"tokenA","type":"address"},{"name":"tokenB","type":"address"},{"name":"fee","type":"uint24"}],
       "outputs":[{"name":"pool","type":"address"}]}
    ]

def position_manager_abi():
    # createAndInitializePoolIfNecessary + mint
    return [
      {"name":"createAndInitializePoolIfNecessary","type":"function","stateMutability":"payable",
       "inputs":[{"name":"token0","type":"address"},{"name":"token1","type":"address"},{"name":"fee","type":"uint24"},{"name":"sqrtPriceX96","type":"uint160"}],
       "outputs":[{"name":"pool","type":"address"}]},
      {"name":"mint","type":"function","stateMutability":"payable",
       "inputs":[{"name":"params","type":"tuple","components":[
          {"name":"token0","type":"address"},
          {"name":"token1","type":"address"},
          {"name":"fee","type":"uint24"},
          {"name":"tickLower","type":"int24"},
          {"name":"tickUpper","type":"int24"},
          {"name":"amount0Desired","type":"uint256"},
          {"name":"amount1Desired","type":"uint256"},
          {"name":"amount0Min","type":"uint256"},
          {"name":"amount1Min","type":"uint256"},
          {"name":"recipient","type":"address"},
          {"name":"deadline","type":"uint256"}
       ]}],
       "outputs":[
         {"name":"tokenId","type":"uint256"},
         {"name":"liquidity","type":"uint128"},
         {"name":"amount0","type":"uint256"},
         {"name":"amount1","type":"uint256"},
       ]}
    ]

def sleep_with_jitter(base: int, jitter: int, reason: str = ""):
    """Поспать base + rand(0..jitter) секунд, с логом причины."""
    t = base + random.randint(0, max(jitter, 0))
    if reason:
        print(f"sleep {t}s  ({reason})")
    else:
        print(f"sleep {t}s")
    time.sleep(t)
