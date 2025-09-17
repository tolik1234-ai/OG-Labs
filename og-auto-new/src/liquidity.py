# src/liquidity.py
from web3 import Web3
from .dex import (
    get_pool, pm_create_pool_if_needed, pm_mint,
    ensure_allowance, erc20, addr_of
)
from .config import POS_MANAGER, ADDRESS_TO_SYMBOL
from .util import get_logger, short, symbol_by_address
log = get_logger()

def ensure_pool_and_add_liquidity(w3: Web3, acct, token0, token1, fee: int, amt0: int, amt1: int):
    pool = get_pool(w3, token0, token1, fee)
    if pool == "0x0000000000000000000000000000000000000000":
        log.info("lp ensure: creating pool (create+init)")
        txh, pool_addr = pm_create_pool_if_needed(w3, acct, token0, token1, fee)
        if txh:
            log.info(f"lp ensure: pool created tx={short(txh)} addr={short(pool_addr)}")

    # approvals
    ensure_allowance(w3, acct, token0, POS_MANAGER, amt0)
    ensure_allowance(w3, acct, token1, POS_MANAGER, amt1)

    # mint
    txh, _ = pm_mint(w3, acct, token0, token1, amt0, amt1, fee, tickLower=-70000, tickUpper=70000)

    # ВАЖНО: для логов приводим к адресам, иначе мог прилететь dict
    t0 = addr_of(token0, w3=w3)
    t1 = addr_of(token1, w3=w3)
    pair = f"{symbol_by_address(t0, ADDRESS_TO_SYMBOL)}/{symbol_by_address(t1, ADDRESS_TO_SYMBOL)}"
    log.info(f"lp mint {pair} fee={fee} tx={short(txh)}")