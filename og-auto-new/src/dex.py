# src/dex.py
from typing import Any, Tuple
from web3 import Web3
from web3.types import TxParams
from .config import ROUTER, V3_FACTORY, POS_MANAGER, GAS_LIMIT_DEFAULT, TOKENS, V3_FEE
from .util import (
    to_checksum, erc20_min_abi, swap_router_v3_abi, v3_factory_abi,
    position_manager_abi, build_tx_base
)
import time

def _sym_addr(sym: str) -> str | None:
    meta = TOKENS.get(sym)
    if isinstance(meta, dict):
        return meta.get("address")
    return None

def addr_of(token_like: Any, *, w3: Web3 | None = None) -> str:
    """
    Принимает: 'WETH' | '0xabc...' | {'address':'0xabc', ...}
    Возвращает: checksum-адрес
    """
    if isinstance(token_like, dict):
        token_like = token_like.get('address')
    if isinstance(token_like, str) and not token_like.startswith('0x'):
        a = _sym_addr(token_like)
        token_like = a or token_like
    if not isinstance(token_like, str) or not token_like.startswith('0x'):
        raise ValueError(f'Bad token value for address: {token_like!r}')
    return Web3.to_checksum_address(token_like) if w3 is None else to_checksum(w3, token_like)

def decimals_of(token_like: Any) -> int:
    if isinstance(token_like, dict):
        try:
            return int(token_like.get('decimals', 18))
        except Exception:
            return 18
    if isinstance(token_like, str) and not token_like.startswith('0x'):
        meta = TOKENS.get(token_like)
        if isinstance(meta, dict):
            try:
                return int(meta.get('decimals', 18))
            except Exception:
                return 18
        return 18
    if isinstance(token_like, str) and token_like.startswith('0x'):
        # поиск по адресу в TOKENS
        for sym, meta in TOKENS.items():
            if isinstance(meta, dict) and meta.get('address','').lower() == token_like.lower():
                try:
                    return int(meta.get('decimals', 18))
                except Exception:
                    return 18
    return 18

def erc20(w3: Web3, token_like: Any):
    address = addr_of(token_like, w3=w3)
    return w3.eth.contract(address=address, abi=erc20_min_abi())

