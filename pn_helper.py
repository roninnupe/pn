# pn_helper.py
# https://docs.piratenation.game/important/contracts

import os
import re
import sys
import time
import datetime
import questionary
import inspect
import json
import requests
import math
from decimal import Decimal, getcontext
import pandas as pd
from typing import Union
from web3 import Web3
from functools import lru_cache
import threading
from prompt_toolkit.styles import Style
from termcolor import colored
try:
    from personal_settings import relative_pn_data_path
except (ImportError, AttributeError):
    # If personal_settings.py doesn't exist or relative_pn_data_path isn't defined,
    # set a default path
    relative_pn_data_path = "data/"

getcontext().prec = 18 

# Create a lock for thread safety
lock = threading.Lock()

# Color Constants for CLI
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN = "\033[96m"
C_END = '\033[0m'  # Reset to the default color
C_YELLOWLIGHT = "\033[33m"

# Color Constants for CLI
COLOR = {
    'RED':"\033[91m",
    'GREEN':"\033[92m",
    'YELLOW': "\033[93m",
    'BLUE':"\033[94m",
    'MAGENTA': "\033[95m",
    'EXTRA': "\033[97m",
    'CYAN': "\033[96m",
    'YELLOWLIGHT': "\033[33m",
    'END': '\033[0m'
}

######################################################
# WEB 3 END POINTS & Other API references
######################################################

URL_COINCAP_API = "https://api.coincap.io/v2/assets/ethereum"
URL_RPC = "https://rpc.apex.proofofplay.com" #"https://nova.arbitrum.io/rpc" #"https://arbitrum-nova.public.blastapi.io" 
URL_RPC_ALT = "https://rpc.apex.proofofplay.com" #"https://arb1.arbitrum.io/rpc" 
URL_PIRATE_NATION_GRAPH_API = "https://subgraph.satsuma-prod.com/208eb2825ebd/proofofplay/pn-pop-apex/api" #"https://subgraph.satsuma-prod.com/208eb2825ebd/proofofplay/pn-nova/api" 
PN_CHAIN_ID = 70700 #42170 #70700

_contract_WETH_addr = "0x77684A04145a5924eFCE0D92A7c4a2A2E8C359de" #"0x722E8BdD2ce80A4422E880164f2079488e115365" 

# contract addresses and their respective URL to JSON formats of their ABIs
_contract_EnergySystem_addr = "0xe4C31d280d63E207621deD8C3Bc70De45DFa5030"
_abi_URL_EnergySystem = "abi/EnergySystem.json"

_contract_GameItems_addr = "0x32a93c3e9A3BE8f0fdd0835aBa7299CBa3624B13"
_abi_URL_GameItems = "abi/GameItems.json"

_contract_PGLD_addr = "0x7117eC11c68E64ca1C477178dFcf16075c5920f3"
_abi_URL_PGLD = "abi/PGLD.json"

_contract_BountySystem_addr = "0x516923F5786f56dec5D64893D258b0d71B151f15" 
_abi_URL_BountySystem = "abi/BountySystem.json"

_contract_QuestSystem_addr = "0x82992d6c86eeEcFc7bAb4cC9004419886b9e6Df9"
_abi_URL_QuestSystem = "abi/QuestSystem.json"

_contract_PirateNFT_addr = "0x1e52c21b9dfcd947d03e9546448f513f1ee8706c"

@lru_cache(maxsize=32)
def get_abi(file_path):
    with lock:
        try:
            # Open the file in read mode
            with open(file_path, 'r') as file:
                # Read the content of the file
                abi_data = file.read()

                # Parse the JSON content into a Python dictionary
                abi = json.loads(abi_data)

                return abi

        except Exception as e:
            print(f"Error: {str(e)}")
            return None

class Web3Singleton:
    _web3_Nova = None
    _web3_NovaAlt = None
    _EnergySystem = None  
    _GameItems = None  
    _PGLDToken = None
    _BountySystem = None
    _QuestSystem = None

    @classmethod
    def get_web3_Apex(cls):
        if cls._web3_Nova is None:
            cls._web3_Nova = Web3(Web3.HTTPProvider(URL_RPC))
        return cls._web3_Nova

    @classmethod
    def get_web3_ApexAlt(cls):
        if cls._web3_NovaAlt is None:
            cls._web3_NovaAlt = Web3(Web3.HTTPProvider(URL_RPC_ALT))
        return cls._web3_NovaAlt

    @classmethod
    def get_EnergySystem(cls):
        if cls._EnergySystem is None:
            web3_Nova = cls.get_web3_Apex()
            cls._EnergySystem = web3_Nova.eth.contract(address=_contract_EnergySystem_addr, abi=get_abi(_abi_URL_EnergySystem))
        return cls._EnergySystem
    
    @classmethod
    def get_GameItems(cls):
        if cls._GameItems is None:
            web3_Nova = cls.get_web3_Apex()
            cls._GameItems = web3_Nova.eth.contract(address=_contract_GameItems_addr, abi=get_abi(_abi_URL_GameItems))
        return cls._GameItems   

    @classmethod
    def get_PGLDToken(cls):
        if cls._PGLDToken is None:
            web3_Nova = cls.get_web3_Apex()
            cls._PGLDToken = web3_Nova.eth.contract(address=_contract_PGLD_addr, abi=get_abi(_abi_URL_PGLD))
        return cls._PGLDToken      

    @classmethod
    def get_BountySystem(cls):
        if cls._BountySystem is None:
            web3_Nova = cls.get_web3_Apex()
            cls._BountySystem = web3_Nova.eth.contract(address=_contract_BountySystem_addr, abi=get_abi(_abi_URL_BountySystem))
        return cls._BountySystem          

    @classmethod
    def get_QuestSystem(cls):
        if cls._QuestSystem is None:
            web3_Nova = cls.get_web3_Apex()
            cls._QuestSystem = web3_Nova.eth.contract(address=_contract_QuestSystem_addr, abi=get_abi(_abi_URL_QuestSystem))
        return cls._QuestSystem      

