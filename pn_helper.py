# pn_helper.py
# https://docs.piratenation.game/important/contracts

import requests
import pandas as pd
from web3 import Web3
import personal_settings # you are required to make a personal settings and define certain variables to help scripts


URL_COINCAP_API = "https://api.coincap.io/v2/assets/ethereum"
URL_ARB_NOVA_RPC = "https://nova.arbitrum.io/rpc"
URL_ARB_NOVA_RPC_ALT = "https://arb1.arbitrum.io/rpc"
URL_PIRATE_NATION_GRAPH_API = "https://subgraph.satsuma-prod.com/208eb2825ebd/proofofplay/pn-nova/api"

_contract_EnergySystem = "0x26DcA20a55AB5D38B2F39E6798CDBee87A5c983D"
# The ABI for TransparentUpgradeableProxy - might need to expand it to include other functions over time
_ABI_EnergySystem = [
        {
            "inputs": [
                {
                    "internalType": "uint256",
                    "name": "entity",
                    "type": "uint256"
                }
            ],
            "name": "getEnergy",
            "outputs": [
                {
                    "internalType": "uint256",
                    "name": "",
                    "type": "uint256"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        }
    ]

_contract_GameItems_addr = "0x3B4cdb27641bc76214a0cB6cae3560a468D9aD4A"
_ABI_GameItems = [
    {
        "inputs": [
            {"internalType": "address", "name": "from", "type": "address"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256[]", "name": "ids", "type": "uint256[]"},
            {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"},
            {"internalType": "bytes", "name": "data", "type": "bytes"}
        ],
        "name": "safeBatchTransferFrom",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

_contract_PGLD = "0x3C2e532a334149D6a2E43523f2427e2fA187c5f0"
_ABI_PGLD = [
    {
        "inputs": [
            {"internalType": "address", "name": "sender", "type": "address"},
            {"internalType": "address", "name": "recipient", "type": "address"},
            {"internalType": "uint256[]", "name": "amount", "type": "uint256"},
        ],
        "name": "transferFrom",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


class Web3Singleton:
    _web3_Nova = None
    _web3_NovaAlt = None
    _EnergySystem = None  
    _GameItems = None  
    _PGLDToken = None

    @classmethod
    def get_web3_Nova(cls):
        if cls._web3_Nova is None:
            cls._web3_Nova = Web3(Web3.HTTPProvider(URL_ARB_NOVA_RPC))
        return cls._web3_Nova

    @classmethod
    def get_web3_NovaAlt(cls):
        if cls._web3_NovaAlt is None:
            cls._web3_NovaAlt = Web3(Web3.HTTPProvider(URL_ARB_NOVA_RPC_ALT))
        return cls._web3_NovaAlt

    @classmethod
    def get_EnergySystem(cls):
        if cls._EnergySystem is None:
            web3_Nova = cls.get_web3_Nova()
            cls._EnergySystem = web3_Nova.eth.contract(address=_contract_EnergySystem, abi=_ABI_EnergySystem)
        return cls._EnergySystem
    
    @classmethod
    def get_GameItems(cls):
        if cls._GameItems is None:
            web3_Nova = cls.get_web3_Nova()
            cls._GameItems = web3_Nova.eth.contract(address=_contract_GameItems_addr, abi=_ABI_GameItems)
        return cls._GameItems   

    @classmethod
    def get_PGLDToken(cls):
        if cls._PGLDToken is None:
            web3_Nova = cls.get_web3_Nova()
            cls._PGLDToken = web3_Nova.eth.contract(address=_contract_PGLD, abi=_ABI_PGLD)
        return cls._PGLDToken         

web3_Nova = Web3Singleton.get_web3_Nova()
web3_NovaAlt = Web3Singleton.get_web3_NovaAlt()
contract_EnergySystem = Web3Singleton.get_EnergySystem()
contract_GameItems = Web3Singleton.get_GameItems()
contract_PGLDToken = Web3Singleton.get_PGLDToken()

# returns a full formed file path - useful to know where to find files
def data_path(filename) :
    return f"{personal_settings.relative_pn_data_path}{filename}"

# gets the JSON data from a query to the pirate nation graph
def get_data(query):
    response = requests.post(URL_PIRATE_NATION_GRAPH_API, json={'query': query})
    return response.json()

# read addresses from a file path passed in stripping funny characters, etc
def read_addresses(file_path):
    with open(file_path, 'r') as f:
        return [line.strip().lower() for line in f]
    
# takes a iterable of addresses and returns it in the string format of [Address1, Address2, ... AddressX]
def format_addresses_for_query(addresses):
    # form addresses into a comma string with spaces
    comma_str_addresses = ', '.join(f'"{address}"' for address in addresses)

    # wrap that comma string of addresses into brackets
    return f"[{comma_str_addresses}]"   

# gets the Eth to USD conversion
def get_eth_to_usd_price():
    try:
        response = requests.get(URL_COINCAP_API)
        response.raise_for_status()  # Raise an exception if the response status code is not 200
        
        data = response.json()  # Parse the JSON content of the response
        eth_to_usd_price = data["data"]["priceUsd"]  # Extract the ETH to USD price

        return float(eth_to_usd_price)
    except requests.exceptions.RequestException as e:
        print("Error making API request:", e)
        return None
    
# gets real time conversion of a USD amount to Eth    
def usd_to_eth(usd_amount):
    try:
        # Make a GET request to the CoinCap API
        response = requests.get(URL_COINCAP_API)
        response.raise_for_status()  # Raise an exception if the request was not successful

        # Parse the JSON response
        data = response.json()

        # Extract the current ETH price in USD
        eth_price_usd = float(data['data']['priceUsd'])

        # Calculate the equivalent amount in ETH
        eth_amount = usd_amount / eth_price_usd

        return eth_amount

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None
    
# returns the Nova eth balance from an address
def get_nova_eth_balance(address):
    eth_balance_wei = web3_Nova.eth.get_balance(Web3.to_checksum_address(address.lower()))
    if eth_balance_wei == 0 :
        eth_balance_wei = web3_NovaAlt.eth.get_balance(Web3.to_checksum_address(address.lower()))
    eth_balance_eth = float(web3_Nova.from_wei(eth_balance_wei, 'ether'))
    return eth_balance_eth

def get_energy(address, long_form=False):
    # Replace this with your logic to get PGLD for the address
    pgld_amount = 0  # Replace with the actual PGLD amount
    function_name = 'getEnergy'
    function_args = [int(address,16)]
    result = contract_EnergySystem.functions[function_name](*function_args).call()    
    if long_form:
        return result
    else:
        return round((result /  10 ** 18), 0)  

# Global variable to store the address to key mapping
_address_key_mapping = None

def load_address_key_mapping(csv_file):
    global _address_key_mapping
    df = pd.read_csv(csv_file)
    df['address_lower'] = df['address'].str.lower()
    _address_key_mapping = df.set_index('address_lower')['key'].to_dict()

def find_key_for_address(target_address):
    global address_key_mapping
    if _address_key_mapping is None:
        raise ValueError("Address to key mapping is not loaded. Call load_address_key_mapping first.")

    target_address_lower = target_address.lower()
    if target_address_lower in _address_key_mapping:
        return _address_key_mapping[target_address_lower]
    return None