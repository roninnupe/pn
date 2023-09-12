import math
import time
import pandas as pd
import pn_helper as pn
from web3 import Web3, HTTPProvider
from eth_utils import to_checksum_address
import csv

token_contract = Web3.to_checksum_address("0x5b0661b61b0e947e7e49ce7a67abaf8eaafcdc1a")

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
ENERGY_REQUIRED_PER_QUEST = 10  # As per the provided quest details
DEBUG_TEST_FLAG = False


# Setup web3 references
web3 = pn.Web3Singleton.get_web3_Nova()
quest_contract = pn.Web3Singleton.get_QuestSystem()
energy_contract = pn.Web3Singleton.get_EnergySystem()


def get_pirate_id(address):

    global id_value

    query = pn.make_pirate_query(address)
    json_data = pn.get_data(query)

    for account in json_data['data']['accounts']:
        for nft in account['nfts']:
            id_value = nft['id']

    return id_value


# Starts the quest for 
def start_quest(contract, address, key):
    """Start the quest."""
    # 1. Get the graph ID for the provided address
    graph_id = get_pirate_id(address)

    # 2. Convert the graph ID to token ID
    token_id = pn.graph_id_to_tokenId(graph_id)

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

    if DEBUG_TEST_FLAG :
      print("address: ", address)
      print("graph_id: ", graph_id)
      print("token_id: ", token_id)
      print(quest_params_data)
      input()

    txn = contract.functions.startQuest((quest_params_data['questId'], quest_params_data['inputs'])).build_transaction({
        'chainId': 42170,  # Replace with your chainId
        'gas': 850000,
        'gasPrice': web3.eth.gas_price,
        'nonce': web3.eth.get_transaction_count(address),
    })

    signed_txn = web3.eth.account.sign_transaction(txn, private_key=key)
    txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)

    print(f"Transaction hash for address {address}: {txn_hash.hex()}")


def main_script():
    with open(pn.data_path("Addresses.csv"), mode='r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            wallet_id = row['wallet']
            address = row['address']
            key = row['key']

            # Check energy balance before starting the quest
            quest_energy_cost = ENERGY_REQUIRED_PER_QUEST
            energy_balance = pn.get_energy(address)
            number_of_quests = math.floor(energy_balance / quest_energy_cost)

            print(f"The energy balance is {energy_balance}\n\tand the quest costs {quest_energy_cost} energy to do\n\ttherefore we can do it {number_of_quests} times")

            for _ in range(number_of_quests):
                try:
                  print(f"{wallet_id} ({energy_balance}/150) - ", end='', flush=True)
                  start_quest(quest_contract, address, key)
                  # Delay to allow the network to update the nonce
                  time.sleep(1)
                except Exception as e:
                    print(print(f"Transaction failed: {e}"))
                    break




main_script()