# NOTE: REFACTOR TO REMOVE THESE stored instance
# Why because every instance using PN Helper will instantiate all these
# Make those scripts hold local references to just the ones they need
#web3_Nova = Web3Singleton.get_web3_Nova()
#web3_NovaAlt = Web3Singleton.get_web3_NovaAlt()
#contract_EnergySystem = Web3Singleton.get_EnergySystem()
#contract_GameItems = Web3Singleton.get_GameItems()
#contract_PGLDToken = Web3Singleton.get_PGLDToken()
#contract_BountySystem = Web3Singleton.get_BountySystem()
#contract_QuestSystem = Web3Singleton.get_QuestSystem()

######################################################
# HELPER FUNCTIONS
######################################################
    
def caller_function():
    called_function()

def called_function():
    # Get the current call stack
    stack = inspect.stack()
    # The first item in the stack is the current frame, so the second item is the caller
    caller_frame = stack[1]
    # The third item in the frame record is the function name
    caller_name = caller_frame.function
    print(f"The function '{caller_name}' called me!")

# returns a full formed file path - useful to know where to find files
def data_path(filepath) :
    try:
        return f"{relative_pn_data_path}{filepath}"
    except Exception as e:
        print(f"Error in data_path: {str(e)}")
        return filepath


# returns the path of an optional inventory data path, and the base if it doesn't exist
def add_inventory_data_path(filename):
    directory_path = data_path("inventory/")
    if not os.path.exists(directory_path):
        directory_path = data_path("")
    return f"{directory_path}{filename}"


from requests.exceptions import HTTPError, ConnectionError, Timeout, RequestException
import logging

# Set up logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

def get_data(query, max_retries=3, backoff_factor=0.3):
    url = URL_PIRATE_NATION_GRAPH_API
    headers = {'Content-Type': 'application/json'}
    retry_count = 0

    while retry_count < max_retries:
        try:
            response = requests.post(url, json={'query': query}, headers=headers, timeout=10)

            # Raise an HTTPError if the status code is 4xx or 5xx
            response.raise_for_status()

            # Validate and parse the JSON response
            try:
                data = response.json()
                return data
            except ValueError as e:
                logging.error(f"JSON decode error: {e}")
                raise

        except (HTTPError, ConnectionError, Timeout) as e:
            logging.error(f"Request error: {e}")
            retry_count += 1
            if retry_count < max_retries:
                sleep_time = backoff_factor * (2 ** (retry_count - 1))
                logging.debug(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                logging.error("Maximum retries reached. Exiting.")
                raise
        except RequestException as e:
            logging.error(f"General request exception: {e}")
            raise

# Example usage
# query = "Your GraphQL query here"
# data = get_data(query)


# read addresses from a file path passed in stripping funny characters, etc
def read_addresses(file_path):
    try:
        with open(file_path, 'r') as f:
            # Stripping each line of leading/trailing whitespace and converting to lowercase
            return [line.strip().lower() for line in f if line.strip()]
    except FileNotFoundError:
        # Handle the case where the file does not exist
        print(f"Error: The file '{file_path}' was not found.")
        return []
    except Exception as e:
        # Handle other potential exceptions
        print(f"An error occurred while reading the file: {e}")
        return []


# Takes an iterable of addresses and returns it in the string format of [address1, address2, ... addressX]
def format_addresses_for_query(addresses):
    # Form addresses into a comma string with spaces, lowercasing each address
    comma_str_addresses = ', '.join(f'"{address.lower()}"' for address in addresses)

    # Wrap that comma string of addresses into brackets
    return f"[{comma_str_addresses}]" 


# Cache structure
eth_price_cache = {
    'price': None,
    'last_updated': 0  # Epoch time
}

# Cache duration in seconds (24 hours)
CACHE_DURATION = 24 * 60 * 60

# URL for CoinCap API
URL_COINCAP_API = 'https://api.coincap.io/v2/assets/ethereum'

def get_cached_eth_price():
    current_time = time.time()
    # Check if the cache is valid
    if current_time - eth_price_cache['last_updated'] > CACHE_DURATION or eth_price_cache['price'] is None:
        # Cache is outdated or empty, fetch new price
        try:
            response = requests.get(URL_COINCAP_API)
            response.raise_for_status()  # Raise an exception if the response status code is not 200
            
            data = response.json()  # Parse the JSON content of the response
            eth_price_cache['price'] = float(data["data"]["priceUsd"])  # Update the cache with the new price
            eth_price_cache['last_updated'] = current_time  # Update the last updated time
        except requests.exceptions.RequestException as e:
            print("Error making API request:", e)
            return 3500

    return eth_price_cache['price']

def get_eth_to_usd_price():
    # Assuming get_cached_eth_price() returns a float or None
    price = get_cached_eth_price()
    return Decimal(price) if price is not None else None

def usd_to_eth(usd_amount, round_result=False):
    eth_price = get_eth_to_usd_price()
    if eth_price is None:
        raise ValueError("ETH price is not available.")
    
    eth_amount = Decimal(usd_amount) / eth_price
    return round(eth_amount, 6) if round_result else eth_amount

def eth_to_usd(eth_amount, round_result=True):
    eth_price = get_eth_to_usd_price()
    if eth_price is None:
        raise ValueError("ETH price is not available.")
    
    usd_amount = Decimal(eth_amount) * eth_price
    return round(usd_amount, 2) if round_result else usd_amount

# Standard ERC-20 ABI snippet for balanceOf function
ERC20_ABI_SNIPPET = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]

