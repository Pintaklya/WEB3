# {repo_name}: Cross-Chain Bridge Event Listener Simulation

This repository contains a Python script that simulates the operation of a validator or oracle node for a cross-chain bridge. It is designed to be an architecturally sound component of a larger decentralized system, demonstrating best practices in modular design, configuration management, and error handling.

## Concept

A cross-chain bridge allows users to transfer assets or data from one blockchain (the *source chain*) to another (the *destination chain*). A common implementation is the "lock-and-mint" model:

1.  A user **locks** tokens in a smart contract on the source chain.
2.  This action emits an event (e.g., `TokensLocked`) on the source chain.
3.  A network of off-chain validators (or oracles) listens for this event.
4.  Upon detecting the event, these validators verify its legitimacy.
5.  After successful validation, one or more validators trigger an action on the destination chain to **mint** an equivalent amount of wrapped tokens for the user.

This script simulates the role of a single validator node (Step 3, 4, and 5), demonstrating how it listens, validates, and prepares to act on bridge events.

## Code Architecture

The script is built with a clear separation of concerns, using several classes to manage different aspects of the process.

-   **`script.py`**: The main executable file that orchestrates the entire process.
-   **`BlockchainConnector`**: A reusable class responsible for managing the connection to a single blockchain via its JSON-RPC endpoint. It handles connection logic, state checking, and basic data fetching (like the latest block number). This isolates the `web3.py` logic.
-   **`BridgeEventListener`**: The core class of the simulation. It orchestrates the entire process:
    -   It uses a `BlockchainConnector` instance to connect to the source chain.
    -   It initializes the bridge's smart contract object using its address and ABI.
    -   It runs a continuous loop to poll the source chain for new blocks and scan them for the specific `TokensLocked` event.
    -   For each new event, it simulates a validation step by making a call to a mock external oracle API using the `requests` library. This mimics a real-world security check.
    -   If validation is successful, it logs a detailed message simulating the transaction that would be sent to the destination chain to mint new tokens.
    -   It includes state management to avoid processing the same event twice.

### External Libraries Used

-   **`web3`**: The primary library for interacting with Ethereum-compatible blockchains. It's used to connect to an RPC node, instantiate contract objects, and filter for events.
-   **`requests`**: Used to simulate communication with an external API (an oracle or a validation service). This demonstrates how an off-chain component can integrate with other microservices for enhanced security and data verification.
-   **`python-dotenv`**: To manage sensitive configuration data like RPC URLs and API keys securely by loading them from a `.env` file instead of hardcoding them.

## How it Works

The script follows a logical, step-by-step process:

1.  **Initialization**: The script starts by loading configuration from a global `CONFIG` dictionary and environment variables from a `.env` file.
2.  **Connection**: The `BridgeEventListener` creates a `BlockchainConnector` instance, which connects to the source chain's RPC endpoint.
3.  **Contract Setup**: The listener uses the provided contract address and ABI to create a `web3.py` Contract object, allowing it to interact with the bridge contract's events.
4.  **Event Loop**: The `listen()` method begins an infinite loop.
5.  **Polling for Blocks**: In each iteration, it fetches the latest block number from the source chain and determines a range of blocks to scan (e.g., the last 100 blocks since the last check).
6.  **Fetching Events**: It uses `contract.events.TokensLocked.get_logs()` to efficiently query the blockchain node for any relevant events within that block range.
7.  **Processing Events**: For each event found:
    a. It checks an internal set (`processed_txs`) to ensure the event's transaction hasn't been processed before.
    b. It calls the `_validate_with_oracle()` method, which sends a POST request to a mock API endpoint. This simulates an essential off-chain verification step.
    c. If validation is successful, it calls `_initiate_destination_chain_action()`, which prints a detailed log of the minting transaction that would be created and sent to the destination chain.
8.  **State Update**: After processing, the block number is updated, and the transaction hash is added to the `processed_txs` set.
9.  **Error Handling**: The loop includes `try...except` blocks to gracefully handle RPC connection issues or other unexpected errors, ensuring the listener is resilient and can continue running.

## Usage Example

### 1. Setup Environment

It is highly recommended to use a Python virtual environment.

```bash
# Create a virtual environment
python -m venv venv

# Activate it
# On Windows:
# .\venv\Scripts\activate
# On macOS/Linux:
# source venv/bin/activate
```

### 2. Install Dependencies

Install the required libraries from the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a file named `.env` in the root directory of the project. This file will hold your RPC URLs. You can get free RPC URLs from services like [Ankr](https://www.ankr.com/), [Infura](https://www.infura.io/), or [Alchemy](https://www.alchemy.com/).

Your `.env` file should look like this:

```
# .env file

# RPC endpoint for the source chain (e.g., Ethereum Mainnet)
SOURCE_CHAIN_RPC_URL="https://rpc.ankr.com/eth"

# RPC endpoint for the destination chain (e.g., Polygon Mainnet)
DEST_CHAIN_RPC_URL="https://rpc.ankr.com/polygon"

# Optional: API key for a hypothetical oracle service
ORACLE_API_KEY="your-secret-api-key"
```

### 4. Run the Script

Execute the script from your terminal:

```bash
python script.py
```

### Expected Output

The script will start logging its activities to the console. Since the configured contract address is a placeholder, it will not find any real events. However, the output will show the connection and polling process.

```
2023-10-27 14:30:00 - [INFO] - Successfully connected to Ethereum at https://rpc.ankr.com/eth
2023-10-27 14:30:01 - [INFO] - Successfully initialized contract object for address 0x1234567890123456789012345678901234567890
2023-10-27 14:30:01 - [INFO] - Starting event listener for 'TokensLocked' events...
2023-10-27 14:30:03 - [INFO] - Scanning blocks from 18445000 to 18445100...
2023-10-27 14:30:18 - [INFO] - Scanning blocks from 18445101 to 18445201...
2023-10-27 14:30:33 - [INFO] - No new blocks to scan. Current head: 18445201. Waiting...
...
```

If the script were pointed at a real, active bridge contract, you would see output like this when an event is detected:

```
2023-10-27 14:35:10 - [INFO] - New 'TokensLocked' event found! Tx: 0xabc...def
2023-10-27 14:35:10 - [INFO] - Validating transaction 0xabc...def with external oracle...
2023-10-27 14:35:11 - [ERROR] - Could not reach oracle API for validation: ... Assuming failure for security.
2023-10-27 14:35:11 - [WARNING] - Validation failed for tx 0xabc...def. No action will be taken.
```
