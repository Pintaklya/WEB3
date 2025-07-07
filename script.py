import os
import time
import json
import logging
from typing import Dict, Any, Optional, Set

import requests
from web3 import Web3
from web3.exceptions import BadFunctionCallOutput, ContractLogicError, StaleBlockchain
from web3.contract import Contract
from dotenv import load_dotenv

# --- Basic Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Load environment variables from a .env file for sensitive data like RPC URLs
load_dotenv()

# --- Bridge Configuration ---
# This configuration simulates a bridge between two hypothetical chains.
# In a real-world scenario, this would be loaded from a more robust configuration management system.
CONFIG = {
    "source_chain": {
        "name": "Ethereum",
        "rpc_url": os.getenv("SOURCE_CHAIN_RPC_URL", "https://rpc.ankr.com/eth"),
        "bridge_contract_address": "0x1234567890123456789012345678901234567890", # Placeholder address
        "event_name": "TokensLocked"
    },
    "destination_chain": {
        "name": "Polygon",
        "rpc_url": os.getenv("DEST_CHAIN_RPC_URL", "https://rpc.ankr.com/polygon"),
        "token_mint_contract_address": "0x0987654321098765432109876543210987654321" # Placeholder address
    },
    "bridge_contract_abi": json.dumps([
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "internalType": "address", "name": "token", "type": "address"},
                {"indexed": True, "internalType": "address", "name": "sender", "type": "address"},
                {"indexed": False, "internalType": "bytes", "name": "recipient", "type": "bytes"},
                {"indexed": False, "internalType": "uint256", "name": "amount", "type": "uint256"},
                {"indexed": True, "internalType": "uint256", "name": "destinationChainId", "type": "uint256"}
            ],
            "name": "TokensLocked",
            "type": "event"
        }
    ]),
    "oracle_api": {
        "url": "https://api.mock-oracle.io/validate-tx",
        "api_key": os.getenv("ORACLE_API_KEY", "your_default_api_key")
    }
}

class BlockchainConnector:
    """Manages the connection to a single blockchain via its RPC endpoint."""

    def __init__(self, rpc_url: str, chain_name: str):
        """
        Initializes the connector with the RPC URL.
        
        Args:
            rpc_url (str): The HTTP/WSS RPC endpoint URL for the blockchain node.
            chain_name (str): A human-readable name for the chain (for logging).
        """
        self.rpc_url = rpc_url
        self.chain_name = chain_name
        self.web3: Optional[Web3] = None
        self.connect()

    def connect(self) -> None:
        """Establishes a connection to the blockchain node."""
        try:
            self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if self.web3.is_connected():
                logging.info(f"Successfully connected to {self.chain_name} at {self.rpc_url}")
            else:
                logging.error(f"Failed to connect to {self.chain_name}. Check RPC URL and network.")
                self.web3 = None
        except Exception as e:
            logging.error(f"Error connecting to {self.chain_name}: {e}")
            self.web3 = None

    def is_connected(self) -> bool:
        """Checks if the Web3 provider is currently connected."""
        return self.web3 is not None and self.web3.is_connected()

    def get_latest_block_number(self) -> Optional[int]:
        """
        Fetches the latest block number from the connected blockchain.

        Returns:
            Optional[int]: The latest block number, or None if an error occurs.
        """
        if not self.is_connected():
            logging.warning(f"Not connected to {self.chain_name}. Attempting to reconnect...")
            self.connect()
            if not self.is_connected():
                return None
        try:
            return self.web3.eth.block_number
        except Exception as e:
            logging.error(f"Failed to get latest block number from {self.chain_name}: {e}")
            return None