def ensure_allowance(w3: Web3, acct, token_like: Any, spender_like: Any, amount: int) -> str | None:
    try:
        token_addr = addr_of(token_like, w3=w3)
        spender_addr = addr_of(spender_like, w3=w3)
        c = erc20(w3, token_addr)
        current = c.functions.allowance(acct.address, spender_addr).call()
        if current >= amount:
            return None
        tx: TxParams = build_tx_base(w3, acct.address, GAS_LIMIT_DEFAULT)
        tx['gas'] = max(GAS_LIMIT_DEFAULT // 5, 60000)
        tx_data = c.functions.approve(spender_addr, int(amount)).build_transaction(tx)
        signed = acct.sign_transaction(tx_data)
        txh = w3.eth.send_raw_transaction(signed.rawTransaction)
        w3.eth.wait_for_transaction_receipt(txh)
        print(f'approve {token_addr} -> {spender_addr} {amount} | {txh.hex()}')
        return txh.hex()
    except Exception as e:
        print('approve failed:', e)
        return None

def erc20_transfer(w3: Web3, acct, token_like: Any, to_like: Any, amount: int) -> str:
    try:
        token_addr = addr_of(token_like, w3=w3)
        to_addr = addr_of(to_like, w3=w3)
        c = erc20(w3, token_addr)
        tx: TxParams = build_tx_base(w3, acct.address, GAS_LIMIT_DEFAULT)
        tx['gas'] = max(GAS_LIMIT_DEFAULT // 5, 60000)
        tx_data = c.functions.transfer(to_addr, int(amount)).build_transaction(tx)
        signed = acct.sign_transaction(tx_data)
        txh = w3.eth.send_raw_transaction(signed.rawTransaction)
        w3.eth.wait_for_transaction_receipt(txh)
        print(f'transfer erc20 {amount} -> {to_addr} ({token_addr}) | {txh.hex()}')
        return txh.hex()
    except Exception as e:
        print('transfer erc20 failed:', e)
        raise

def native_transfer(w3: Web3, acct, to_like: Any, amount_wei: int) -> str:
    try:
        to_addr = addr_of(to_like, w3=w3)
        tx: TxParams = build_tx_base(w3, acct.address, GAS_LIMIT_DEFAULT // 10)
        tx['to'] = to_addr
        tx['value'] = int(amount_wei)
        signed = acct.sign_transaction(tx)
        txh = w3.eth.send_raw_transaction(signed.rawTransaction)
        w3.eth.wait_for_transaction_receipt(txh)
        print(f'transfer native {amount_wei} wei -> {to_addr} | {txh.hex()}')
        return txh.hex()
    except Exception as e:
        print('transfer native failed:', e)
        raise

def v3_exactInputSingle(
    w3: Web3, acct, token_in_like: Any, token_out_like: Any,
    amount_in: int, min_amount_out: int = 0, fee: int = None,
    recipient: str | None = None, deadline_sec: int = 600
) -> str:
    try:
        token_in = addr_of(token_in_like, w3=w3)
        token_out = addr_of(token_out_like, w3=w3)
        fee = int(fee or V3_FEE)
        params = {
            "tokenIn": token_in,
            "tokenOut": token_out,
            "fee": fee,
            "recipient": recipient or acct.address,
            "deadline": int(w3.eth.get_block("latest")["timestamp"]) + int(deadline_sec),
            "amountIn": int(amount_in),
            "amountOutMinimum": int(min_amount_out),
            "sqrtPriceLimitX96": 0,
        }
        router = w3.eth.contract(address=to_checksum(w3, ROUTER), abi=swap_router_v3_abi())
        tx: TxParams = build_tx_base(w3, acct.address, GAS_LIMIT_DEFAULT)
        tx_data = router.functions.exactInputSingle(params).build_transaction(tx)
        signed = acct.sign_transaction(tx_data)
        txh = w3.eth.send_raw_transaction(signed.rawTransaction)
        w3.eth.wait_for_transaction_receipt(txh)
        print(f'v3 exactInputSingle {token_in}->{token_out} in={amount_in} minOut={min_amount_out} fee={fee} | {txh.hex()}')
        return txh.hex()
    except Exception as e:
        print('swap v3 failed:', e)
        raise

# ---- Uniswap V3 factory / position manager helpers ----

def get_pool(w3: Web3, tokenA_like: Any, tokenB_like: Any, fee: int) -> str:
    try:
        tokenA = addr_of(tokenA_like, w3=w3)
        tokenB = addr_of(tokenB_like, w3=w3)
        factory = w3.eth.contract(address=to_checksum(w3, V3_FACTORY), abi=v3_factory_abi())
        pool = factory.functions.getPool(tokenA, tokenB, int(fee)).call()
        return Web3.to_checksum_address(pool) if int(pool, 16) != 0 else "0x0000000000000000000000000000000000000000"
    except Exception as e:
        print('get_pool failed:', e)
        return "0x0000000000000000000000000000000000000000"

def _sort_tokens(a: str, b: str) -> tuple[str, str, bool]:
    a_l, b_l = a.lower(), b.lower()
    if a_l < b_l:
        return a, b, False
    return b, a, True

def pm_create_pool_if_needed(w3: Web3, acct, tokenA_like: Any, tokenB_like: Any, fee: int, sqrt_price_x96: int | None = None):
    try:
        tokenA = addr_of(tokenA_like, w3=w3)
        tokenB = addr_of(tokenB_like, w3=w3)
        pool = get_pool(w3, tokenA, tokenB, fee)
        if pool != "0x0000000000000000000000000000000000000000":
            return None, pool
        token0, token1, _ = _sort_tokens(tokenA, tokenB)
        sqrt_price = sqrt_price_x96 or (1 << 96)
        pm = w3.eth.contract(address=to_checksum(w3, POS_MANAGER), abi=position_manager_abi())
        tx = build_tx_base(w3, acct.address, GAS_LIMIT_DEFAULT)
        tx_data = pm.functions.createAndInitializePoolIfNecessary(token0, token1, int(fee), int(sqrt_price)).build_transaction(tx)
        signed = acct.sign_transaction(tx_data)
        txh = w3.eth.send_raw_transaction(signed.rawTransaction)
        w3.eth.wait_for_transaction_receipt(txh)
        print(f'pool ensure {token0}/{token1} fee={fee} | {txh.hex()}')
        pool2 = get_pool(w3, token0, token1, fee)
        return txh.hex(), pool2
    except Exception as e:
        print('pm_create_pool_if_needed failed:', e)
        raise

def pm_mint(
    w3: Web3, acct, tokenA_like: Any, tokenB_like: Any,
    amountA: int, amountB: int, fee: int, tickLower: int, tickUpper: int,
    amount0Min: int = 0, amount1Min: int = 0, recipient: str | None = None
) -> Tuple[str, Any]:
    try:
        tokenA = addr_of(tokenA_like, w3=w3)
        tokenB = addr_of(tokenB_like, w3=w3)
        token0, token1, flipped = _sort_tokens(tokenA, tokenB)
        amt0 = int(amountB if flipped else amountA)
        amt1 = int(amountA if flipped else amountB)
        pm = w3.eth.contract(address=to_checksum(w3, POS_MANAGER), abi=position_manager_abi())
        params = {
            "token0": token0,
            "token1": token1,
            "fee": int(fee),
            "tickLower": int(tickLower),
            "tickUpper": int(tickUpper),
            "amount0Desired": int(amt0),
            "amount1Desired": int(amt1),
            "amount0Min": int(amount0Min),
            "amount1Min": int(amount1Min),
            "recipient": recipient or acct.address,
            "deadline": int(w3.eth.get_block("latest")["timestamp"]) + 600,
        }
        tx = build_tx_base(w3, acct.address, GAS_LIMIT_DEFAULT)
        tx_data = pm.functions.mint(params).build_transaction(tx)
        signed = acct.sign_transaction(tx_data)
        txh = w3.eth.send_raw_transaction(signed.rawTransaction)
        w3.eth.wait_for_transaction_receipt(txh)
        print(f'lp mint {token0}/{token1} fee={fee} | {txh.hex()}')
        return txh.hex(), rec
    except Exception as e:
        print('pm_mint failed:', e)
        raise