# OgLabs Auto

Automated on-chain activity: Uniswap v3 swaps, token transfers, LP provisioning, and optional ERC-20 deployments via LLM (Nous / OpenRouter).

## Features

- **Randomized swaps** on Uniswap v3 (`exactInputSingle`)
- **ERC-20 and native transfers**
- **Liquidity provision**: auto-create/init pools and mint positions
- **LLM-powered contract deployment** (ERC-20 fixed / mintable / capped + burnable)
- **Readable logs** (colored or JSON), configurable verbosity

---

## Quick Start

1. **Clone and set up environment**
   ```bash
   git clone https://github.com/yourname/og-auto.git
   cd og-auto
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