class BridgeEventListener:
    """Listens for events on a source chain and simulates actions on a destination chain."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the listener with bridge configuration.

        Args:
            config (Dict[str, Any]): A dictionary containing configuration for chains, contracts, and APIs.
        """
        self.config = config
        self.source_connector = BlockchainConnector(
            rpc_url=config["source_chain"]["rpc_url"],
            chain_name=config["source_chain"]["name"]
        )
        self.bridge_contract: Optional[Contract] = self._setup_source_contract()
        self.processed_txs: Set[str] = set() # In-memory cache to prevent reprocessing events

    def _setup_source_contract(self) -> Optional[Contract]:
        """Initializes the Web3 contract object for the source chain bridge."""
        if not self.source_connector.is_connected():
            logging.error("Cannot setup contract: source chain connector is not available.")
            return None
        
        try:
            address = self.config["source_chain"]["bridge_contract_address"]
            abi = self.config["bridge_contract_abi"]
            # The address must be checksummed for web3.py
            checksum_address = self.source_connector.web3.to_checksum_address(address)
            contract = self.source_connector.web3.eth.contract(address=checksum_address, abi=abi)
            logging.info(f"Successfully initialized contract object for address {address}")
            return contract
        except Exception as e:
            logging.error(f"Failed to initialize bridge contract: {e}")
            return None

    def _validate_with_oracle(self, event_data: Dict[str, Any]) -> bool:
        """
        Simulates an external validation step using a mock oracle API.
        In a real bridge, this would be a crucial security step, potentially involving
        multiple independent validators confirming the event.

        Args:
            event_data (Dict[str, Any]): The parsed data from the blockchain event.

        Returns:
            bool: True if validation is successful, False otherwise.
        """
        api_config = self.config.get("oracle_api", {})
        url = api_config.get("url")
        if not url:
            logging.warning("Oracle API URL not configured. Skipping external validation.")
            return True # Default to true if oracle is not configured
        
        headers = {"x-api-key": api_config.get("api_key", "")}
        payload = {
            "transactionHash": event_data['transactionHash'].hex(),
            "sourceChain": self.config["source_chain"]["name"],
            "amount": event_data['args']['amount']
        }

        logging.info(f"Validating transaction {payload['transactionHash']} with external oracle...")
        try:
            # Using requests library to make a POST request
            # We expect a mock server here, so we handle potential connection errors.
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            # In this simulation, we'll accept any 2xx response as valid.
            if response.status_code == 200 and response.json().get("isValid", False):
                logging.info(f"Oracle validation successful for {payload['transactionHash']}.")
                return True
            else:
                logging.warning(f"Oracle validation failed for {payload['transactionHash']}. Status: {response.status_code}, Body: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            # This catches connection errors, timeouts, etc.
            logging.error(f"Could not reach oracle API for validation: {e}. Assuming failure for security.")
            return False

    def _initiate_destination_chain_action(self, event_data: Dict[str, Any]) -> None:
        """
        Simulates the final step of the bridge: minting tokens on the destination chain.
        In a real implementation, this would involve creating, signing, and sending a transaction.
        """
        args = event_data['args']
        tx_hash = event_data['transactionHash'].hex()
        recipient = args['recipient'].hex() if isinstance(args['recipient'], bytes) else args['recipient']
        amount = args['amount']
        dest_chain_name = self.config["destination_chain"]["name"]

        logging.info("-" * 50)
        logging.info(f"SIMULATION: Initiating minting process on {dest_chain_name}.")
        logging.info(f"  Source Tx Hash: {tx_hash}")
        logging.info(f"  Recipient on {dest_chain_name}: {recipient}")
        logging.info(f"  Amount to Mint: {amount / (10**18):.6f} tokens") # Assuming 18 decimals
        logging.info(f"  Action: Call 'mint' on contract {self.config['destination_chain']['token_mint_contract_address']}")
        logging.info("-" * 50)
        
        # Mark as processed to avoid duplicates
        self.processed_txs.add(tx_hash)

    def _process_event(self, event: Dict[str, Any]) -> None:
        """
        Processes a single event log, including validation and triggering the destination action.
        """
        tx_hash = event['transactionHash'].hex()
        if tx_hash in self.processed_txs:
            logging.debug(f"Skipping already processed transaction: {tx_hash}")
            return
        
        logging.info(f"New '{self.config['source_chain']['event_name']}' event found! Tx: {tx_hash}")

        # Step 1: External validation via Oracle
        if self._validate_with_oracle(event):
            # Step 2: If validation passes, simulate the minting action
            self._initiate_destination_chain_action(event)
        else:
            logging.warning(f"Validation failed for tx {tx_hash}. No action will be taken.")

    def listen(self, poll_interval: int = 15, block_range: int = 100) -> None:
        """
        The main loop that polls the source blockchain for new events.

        Args:
            poll_interval (int): Seconds to wait between each poll.
            block_range (int): The number of blocks to scan in each iteration.
        """
        if not self.bridge_contract:
            logging.critical("Bridge contract is not initialized. Cannot start listener.")
            return

        logging.info(f"Starting event listener for '{self.config['source_chain']['event_name']}' events...")
        
        # Start scanning from the latest block to avoid processing the entire history
        # A production system would persist the last scanned block.
        try:
            last_scanned_block = self.source_connector.get_latest_block_number() - 1
        except Exception:
             logging.critical("Could not fetch initial block number. Aborting.")
             return

        while True:
            try:
                latest_block = self.source_connector.get_latest_block_number()
                if latest_block is None:
                    logging.warning("Could not determine latest block. Retrying after delay...")
                    time.sleep(poll_interval * 2) # Longer delay on RPC failure
                    continue

                # Define the range of blocks to query
                from_block = last_scanned_block + 1
                to_block = min(latest_block, from_block + block_range)

                if from_block > latest_block:
                    logging.info(f"No new blocks to scan. Current head: {latest_block}. Waiting...")
                    time.sleep(poll_interval)
                    continue
                
                logging.info(f"Scanning blocks from {from_block} to {to_block}...")

                event_filter = self.bridge_contract.events[self.config['source_chain']['event_name']].get_logs(
                    fromBlock=from_block,
                    toBlock=to_block
                )
                
                if event_filter:
                    for event in event_filter:
                        self._process_event(event)
                
                last_scanned_block = to_block

            except (StaleBlockchain, BadFunctionCallOutput, ContractLogicError) as e:
                logging.warning(f"Web3 related error occurred: {e}. Will retry.")
            except Exception as e:
                logging.error(f"An unexpected error occurred in the listener loop: {e}", exc_info=True)
            
            time.sleep(poll_interval)

def main():
    """Main function to set up and run the listener."""
    listener = BridgeEventListener(CONFIG)
    
    # Check if essential configurations are present
    if not all([os.getenv("SOURCE_CHAIN_RPC_URL"), os.getenv("DEST_CHAIN_RPC_URL")]):
        logging.warning("RPC URLs are not set in the .env file. The script will use public default RPCs which may be rate-limited.")
    
    listener.listen()

if __name__ == "__main__":
    main()
