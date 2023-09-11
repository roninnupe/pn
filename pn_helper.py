# pn_helper.py
# https://docs.piratenation.game/important/contracts

import json
import requests
import pandas as pd
from web3 import Web3
import personal_settings # you are required to make a personal settings and define certain variables to help scripts


######################################################
# WEB 3 END POINTS & Other API references
######################################################

URL_COINCAP_API = "https://api.coincap.io/v2/assets/ethereum"
URL_ARB_NOVA_RPC = "https://nova.arbitrum.io/rpc"
URL_ARB_NOVA_RPC_ALT = "https://arb1.arbitrum.io/rpc"
URL_PIRATE_NATION_GRAPH_API = "https://subgraph.satsuma-prod.com/208eb2825ebd/proofofplay/pn-nova/api"

# contract addresses and their respective URL to JSON formats of their ABIs
_contract_EnergySystem_addr = "0x26DcA20a55AB5D38B2F39E6798CDBee87A5c983D"
_abi_URL_EnergySystem = "https://api-nova.arbiscan.io/api?module=contract&action=getabi&address=0x5635Dc8d6A8aDFc2ABe4eF8A6a1b06c9CB1d5185"

_contract_GameItems_addr = "0x3B4cdb27641bc76214a0cB6cae3560a468D9aD4A"
_abi_URL_GameItems = "https://api-nova.arbiscan.io/api?module=contract&action=getabi&address=0xad6Bd6a4F2279d6Ece6f2be15d5Ce80719b1E361"

_contract_PGLD_addr = "0x3C2e532a334149D6a2E43523f2427e2fA187c5f0"
_abi_URL_PGLD = "https://api-nova.arbiscan.io/api?module=contract&action=getabi&address=0x71BD13EF8f3D63F6924f48b6806D7000A355B353"

_contract_BountySystem_addr = "0xE6FDcF808cD795446b3520Be6487917E9B82339a"
_abi_URL_BountySystem = "https://api-nova.arbiscan.io/api?module=contract&action=getabi&address=0x13A2C5f0fF0Afd50278f78a48dcE94e656187cf2"

def get_abi_from_url(abi_url):
    try:
        # Make an HTTP GET request to fetch the ABI
        response = requests.get(abi_url)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Parse the JSON response into a Python dictionary
            abi_data = json.loads(response.text)

            # Extract the ABI from the dictionary
            abi = json.loads(abi_data['result'])

            return abi

        else:
            print("Failed to fetch ABI from the URL.")
            return None
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
            cls._EnergySystem = web3_Nova.eth.contract(address=_contract_EnergySystem_addr, abi=get_abi_from_url(_abi_URL_EnergySystem))
        return cls._EnergySystem
    
    @classmethod
    def get_GameItems(cls):
        if cls._GameItems is None:
            web3_Nova = cls.get_web3_Nova()
            cls._GameItems = web3_Nova.eth.contract(address=_contract_GameItems_addr, abi=get_abi_from_url(_abi_URL_GameItems))
        return cls._GameItems   

    @classmethod
    def get_PGLDToken(cls):
        if cls._PGLDToken is None:
            web3_Nova = cls.get_web3_Nova()
            cls._PGLDToken = web3_Nova.eth.contract(address=_contract_PGLD_addr, abi=get_abi_from_url(_abi_URL_PGLD))
        return cls._PGLDToken      

    @classmethod
    def get_BountySystem(cls):
        if cls._BountySystem is None:
            web3_Nova = cls.get_web3_Nova()
            cls._BountySystem = web3_Nova.eth.contract(address=_contract_BountySystem_addr, abi=get_abi_from_url(_abi_URL_BountySystem))
        return cls._BountySystem           

web3_Nova = Web3Singleton.get_web3_Nova()
web3_NovaAlt = Web3Singleton.get_web3_NovaAlt()
contract_EnergySystem = Web3Singleton.get_EnergySystem()
contract_GameItems = Web3Singleton.get_GameItems()
contract_PGLDToken = Web3Singleton.get_PGLDToken()
contract_BountySystem = Web3Singleton.get_BountySystem()

######################################################
# HELPER FUNCTIONS
######################################################

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