def to_web3_address(address):
    return Web3.toChecksumAddress(address)

def get_token_balance(contract_address, contract_abi, user_address, web3_instance):
    contract = web3_instance.eth.contract(address=to_web3_address(contract_address), abi=contract_abi)
    balance_wei = contract.functions.balanceOf(to_web3_address(user_address)).call()
    balance_eth = web3_instance.from_wei(balance_wei, 'ether')
    return float(balance_eth)

def get_apex_eth_balance(address):
    try:
        eth_balance_wei = Web3Singleton.get_web3_Apex().eth.get_balance(to_web3_address(address))
        eth_balance_eth = float(Web3Singleton.get_web3_Apex().from_wei(eth_balance_wei, 'ether'))

        # Use the standard ERC-20 ABI snippet for the balanceOf function
        weth_balance_eth = get_token_balance(_contract_WETH_addr, ERC20_ABI_SNIPPET, address, Web3Singleton.get_web3_Apex())

        return eth_balance_eth, weth_balance_eth
    except Exception as e:
        error_type = type(e).__name__
        print(f"**get_apex_eth_balance -> Exception: {e} - {error_type}")
        return None, None


def get_energy(address, long_form=False):
    try:
        function_name = 'getEnergy'
        function_args = [int(address,16)]
        result = Web3Singleton.get_EnergySystem().functions[function_name](*function_args).call()    
        if long_form:
            return result
        else:
            return math.floor(result /  10 ** 18)
    except Exception as e:
        error_type = type(e).__name__
        print(f"{C_RED}**get_energy -> Exception: {e} - {error_type}{C_END}")
        return None


# Global variable to store the address to key mapping
_address_key_mapping = None
_address_file_name = None

def load_address_key_mapping(csv_file, reload=False):
    global _address_key_mapping
    global _address_file_name

    # do not bother loading up again if we are trying to load the same file, and not override
    if _address_file_name == csv_file and reload == False :
        return

    df = pd.read_csv(csv_file)
    df['address_lower'] = df['address'].str.lower()
    _address_key_mapping = df.set_index('address_lower')['key'].to_dict()

# Finds a key for a specific address from the key mapping
def find_key_for_address(target_address):
    global address_key_mapping
    if _address_key_mapping is None:
        raise ValueError("Address to key mapping is not loaded. Call load_address_key_mapping first.")

    target_address_lower = target_address.lower()
    if target_address_lower in _address_key_mapping:
        return _address_key_mapping[target_address_lower]
    return None


# Converts a graphID into just it's token ID and discards the address
def graph_id_to_tokenId(id_str: str) -> int:
    address, token_id = id_str.split('-')
    return int(token_id)

def graph_id_to_address_and_tokenId(id_str: str) -> Union[str, int]:
    address, token_id = id_str.split('-')
    return address, int(token_id)

# Converts a graphID into it's entity ID
def graph_id_to_entity(id_str: str) -> int:
    address, token_id = id_str.split('-')
    return token_to_entity(address, int(token_id))


# Convert and address and entity to it's packed uInt256 variant
def token_to_entity(address: str, token_id: int) -> int:
    # Convert Ethereum address from hex string to integer
    address_int = int(address, 16)

    # Left shift the token_id by 160 bits to make space for the address
    result = token_id << 160

    # Combine the shifted token_id and address_int
    packed_result = result | address_int

    return packed_result

# helper function to get a pirate tokenID and turn it into the entity 
def pirate_token_id_to_entity(token_id:int, address=_contract_PirateNFT_addr):
    return token_to_entity(address, token_id)


# Convert and entity to it's address and token representation
def entity_to_token(packed_result: int) -> Union[str, int]:
    # Mask to extract the least significant 160 bits (Ethereum address)
    mask = (1 << 160) - 1

    # Extract the address integer using the mask
    address_int = packed_result & mask

    # Convert the address integer to a hex string
    address_str = hex(address_int).rstrip("L").lstrip("0x")  # Remove trailing 'L' (if exists) and leading '0x'

    # Extract the token_id by right-shifting the packed_result by 160 bits
    token_id = packed_result >> 160

    #print(f"0x{address_str} - {token_id}")

    return ("0x" + address_str, token_id)  # Prefix the Ethereum address with '0x'

# A query to get all pirates that belong to a given address
def make_pirate_query(address):
    return f"""
    {{
      accounts(where: {{address: "{address.lower()}"}}){{
        nfts(where:{{or: [{{nftType: "pirate"}}, {{nftType: "starterpirate"}}]}}){{
            name
            nftType
            id
            tokenId
            traits {{ 
                value
                metadata {{
                    name
                }}
            }}            
        }}
      }}
    }}
    """

def fetch_game_item_data(address):
    query = f"""
    {{
      accounts(where: {{address: "{address.lower()}"}}){{
        address
        gameItems(where: {{amount_gt:0}}){{
            amount
            gameItem{{
                tokenId
                name
                worldEntity{{
                    id
                }}                
            }}
        }}
      }}
    }}
    """
    return get_data(query)


def fetch_game_items_data():
    item_query = """
    {
        gameItems(first: 1000) {
            worldEntity {
                name
                gameItem
                {
                    tokenId
                    traits
                    {
                        value
                        metadata
                        {
                            name
                        }
                    }
                }
            }
        }
    }
    """
    data = get_data(item_query)
    
    # Check if the data has the expected structure
    if isinstance(data, dict) and "data" in data and "gameItems" in data["data"]:
        game_items = data["data"]["gameItems"]
        
        # Check if game_items is a list of dictionaries
        if isinstance(game_items, list) and all(isinstance(item, dict) for item in game_items):
            return game_items
    return {}


