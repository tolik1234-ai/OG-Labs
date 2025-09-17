import random, time
from typing import Dict, List
from web3 import Web3
from eth_account import Account

from .config import (
    TOKENS, V3_FEE, LP_PROBABILITY, DEPLOY_PROBABILITY,
    TRANSFERS_MIN, TRANSFERS_MAX, SWAPS_MIN, SWAPS_MAX,
    SLEEP_BETWEEN, ENABLE_DEPLOY, ACTION_SLEEP_BASE, ACTION_SLEEP_JITTER,
    ROUTER, POS_MANAGER
)
from .util import make_account, jitter, sleep_with_jitter
from .dex import (
    v3_exactInputSingle, ensure_allowance, erc20_transfer, native_transfer, erc20
)
from .liquidity import ensure_pool_and_add_liquidity

# optional
try:
    from .contracts_llm import selection_from_llm
except Exception:
    selection_from_llm = None

def _symbols_universe() -> List[str]:
    # только строки-символы, никаких dict!
    return [sym for sym in TOKENS.keys()]

def _rand_two(tokens: List[str]) -> tuple[str, str]:
    if len(tokens) < 2:
        raise RuntimeError("Need at least 2 tokens in TOKENS")
    a, b = random.sample(tokens, 2)
    return a, b

def _random_amount_wei() -> int:
    return random.randint(10**8, 10**10)

def _random_amount_erc20() -> int:
    return random.randint(10**9, 10**12)

def run_for_wallet(w3: Web3, pk: str, cfg: Dict):
    acct = make_account(pk)
    owner = acct.address

    # 1) SWAPS
    swap_n = random.randint(SWAPS_MIN, SWAPS_MAX)
    syms = _symbols_universe()

    for _ in range(swap_n):
        t_in, t_out = _rand_two(syms)
        amt_in = _random_amount_erc20()
        ensure_allowance(w3, acct, t_in, cfg.get("ROUTER") or ROUTER, amt_in)
        v3_exactInputSingle(w3, acct, t_in, t_out, amt_in, min_amount_out=0, fee=V3_FEE)
        sleep_with_jitter(ACTION_SLEEP_BASE, ACTION_SLEEP_JITTER, "after action")
        time.sleep(random.randint(1,3))

    # 2) TRANSFERS
    transfers_n = random.randint(TRANSFERS_MIN, TRANSFERS_MAX)
    for _ in range(transfers_n):
        if random.random() < 0.5:
            native_transfer(w3, acct, owner, _random_amount_wei())
        else:
            sym = random.choice(syms)
            erc20_transfer(w3, acct, sym, owner, _random_amount_erc20())
        sleep_with_jitter(ACTION_SLEEP_BASE, ACTION_SLEEP_JITTER, "after action")
        time.sleep(random.randint(1,3))

    # 3) LP (по вероятности)
    if random.random() < LP_PROBABILITY:
        t0, t1 = _rand_two(syms)
        amt0 = _random_amount_erc20()
        amt1 = _random_amount_erc20()
        ensure_pool_and_add_liquidity(w3, acct, t0, t1, V3_FEE, amt0, amt1)
        sleep_with_jitter(ACTION_SLEEP_BASE, ACTION_SLEEP_JITTER, "after action")
        time.sleep(random.randint(3,10))

    # 4) DEPLOY (опционально)
    if ENABLE_DEPLOY and (random.random() < DEPLOY_PROBABILITY) and selection_from_llm:
        sel = selection_from_llm(owner)
        print("LLM selection:", sel)
        sleep_with_jitter(ACTION_SLEEP_BASE, ACTION_SLEEP_JITTER, "after action")

    # пауза между кошельками
    jitter(*SLEEP_BETWEEN)
