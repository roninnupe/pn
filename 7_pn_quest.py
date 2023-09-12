import argparse
import random
import time
import pandas as pd
import json
import requests
from web3 import Web3, HTTPProvider
from eth_utils import to_checksum_address
import csv

# Constants and configuration
INFURA_URL = 'https://nova.arbitrum.io/rpc'  # Placeholder
token_contract = Web3.to_checksum_address("0x5b0661b61b0e947e7e49ce7a67abaf8eaafcdc1a")
CONTRACT_ADDRESS = '0x093aE1c7F34E7219674031F16eBbEB6a0c4F8d97'
CONTRACT_ABI = [{
  "inputs": [
    {
      "components": [
        {
          "internalType": "uint32",
          "name": "questId",
          "type": "uint32"
        },
        {
          "components": [
            {
              "internalType": "enum GameRegistryLibrary.TokenType",
              "name": "tokenType",
              "type": "uint8"
            },
            {
              "internalType": "address",
              "name": "tokenContract",
              "type": "address"
            },
            {
              "internalType": "uint256",
              "name": "tokenId",
              "type": "uint256"
            },
            {
              "internalType": "uint256",
              "name": "amount",
              "type": "uint256"
            }
          ],
          "internalType": "struct GameRegistryLibrary.TokenPointer[]",
          "name": "inputs",
          "type": "tuple[]"
        }
      ],
      "internalType": "struct QuestSystem.QuestParams",
      "name": "params",
      "type": "tuple"
    }
  ],
  "name": "startQuest",
  "outputs": [
    {
      "internalType": "uint256",
      "name": "",
      "type": "uint256"
    }
  ],
  "stateMutability": "nonpayable",
  "type": "function"
}]

Energy_ABI = [{
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
}]


quest_menu = {
    1: "Swab the Decks",
    2: "Load Cargo",
    3: "Chop Wood",
    4: "Harvest Cotton",
    5: "Mine Iron",
    19: "Chop More Wood",
    20: "Harvest More Cotton",
    21: "Mine More Iron"
}

def display_quest_menu():
    while True:
        print("Select a quest ID:")
        for quest_id, quest_name in quest_menu.items():
            print(f"{quest_id} - {quest_name}")
        user_input = input("Enter the quest ID: ")
        if user_input.isdigit() and int(user_input) in quest_menu:
            return int(user_input)
        else:
            print("Invalid input. Please enter a valid quest ID.")

QUEST_ID = display_quest_menu()


PROXY_CONTRACT_ADDRESS = '0x8166F6be09f1da50B41dD22509a4B7573C67cEA6'
ENERGY_CONTRACT = ''
CSV_FILE_PATH = 'addresses.csv'  # Placeholder
ENERGY_REQUIRED_PER_QUEST = 5  # As per the provided quest details
graph_url = "https://subgraph.satsuma-prod.com/208eb2825ebd/proofofplay/pn-nova/api" # The Pirate Nation Graph for queries


# Setup web3 instance
web3 = Web3(Web3.HTTPProvider(INFURA_URL))

# Load contract
contract = web3.eth.contract(address=PROXY_CONTRACT_ADDRESS, abi=CONTRACT_ABI)
energy_contract = web3.eth.contract(address=ENERGY_CONTRACT, abi=Energy_ABI)


def get_energy_balance(contract, address):
    """Retrieve the energy balance for a given Ethereum address."""
    function_name = 'getEnergy'
    function_args = [int(address, 16)]
    result = contract.functions[function_name](*function_args).call()
    return round((result /  10 ** 18), 0)

# A query to get all pirates that belong to a given address
def make_pirate_query(address):
    return f"""
    {{
      accounts(where: {{address: "{address.lower()}"}}){{
        nfts(where:{{nftType: "pirate"}}){{
            name
            id
        }}
      }}
    }}
    """

# Get Data from the following enpoint using the query and return json
def get_json_data(url, query):
    response = requests.post(url, json={'query': query})
    return response.json()

def get_pirate_id(address):

    global id_value
    query = make_pirate_query(address)
    json_data = get_json_data(graph_url, query)

    for account in json_data['data']['accounts']:
        for nft in account['nfts']:
            id_value = nft['id']

    return id_value

def graph_id_to_tokenId(id_str: str) -> int:
    address, token_id = id_str.split('-')
    return int(token_id)

def get_current_energy(contract, address):
    """Retrieve the current energy of the given address from the energy contract."""
    entity_id = get_pirate_id(address)  # Use the function to get the entity ID
    return contract.functions.getEnergy(entity_id).call()

def start_quest(contract, address, private_key):
    """Start the quest."""
    # 1. Get the graph ID for the provided address
    graph_id = get_pirate_id(address)

    # 2. Convert the graph ID to token ID
    token_id = graph_id_to_tokenId(graph_id)

    # 3. Use the token ID in the quest_params_data
    quest_params_data = {
        'questId': QUEST_ID,
        'inputs': [
            {
                'tokenType': 2,
                'tokenContract': token_contract,
                'tokenId': token_id,
                'amount': 1
            }
        ]
    }
    # Estimating the gas
    #gas_estimate = contract.functions.startQuest((quest_params_data['questId'], quest_params_data['inputs'])).estimate_gas()

    txn = contract.functions.startQuest((quest_params_data['questId'], quest_params_data['inputs'])).build_transaction({
        'chainId': 42170,  # Replace with your chainId
        'gas': 850000,
        'gasPrice': web3.eth.gas_price,
        'nonce': web3.eth.get_transaction_count(address),
    })

    signed_txn = web3.eth.account.sign_transaction(txn, private_key=private_key)
    txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)

    print(f"Transaction hash for address {address}: {txn_hash.hex()}")

def main_script():
    with open(CSV_FILE_PATH, mode='r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            address = row['address']
            private_key = row['key']

            # Check energy balance before starting the quest
            #energy_balance = get_energy_balance(energy_contract, address)
            #energy_balance = get_current_energy(energy_contract, address)
            number_of_quests = 1#energy_balance // ENERGY_REQUIRED_PER_QUEST

            for _ in range(number_of_quests):
                start_quest(contract, address, private_key)

main_script()