def get_token_id_mapping_and_soulbound_list(gameItems):
    item_to_tokenId = {}

    # temporarily hard coded all soulboundIds because graph isn't showing soulbound trait anymore
    soulbound_tokenIds = [2,4,5,100,101,102,201,205,209,210,211,212,213,214,215,216,217,218,219,220,221,222,223,224,225,226,227,241,242,243,250,328,80,335]

    for element in gameItems:  # Iterate over each element in gameItems
        worldEntity = element.get("worldEntity", {})  # Extract the worldEntity object
        gameItem = worldEntity.get("gameItem", {})  # Extract the gameItem object from worldEntity

        item_name = worldEntity.get("name")
        if item_name:  # Check if item_name is not None and not an empty string
            item_name = item_name.lower()  # Safely call .lower()
        else:
            print(f"Missing or None 'name' in worldEntity: {worldEntity}")
            continue  # Skip the rest of the loop for this element
        
        token_id = int(gameItem.get("tokenId", 0))  # Get the tokenId from gameItem
        traits = gameItem.get("traits", [])  # Get the traits list from gameItem

        # Check for the soulbound trait and add to soulbound_tokenIds if true
        soulbound_trait = any(
            trait.get("metadata", {}).get("name") == "soulbound" and trait.get("value") == "true"
            for trait in traits
        )
        if soulbound_trait:
            soulbound_tokenIds.append(token_id)

        # Store item_name and token_id in item_to_tokenId
        item_to_tokenId[item_name] = token_id

    return item_to_tokenId, soulbound_tokenIds 


def get_amount_by_item_token_id(data, target_token_id):
    # Extract the 'gameItems' list from the JSON data
    game_items = data.get('data', {}).get('accounts', [])[0].get('gameItems', [])

    # Iterate through the game items to find the matching tokenId
    for item in game_items:
        if item.get('gameItem', {}).get('tokenId') == str(target_token_id):
            return int(item.get('amount', 0))

    # Return 0 if no match is found
    return 0


def get_amount_by_world_entity_id(data, world_entity_id):
    try:
        accounts = data['data']['accounts']
        for account in accounts:
            game_items = account['gameItems']
            for game_item in game_items:
                if game_item['gameItem']['worldEntity']['id'] == world_entity_id:
                    return int(game_item['amount'])
        # Return 0 if the worldEntity ID is not found
        return 0
    except KeyError:
        # Handle the case where the data structure is not as expected
        return 0
    

def fetch_quest_data():
    query = f"""
    {{
      quests(first: 1000) {{
        id
        inputs {{
          id
          tokenPointer {{
            id
            amount
            tokenType
            tokenId
            tokenContract {{
              address
            }}
          }}
          energyRequired
        }}
      }}
    }}
    """
    return get_data(query)



# makes sure to properly format address to checksum lowercase variant
def to_web3_address(address):
    return Web3.to_checksum_address(address.lower())


# Custom exception class for gas limit exceeded
class GasLimitExceededError(Exception):
    def __init__(self, message="Gas limit exceeded"):
        self.message = message
        super().__init__(self.message)


# Try importing TransactionError, fall back to generic Exception if not available
try:
    from web3.exceptions import TransactionError
except ImportError:
    TransactionError = Exception


