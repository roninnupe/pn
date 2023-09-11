# pn_helper.py

import requests
from web3 import Web3
import personal_settings # you are required to make a personal settings and define certain variables to help scripts


URL_COINCAP_API = "https://api.coincap.io/v2/assets/ethereum"
URL_ARB_NOVA_RPC = "https://nova.arbitrum.io/rpc"
URL_ARB_NOVA_RPC_ALT = "https://arb1.arbitrum.io/rpc"
URL_PIRATE_NATION_GRAPH_API = "https://subgraph.satsuma-prod.com/208eb2825ebd/proofofplay/pn-nova/api"

_contract_TransparentUpgradeableProxy_addr = "0x26DcA20a55AB5D38B2F39E6798CDBee87A5c983D"
# The ABI for TransparentUpgradeableProxy - might need to expand it to include other functions over time
_ABI_TransparentUpgradeableProxy = [
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

class Web3Singleton:
    _web3_Nova = None
    _web3_NovaAlt = None
    _TransparentUpgradeableProxy = None  # Add the TransparentUpgradeableProxy here

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
    def get_TransparentUpgradeableProxy(cls):
        if cls._TransparentUpgradeableProxy is None:
            web3_Nova = cls.get_web3_Nova()
            cls._TransparentUpgradeableProxy = web3_Nova.eth.contract(address=_contract_TransparentUpgradeableProxy_addr, abi=_ABI_TransparentUpgradeableProxy)
        return cls._TransparentUpgradeableProxy

web3_Nova = Web3Singleton.get_web3_Nova()
web3_NovaAlt = Web3Singleton.get_web3_NovaAlt()
contract_transparentUpgradeableProxy = Web3Singleton.get_TransparentUpgradeableProxy()


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
    
# returns the Nova eth balance from an address
def get_nova_eth_balance(address):
    eth_balance_wei = web3_Nova.eth.get_balance(Web3.to_checksum_address(address.lower()))
    if eth_balance_wei == 0 :
        eth_balance_wei = web3_NovaAlt.eth.get_balance(Web3.to_checksum_address(address.lower()))
    eth_balance_eth = float(web3_Nova.from_wei(eth_balance_wei, 'ether'))
    return eth_balance_eth
