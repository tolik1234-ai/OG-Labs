# src/orchestrator.py
import random, time
from typing import List, Dict
from eth_account import Account
from .config import (
    PRIVATE_KEYS, MAX_WALLETS_PER_BATCH, RANDOM_SKIP_PROB,
    ROUTER, POS_MANAGER
)
from .chain import get_w3
from .strategy import run_for_wallet

def _pick_wallets() -> List[str]:
    if not PRIVATE_KEYS:
        raise AssertionError("PRIVATE_KEYS is empty")
    pks = PRIVATE_KEYS[:]
    random.shuffle(pks)
    return pks[:MAX_WALLETS_PER_BATCH]

def run_batch_once():
    wallets = _pick_wallets()
    print("batch wallets:", ", ".join([Account.from_key(pk).address[:10] + "…" for pk in wallets]))
    for pk in wallets:
        if random.random() < RANDOM_SKIP_PROB:
            continue
        try:
            w3 = get_w3()
            cfg: Dict = {"ROUTER": ROUTER, "POS_MANAGER": POS_MANAGER}
            run_for_wallet(w3, pk, cfg)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print("wallet failed:", e)
            time.sleep(5)