def send_web3_transaction(web3, private_key, txn_dict, max_transaction_cost_usd=0.0333, is_legacy=True, retries=120, retry_delay=300):
    attempt = 0
    while True:  # Infinite loop to simulate a do-while loop
        try:
            if is_legacy:
                receipt = send_web3_transaction_legacy(web3, private_key, txn_dict, max_transaction_cost_usd)
            else:
                receipt = send_web3_transaction_modern(web3, private_key, txn_dict, max_transaction_cost_usd)
            return receipt  # If successful, return the receipt
        except Exception as e:
            error_message = str(e)
            if "max fee per gas less than block base fee" in error_message or \
               "Max possible fee" in error_message or \
               "exceeds threshold" in error_message or \
               "err: max fee per gas less than block base fee" in error_message:
                attempt += 1
                if attempt > retries: 
                    raise
                else:
                    print(f"Attempt {attempt + 1}: Error encountered ({error_message}). Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
            else:
                raise


def send_web3_transaction_legacy(web3, private_key, txn_dict, max_transaction_cost_usd):
    max_transaction_cost_usd = Decimal(max_transaction_cost_usd)

    # Convert the USD cost threshold to ETH
    max_transaction_fee_eth = usd_to_eth(max_transaction_cost_usd, round_result=False)
    #print(f"Max Transaction Fee in ETH: {max_transaction_fee_eth} ETH")

    # Estimate effective gas price and gas limit
    effective_gas_price = web3.eth.get_block('latest').get('baseFeePerGas', web3.to_wei(1, 'gwei'))
    txn_dict['gasPrice'] = effective_gas_price
    estimated_gas_limit = web3.eth.estimate_gas(txn_dict)
    txn_dict['gas'] = int(estimated_gas_limit * 1.2)  # Add a 2% buffer for gas limit

    # Estimate the transaction fee in ETH and then convert to USD
    estimated_transaction_fee_eth = txn_dict['gas'] * effective_gas_price
    estimated_transaction_fee_usd = eth_to_usd(web3.from_wei(estimated_transaction_fee_eth, 'ether'), round_result=False)
    
    print(f"Estimated Transaction Fee: {web3.from_wei(estimated_transaction_fee_eth, 'ether')} ETH (${estimated_transaction_fee_usd} USD)")

    # Failsafe check: Throw an error if estimated cost exceeds threshold
    if estimated_transaction_fee_usd > max_transaction_cost_usd:
        error_message = f"Estimated fee (${round(estimated_transaction_fee_usd, 4)} USD) exceeds threshold (${round(max_transaction_cost_usd, 4)} USD)"
        raise ValueError(error_message)

    # Sign and send the transaction
    signed_txn = web3.eth.account.sign_transaction(txn_dict, private_key=private_key)

    txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
    txn_receipt = web3.eth.wait_for_transaction_receipt(txn_hash)

    # Arbitrum and other L2s might use effectiveGasPrice for fee calculation
    effective_gas_price = txn_receipt.effectiveGasPrice
    gas_used = txn_receipt.gasUsed
    actual_transaction_fee_eth = effective_gas_price * gas_used

    actual_transaction_fee_usd = eth_to_usd(web3.from_wei(actual_transaction_fee_eth, 'ether'), round_result=False)
    print(f"Actual Transaction Fee: {web3.from_wei(actual_transaction_fee_eth, 'ether')} ETH (${actual_transaction_fee_usd} USD)")
    return txn_receipt


def send_web3_transaction_modern(web3, private_key, txn_dict, max_transaction_cost_usd):
    max_transaction_cost_usd = Decimal(max_transaction_cost_usd)

    # Fetch the current base fee from the latest block
    base_fee = web3.eth.get_block('latest')['baseFeePerGas']
    
    # Set an extremely low priority fee
    max_priority_fee_per_gas = web3.to_wei(0.00111, 'gwei')  # Minimal tip

    # Set maxFeePerGas just above the base fee to account for fluctuations
    max_fee_per_gas = base_fee + max_priority_fee_per_gas

    # Use the precise gas limit estimate provided by estimate_gas
    estimated_gas_limit = web3.eth.estimate_gas(txn_dict)
    txn_dict['gas'] = estimated_gas_limit  # No buffer

    # Calculate the max possible transaction fee and convert to USD
    max_possible_fee_eth = txn_dict['gas'] * max_fee_per_gas
    max_possible_fee_usd = eth_to_usd(web3.from_wei(max_possible_fee_eth, 'ether'), round_result=False)

    print(f"Max Transaction Fee: {web3.from_wei(max_possible_fee_eth, 'ether')} ETH (${max_possible_fee_usd} USD)")

    if max_possible_fee_usd > max_transaction_cost_usd:
        error_message = f"Max possible fee (${round(max_possible_fee_usd, 4)} USD) exceeds threshold (${round(max_transaction_cost_usd, 4)} USD). Transaction aborted."
        raise ValueError(error_message)

    # Set EIP-1559 transaction parameters
    txn_dict['maxPriorityFeePerGas'] = max_priority_fee_per_gas
    txn_dict['maxFeePerGas'] = max_fee_per_gas

    signed_txn = web3.eth.account.sign_transaction(txn_dict, private_key=private_key)
    txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
    txn_receipt = web3.eth.wait_for_transaction_receipt(txn_hash)

    # Calculate the actual transaction fee in ETH and then convert to USD
    effective_gas_price = txn_receipt.effectiveGasPrice if hasattr(txn_receipt, 'effectiveGasPrice') else max_fee_per_gas
    gas_used = txn_receipt.gasUsed
    actual_transaction_fee_eth = effective_gas_price * gas_used
    actual_transaction_fee_usd = eth_to_usd(web3.from_wei(actual_transaction_fee_eth, 'ether'), round_result=False)

    print(f"Actual Transaction Fee: {web3.from_wei(actual_transaction_fee_eth, 'ether')} ETH (${actual_transaction_fee_usd} USD)")

    return txn_receipt


WEB3_STATUS_PENDING = "Pending"
WEB3_STATUS_SUCCESS = "Successful"
WEB3_STATUS_FAILURE = "Failed"

# Convert a transaction reciept into it's display friendly message
def get_status_message(txn_reciept):
    if txn_reciept is None:
        return WEB3_STATUS_PENDING  # Transaction is still pending

    if txn_reciept["status"] == 1:
        return WEB3_STATUS_SUCCESS  # Transaction was successful
    else:
        return WEB3_STATUS_FAILURE  # Transaction failed    


def send_l2_eth(sender, recipient, amount_in_eth, private_key, gas_limit=30000, subtract_gas=False):
    web3 = Web3Singleton.get_web3_Apex()

    # Calculate gas costs based on gas price and gas limit
    gas_price = web3.eth.gas_price
    gas_cost = gas_price * gas_limit

    # Convert the amount_in_eth to wei
    amount_in_wei = web3.to_wei(amount_in_eth, 'ether')

    if subtract_gas:
        # Calculate the total amount to send, deducting gas costs
        print(f"Subtracting {gas_cost} from {amount_in_wei}")
        amount_in_wei -= gas_cost
        print(f"New amount: {amount_in_wei}")

    # Format the addresses to proper web3 format
    sender_addr = to_web3_address(sender)
    recipient_addr = to_web3_address(recipient)

    if(sender_addr == recipient_addr) :
        print(f"Skipping: Sender and Recipient Address is the same {sender_addr}")
        return None

    nonce = web3.eth.get_transaction_count(sender_addr, 'latest')

    print("nonce: ", nonce)

    # Build the transaction
    txn_dict = {
        'from': sender_addr,
        'to': recipient_addr,
        'value': amount_in_wei,
        'gasPrice': gas_price,
        'nonce': nonce,
        'gas': gas_limit,
        'chainId': PN_CHAIN_ID,
    }

    # Send the transaction
    try:
        return send_web3_transaction(web3, private_key, txn_dict)
    except Exception as e:
        print(f"Transaction failed: {e}")
        return None
    

# returns a list of pirate IDs associated with their account as a list of integer values
def get_pirate_ids(address):
    query = make_pirate_query(address)
    json_data = get_data(query)

    pirate_ids = [
        nft['id']
        for account in json_data['data']['accounts']
        for nft in account.get('nfts', [])  # Use .get() to handle the case where 'nfts' is missing
    ]

    return pirate_ids


def extract_captain_token_ids(data):
    captain_tuples = {}  # Initialize an empty dictionary to store captain tuples

    # Check if the necessary keys exist
    if 'data' in data and 'accounts' in data['data']:
        for account in data['data']['accounts']:
            # Use the account's address as the account_id, ensuring lowercase
            account_id = account.get('address', '').lower()

            if 'worldEntity' in account and 'components' in account['worldEntity']:
                for component in account['worldEntity']['components']:
                    if 'fields' in component:
                        for field in component['fields']:
                            if field['name'] == 'nft_entity':
                                # Convert the value to a captain_tuple; ensure your entity_to_token function can handle the conversion
                                captain_tuple = entity_to_token(int(field['value']))

                                if account_id:  # Check if account_id is not None
                                    captain_tuples[account_id] = f'{captain_tuple[0]}-{captain_tuple[1]}'
                                    break  # Assuming only one captain per account, break after finding the first

    return captain_tuples


def move_captain_id_to_front(pirate_ids, captain_token_id):
    # Check if captain_token_id is None
    if captain_token_id is None:
        return pirate_ids

    # Convert captain_token_id to string for comparison
    captain_token_id_str = str(captain_token_id)

    for pirate_id in pirate_ids:
        # Check if pirate_id ends with the captain_token_id
        if pirate_id.endswith(captain_token_id_str):
            # Remove the found pirate_id from the list
            pirate_ids.remove(pirate_id)
            # Insert the pirate_id at the beginning of the list
            pirate_ids.insert(0, pirate_id)
            break  # Break the loop as we found and moved the captain

    return pirate_ids


def move_captain_nft_to_front(pirate_nfts, captain_token_id):
    # Find the index of the NFT with the matching captain_token_id
    captain_index = next((index for index, nft in enumerate(pirate_nfts) if nft['id'] == captain_token_id), None)

    # If a matching NFT is found, move it to the front of the list
    if captain_index is not None:
        captain_nft = pirate_nfts.pop(captain_index)  # Remove the captain NFT from its current position
        pirate_nfts.insert(0, captain_nft)  # Insert the captain NFT at the beginning of the list

    return pirate_nfts


def get_pirate_nfts_dictionary(addresses):
    formatted_output = format_addresses_for_query(addresses)

    query = f"""

        fragment WorldEntityComponentValueCore on WorldEntityComponentValue {{
        id
        fields {{
            name
            value
        }}
        }}

        fragment WorldEntityCore on WorldEntity {{
        id
        components {{
            ...WorldEntityComponentValueCore
        }}
        name
        }}

        {{
            accounts(where: {{address_in: {formatted_output}}}){{
                address
                nfts(where:{{or: [{{nftType: "pirate"}}, {{nftType: "starterpirate"}}]}}){{
                    name
                    nftType
                    id
                    tokenId
                    traits {{
                        value
                        metadata {{
                            name
                        }}
                    }}             
                }}
                worldEntity{{
                    ...WorldEntityCore
                }}        
            }}
        }}
        """

    json_data = get_data(query)
    captain_token_ids = extract_captain_token_ids(json_data)

    pirate_nfts_dict = {}

    for account in json_data['data']['accounts']:
        address = account['address'].lower()
        pirate_nfts = []

        for nft in account.get('nfts', []):
            # Extracting level from traits
            level_trait = next((trait['value'] for trait in nft.get('traits', []) if trait['metadata']['name'].lower() == 'level'), None)
            level = int(level_trait) if level_trait is not None else None

            pirate_nft = {
                'name': nft['name'],
                'nftType': nft['nftType'],
                'id': nft['id'],
                'tokenId': nft['tokenId'],
                'level': level
            }

            pirate_nfts.append(pirate_nft)

        # If a captain is present, adjust the list order
        captain_token_id = captain_token_ids.get(address)
        if captain_token_id:
            pirate_nfts = move_captain_nft_to_front(pirate_nfts, captain_token_id)

        pirate_nfts_dict[address] = pirate_nfts

    return pirate_nfts_dict


def get_pirate_ids_dictionary(addresses):
    formatted_output = format_addresses_for_query(addresses)
    query = f"""

        fragment WorldEntityComponentValueCore on WorldEntityComponentValue {{
        id
        fields {{
            name
            value
        }}
        }}

        fragment WorldEntityCore on WorldEntity {{
        id
        components {{
            ...WorldEntityComponentValueCore
        }}
        name
        }}

        {{
            accounts(where: {{address_in: {formatted_output}}}){{
                address
                nfts(where:{{or: [{{nftType: "pirate"}}, {{nftType: "starterpirate"}}]}}){{
                    name
                    nftType
                    id
                    tokenId         
                }}
                worldEntity{{
                    ...WorldEntityCore
                }}        
            }}
        }}
        """

    json_data = get_data(query)

    captain_token_ids = extract_captain_token_ids(json_data)

    # Create a dictionary to store pirate IDs for each address
    pirate_ids_dict = {}

    for account in json_data['data']['accounts']:
        address = account['address'].lower()

        pirate_ids = [
            nft['id']
            for nft in account.get('nfts', [])
        ]

        captain_token_id = captain_token_ids[address]
        pirate_ids = move_captain_id_to_front(pirate_ids, captain_token_id)  

        # Store the pirate IDs in the dictionary with the address as the key
        pirate_ids_dict[address] = pirate_ids

    return pirate_ids_dict    


def get_currency_dictionary(addresses):
    formatted_output = format_addresses_for_query(addresses)
    query = f"""
    {{
        accounts(where: {{address_in: {formatted_output}}}){{
            address
            currencies{{
                amount
            }}
        }}
    }}
    """

    json_data = get_data(query)

    # Create a dictionary to store currency amounts for each address
    currency_dict = {}

    for account in json_data['data']['accounts']:
        address = account['address']
        # Assume only one currency amount will be returned per address
        currency_amount = account.get('currencies', [{}])[0].get('amount', 0)

        # Store the currency amount in the dictionary with the address as the key
        currency_dict[address] = currency_amount

    return currency_dict

    
# Selects a wallet from a CSV returns the name, address, and key associated with the wallet
# if there is only one address in the csv file, it returns the data instantly 
# if there is multiple addresses in the file it prompts the user to choose one
def select_wallet(csv_file):

    try:
        df = pd.read_csv(csv_file)

        if df.shape[0] == 1: 
            selected_row = df.iloc[0]
            wallet_data = {
                'name' : selected_row.get('wallet', ''),
                'address' : selected_row.get('address', ''),
                'key' : selected_row.get('key', '')   
            }

            return wallet_data    

        print("\nPlease select a wallet:\n")

        # Display the available wallets
        print("Available wallets:")
        print(df[['wallet', 'address']].to_string(index=False))

        # Ask the user to enter the wallet value
        selected_wallet = int(input("Enter wallet #: "))

        # Check if the input wallet value is in the DataFrame
        if selected_wallet in df['wallet'].tolist():
            # Find the corresponding row for the selected wallet
            selected_row = df[df['wallet'] == selected_wallet].iloc[0]

            # Retrieve the information from the selected row
            wallet_data = {
                'name' : selected_row.get('wallet', ''),
                'address' : selected_row.get('address', ''),
                'key' : selected_row.get('key', '')   
            }

            print(f"Selected Wallet: {wallet_data['name']}")
            print(f"Selected Address: {wallet_data['address']}")

            # Return the selected information
            return wallet_data
        else:
            return None  # Wallet not found in the DataFrame
    except FileNotFoundError:
        return None  # File not found    


# Function to list .csv files in a directory
def list_csv_files(path, prefix=""):
    return list_files(path, prefix, ".csv")

# function to list files in path with prefix and file_type optional
def list_files(path, prefix="", file_type=""):
    try:
        # Check if the path exists and is a directory
        if not os.path.exists(path):
            print(f"Error: The path '{path}' does not exist.")
            return []
        elif not os.path.isdir(path):
            print(f"Error: The path '{path}' is not a directory.")
            return []

        # List all files that match the prefix and file type
        return [f for f in os.listdir(path) if f.endswith(file_type) and f.startswith(prefix)]

    except Exception as e:
        # Handle other potential exceptions, such as permission issues
        print(f"An error occurred while listing files in '{path}': {e}")
        return []

# Function to display a menu and select a .csv file
def _select_directory_file(dir_files):
    choices = [{"name": file} for file in dir_files]
    questions = [
        questionary.select(
            "Select a file:",
            choices=choices,
        ).ask()
    ]

    if questions[0] is not None:
        return questions[0]
    else:
        return None

def select_csv_file(prefix=""):
    directory_path = data_path("")

    # List .csv files in the directory
    csv_files = list_files(directory_path, prefix, ".csv")

    if not csv_files:
        print("No .csv files found in the specified directory.")
        return None
    else:
        # Display and select a .csv file using the menu
        selected_csv_file = _select_directory_file(csv_files)
        print(f"You selected: {selected_csv_file}")
        return data_path(selected_csv_file)
    

def select_file(directory_path=data_path(""), prefix="", file_extension=""):
    files = list_files(directory_path, prefix, file_extension)

    if not files:
        if prefix == "":
            print(f"No {file_extension} files in '{directory_path}'")
        else:
            print(f"No {prefix}[name]{file_extension} files in '{directory_path}'")
        return None
    else:
        selected_file = _select_directory_file(files)
        print(f"You selected: {selected_file}")
        return f"{directory_path}{selected_file}"


# Prompts the user to select an address file
def select_xlsx_file():

    directory_path = add_inventory_data_path("")

    excel_files = [f for f in os.listdir(directory_path) if f.endswith(".xlsx")]

    if not excel_files:
        print("No .xlsx files found in the specified directory.")
        return None
    else:
        # Display and select a .xslx file using the menu
        selected_file = _select_directory_file(excel_files)
        print(f"You selected: {selected_file}")
        return f"{directory_path}/{selected_file}"


def formatted_time_str(format="%m-%d %H:%M:%S"):
    return datetime.datetime.now().strftime(format) 


def handle_delay(delay, time_period="minute", desc_msg=None):
    
    if delay is not None and delay > 0:

        if time_period == "hour":
            delay_seconds = delay * 3600
        elif time_period == "second":
            delay_seconds = delay
        else:  # Default to minutes if not specified
            delay_seconds = delay * 60

        # Convert delay_seconds into hours, minutes, and seconds
        hours = delay_seconds // 3600
        minutes = (delay_seconds % 3600) // 60
        seconds = delay_seconds % 60

        # Build the delay message
        delay_message = f"{formatted_time_str()} - "
        
        # Optionally prepend the desc_msg if provided
        if desc_msg:
            delay_message += f"{desc_msg}"
        else:
            delay_message += "Delaying for"

        # Add hours if it's greater than zero
        if hours > 0:
            delay_message += f" {hours} hours"

        # Add minutes if it's greater than zero
        if minutes > 0:
            delay_message += f" {minutes} minutes"

        # Add seconds if it's greater than zero
        if seconds > 0:
            delay_message += f" {seconds} seconds"

        # Print the delay message
        print(delay_message)

        visual_delay_for(delay_seconds)  # Assuming this is a function you have for showing delay visually

        print(f"\nDelay complete. {C_CYAN}Resuming execution at {formatted_time_str()}{C_END}")


def visual_delay_for(delay_seconds, prefix="Time remaining: "):
    for remaining in range(delay_seconds, 0, -1):
        hours_remaining = remaining // 3600
        minutes_remaining = (remaining % 3600) // 60
        seconds_remaining = remaining % 60
        if hours_remaining > 0:
            sys.stdout.write(f"\r{prefix}{C_CYAN}{hours_remaining} hours {minutes_remaining} minutes {seconds_remaining} seconds {C_END}")
        elif minutes_remaining > 0:
            sys.stdout.write(f"\r{prefix}{C_CYAN}{minutes_remaining} minutes {seconds_remaining} seconds {C_END}")
        else:
            sys.stdout.write(f"\r{prefix}{C_CYAN}{seconds_remaining} seconds {C_END}")                                
        sys.stdout.flush()
        time.sleep(1)



def get_full_wallet_data(walletlist, csv_filename="full_data_for_addresses.csv"):
    try:
        # Read the CSV file into a DataFrame
        file_path = data_path(csv_filename)
        df = pd.read_csv(file_path)

        # Filter the DataFrame based on the 'identifier' column
        filtered_df = df[df['identifier'].isin(walletlist)]

        # Define Ethereum address and private key patterns
        eth_address_pattern = re.compile(r'^0x[a-fA-F0-9]{40}$')
        eth_private_key_pattern = re.compile(r'^[a-fA-F0-9]{64}$') 

        # Check for valid Ethereum addresses and private keys
        valid_addresses = filtered_df['address'].apply(lambda x: bool(eth_address_pattern.match(x)))
        valid_keys = filtered_df['key'].apply(lambda x: bool(eth_private_key_pattern.match(x)))

        # Filter DataFrame to only include valid entries
        valid_filtered_df = filtered_df[valid_addresses & valid_keys]

        # Check if the DataFrame is empty after validation
        if valid_filtered_df.empty:
            print(f"No valid Ethereum addresses and private keys found in {file_path}")
            sys.exit()

        return valid_filtered_df

    except FileNotFoundError as e:
        print(f"File not found: {str(e)}")
        return pd.DataFrame()
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return pd.DataFrame()



def parse_number_ranges(range_str):
    result = []
    ranges = range_str.split(',')
    
    for r in ranges:
        parts = r.split('-')
        
        if len(parts) == 1:
            # Single number
            result.append(int(parts[0]))
        elif len(parts) == 2:
            # Range of numbers
            start, end = int(parts[0]), int(parts[1])
            result.extend(range(start, end + 1))
    
    return result

def insert_address_into_dictionary(dictionary, key, address):
    """
    Insert an address into a dictionary of lists associated with keys, ensuring uniqueness.

    Parameters:
        dictionary (dict): The dictionary to insert the address into.
        key (hashable): The key to associate with the address in the dictionary.
        address: The address to insert into the list associated with the key.

    Explanation:
        This function is used to maintain a dictionary where each key is associated with a list of addresses.
        It ensures that addresses are unique within each list.

        - If the key is not already in the dictionary, a new key is created with a list containing the address.
        - If the key is already in the dictionary, the function checks if the address is already in the list.
          - If the address is not in the list, it's appended to the list.
          - If the address is already in the list, it won't be added again to maintain uniqueness.
    """
    if key not in dictionary:
        # If the key is not in the dictionary, create a new key with a list containing the address.
        dictionary[key] = [address]
    elif address not in dictionary[key]:
        # If the key is in the dictionary and the address is not in the list, append the address to the list.
        dictionary[key].append(address)


class PirateCommandMappings:
    """
    A Singleton class for managing mappings between pirates and their associated commands.

    Explanation:
        Ensures a single instance for consistent access to pirate command mappings.
        Loads and stores mappings in a DataFrame for easy retrieval.

    Methods:
        __new__(cls): Singleton pattern for one instance.

        initialize(self): Load mappings from Excel if not initialized.

        reload_data(self): Load data from an Excel file into a DataFrame. Handles file not found gracefully.

        get_mappings_df(self): Retrieve pirate command mappings DataFrame.

    Attributes:
        df (pandas.DataFrame): DataFrame containing command mappings.

    Usage:
        Create an instance to access mappings via 'get_mappings_df'.
    """

    _instance = None

    def __new__(cls):
        """Singleton pattern for one instance."""
        if cls._instance is None:
            cls._instance = super(PirateCommandMappings, cls).__new__(cls)
            cls._instance.__initialized = False
        return cls._instance

    def initialize(self):
        """Load mappings from Excel if not initialized."""
        if not self.__initialized:
            self.__initialized = True
            self.reload_data()

    def reload_data(self):
        """Load data from an Excel file into a DataFrame. Handles file not found gracefully."""
        try:
            file_path = data_path("inventory/pirate_command.xlsx")
            self.df = pd.read_excel(file_path, engine='openpyxl')
        except FileNotFoundError:
            print(f"Warning: Pirate command mapping file '{file_path}' not found. Initialize it first.")
            self.df = pd.DataFrame()  # Create an empty DataFrame if the file doesn't exist.

    def get_mappings_df(self):
        """Retrieve pirate command mappings DataFrame."""
        self.initialize()
        return self.df

# Creating a single instance of the PirateCommandMappings class, named '_pirate_command_mappings'.
# Follows the Singleton pattern, ensuring one instance program-wide for central access to mappings.
# Provides easy access to mappings from different parts of the program.
_pirate_command_mappings = PirateCommandMappings()
