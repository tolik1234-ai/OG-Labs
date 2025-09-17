# src/chain.py
from web3 import Web3
from .config import OG_RPC

def get_w3() -> Web3:
    assert OG_RPC, "OG_RPC required (.env)"
    w3 = Web3(Web3.HTTPProvider(OG_RPC, request_kwargs={"timeout": 30}))
    assert w3.is_connected(), f"RPC not connected: {OG_RPC}"
    return w3