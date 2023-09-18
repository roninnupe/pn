import math
import time
import pandas as pd
import pn_helper as pn
from itertools import cycle
from web3 import Web3, HTTPProvider
from eth_utils import to_checksum_address
import csv

token_contract = Web3.to_checksum_address("0x5b0661b61b0e947e7e49ce7a67abaf8eaafcdc1a")

quest_menu = {
    #1: "Swab the Decks",
    2: "Load Cargo",
    #3: "Chop Wood",
    #4: "Harvest Cotton",
    #5: "Mine Iron",
    19: "Chop More Wood",
    20: "Harvest More Cotton",
    21: "Mine More Iron"
}

quest_data = pn.fetch_quest_data()
chosen_quests = []

def display_quest_menu():
    quest_counter = 0

    while True:
        print("Select a quest ID (leave blank to exit):")
        for quest_id, quest_name in quest_menu.items():
            print(f"{quest_id} - {quest_name}")
        user_input = input("Enter the quest ID: ")
        if user_input.isdigit() and int(user_input) in quest_menu:
            quest_id = int(user_input)
            quest_name = quest_menu.get(quest_id, "Quest Not Found")
            chosen_quest = next((quest for quest in quest_data["data"]["quests"] if quest["id"] == str(quest_id)), None)
            chosen_quest['name'] = quest_name
            energy_required = int(chosen_quest['inputs'][0]['energyRequired'])
            chosen_quest['energy'] = round((energy_required / 10 ** 18), 0)
            chosen_quest['count'] = 0
            chosen_quests.append(chosen_quest)
            quest_counter += 1
            print(f"{quest_name} chosen in slot {quest_counter}")
        elif user_input.strip() == "":
            return 
        else:
            print("Invalid input. Please enter a valid quest ID.")


display_quest_menu()
quest_cycle = cycle(chosen_quests)


PROXY_CONTRACT_ADDRESS = '0x8166F6be09f1da50B41dD22509a4B7573C67cEA6'
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
def start_quest(contract, address, key, quest_id):
    """Start the quest."""
    # 1. Get the graph ID for the provided address
    graph_id = get_pirate_id(address)

    # 2. Convert the graph ID to token ID
    token_id = pn.graph_id_to_tokenId(graph_id)

    # 3. Use the token ID in the quest_params_data
    quest_params_data = {
        'questId': int(quest_id),
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
        'gas': 950000,
        'gasPrice': web3.eth.gas_price,
        'nonce': web3.eth.get_transaction_count(address),
    })

    signed_txn = web3.eth.account.sign_transaction(txn, private_key=key)
    txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
    time.sleep(1)
    txn_reciept = web3.eth.get_transaction_receipt(txn_hash)
    
    print(f"Transaction hash for address {address}: {txn_hash.hex()}")

    if DEBUG_TEST_FLAG :
      print(txn_reciept)
      input()

    if txn_reciept is None:
        return "Pending"  # Transaction is still pending

    if txn_reciept["status"] == 1:
        return "Successful"  # Transaction was successful
    else:
        return "Failed"  # Transaction failed


def main_script():
    with open(pn.data_path("addresses.csv"), mode='r') as file:
        csv_reader = csv.DictReader(file)

        for row in csv_reader:
            wallet_id = row['wallet']
            address = row['address']
            key = row['key']

            chosen_quest = next(quest_cycle)

            # Check energy balance before starting the quest
            quest_energy_cost = chosen_quest['energy']
            energy_balance = pn.get_energy(address)
            number_of_quests = math.floor(energy_balance / quest_energy_cost)

            # sometimes wallets are throwing issue with 1 quest and not sure why, so I'm going to pass on a wallet if there's only enough energy to do 1 quest
            if number_of_quests < 2 : 
                print(f"{wallet_id}", end='...', flush=True)
                continue
            
            print(f"\nSo far we have done {chosen_quest['name']} {chosen_quest['count']} times")
            print(f"{wallet_id} - The energy balance is {energy_balance} and the quest costs {quest_energy_cost} energy to do, therefore we can do it {number_of_quests} times")

            for _ in range(number_of_quests):
                try:
                    print(f"{wallet_id} ({int(energy_balance)}/150) - ", end='', flush=True)
                    if start_quest(quest_contract, address, key, chosen_quest['id']) == "Successful": 
                        chosen_quest['count'] += 1
                        energy_balance -= quest_energy_cost
                    else:
                        print("**There was an issue with the transaction failing, so we aren't continuing on this wallet")
                        break
                except Exception as e:
                  print(print(f"Transaction failed: {e}"))
                  break




main_script()
