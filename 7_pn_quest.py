import time
import pandas as pd
import pn_helper as pn
from web3 import Web3, HTTPProvider
from eth_utils import to_checksum_address
import csv
from termcolor import colored
import questionary
from questionary import Choice
from pygments.token import Token
from prompt_toolkit.styles import Style
from termcolor import colored
from itertools import cycle
from concurrent.futures import ThreadPoolExecutor



token_contract = Web3.to_checksum_address("0x5b0661b61b0e947e7e49ce7a67abaf8eaafcdc1a")

custom_style = Style.from_dict({
    'questionmark': '#E91E63 bold',
    'selected': '#673AB7 bold',
    'pointer': '#673AB7 bold',
    'answer': '#2196F3 bold',
    'question': 'cyan bold',
})

quest_menu = {
    2: "📦 Load Cargo",
    19: "🪓 Chop More Wood",
    20: "🌾 Harvest More Cotton",
    21: "⛏️ Mine More Iron",
    99: "🚪 Exit"
}

quest_colors = {
    "📦 Load Cargo": "\033[93m",          # Light Blue
    "🪓 Chop More Wood": "\033[95m",     # Light Purple
    "🌾 Harvest More Cotton": "\033[96m", # Light Cyan
    "⛏️ Mine More Iron": "\033[97m"      # White
}

# Color Constants for CLI
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN = "\033[96m"
C_END = '\033[0m'  # Reset to the default color
C_YELLOWLIGHT = "\033[33m"

chosen_quests = []

def display_quest_menu():
    # ASCII Banner
    print(colored("  ##############################", 'cyan'))
    print(colored("  #                            #", 'cyan'))
    print(colored("  #", 'cyan') + "🏴‍☠️" + colored("PIRATE QUEST MENU ", 'red') + "🏴‍☠️" + colored("#", 'cyan'))
    print(colored("  #                            #", 'cyan'))
    print(colored("  ##############################", 'cyan'))

    print(colored("\n🏴‍☠️ Ahoy, matey!", 'yellow', attrs=['bold']))
    print(colored("Choose your quest and set sail on the high seas! 🌊⚓", 'yellow', attrs=['bold']))
    print("\n")

    # Fetch the quest data
    quest_data = pn.fetch_quest_data()
    chosen_quests_local = []
    while True:
        questions = [
            {
                'type': 'select',
                'name': 'quest',
                'message': 'Select a quest (Choose "Exit" when done):',
                'choices': [Choice(title=quest_name, value=quest_id) for quest_id, quest_name in quest_menu.items()]
            }
        ]

        answers = questionary.prompt(questions, style=custom_style)
        chosen_quest_id = int(answers['quest'])

        if chosen_quest_id == 99:
            break

        # Extract chosen quest details and append to the list
        quest_name = quest_menu.get(chosen_quest_id, "Quest Not Found")
        chosen_quest = next((quest for quest in quest_data["data"]["quests"] if quest["id"] == str(chosen_quest_id)),
                            None)
        chosen_quest['name'] = quest_name
        energy_required = int(chosen_quest['inputs'][0]['energyRequired'])
        chosen_quest['energy'] = round((energy_required / 10 ** 18), 0)
        chosen_quest['count'] = 0
        chosen_quests_local.append(chosen_quest)

    return chosen_quests_local




PROXY_CONTRACT_ADDRESS = '0x8166F6be09f1da50B41dD22509a4B7573C67cEA6'
DEBUG_TEST_FLAG = False

# Fetch the quest data using fetch_quest_data() from pn_helper
quest_data = pn.fetch_quest_data()
chosen_quests = display_quest_menu()
quest_cycle = cycle(chosen_quests)


# From the chosen quest, we extract all non-zero energy requirements.
# This step is important to ignore any quest data responses or parts that don't any require energy LOL
# This dictionary will hold the energy required for each quest
energy_required_per_quest = {}

for quest in chosen_quests:
    # Fetch the first non-zero value
    non_zero_energies = [int(input["energyRequired"]) for input in quest["inputs"] if int(input["energyRequired"]) > 0]

    # If there's at least one non-zero energy requirement, use the first one
    if non_zero_energies:
        ENERGY_REQUIRED_PER_QUEST_UNFORMATTED = non_zero_energies[0]
        energy_required = round((ENERGY_REQUIRED_PER_QUEST_UNFORMATTED / 10 ** 18), 0)
        energy_required_per_quest[quest['id']] = energy_required
    else:
        raise Exception(f"No non-zero energy requirement found for the quest {quest['name']}.")

if not energy_required_per_quest:
    raise Exception("No chosen quests found in fetched data.")


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
def start_quest(contract, address, key, quest):
    """Start the quest."""
    # 1. Get the graph ID for the provided address
    graph_id = get_pirate_id(address)

    # 2. Convert the graph ID to token ID
    token_id = pn.graph_id_to_tokenId(graph_id)

    # 3. Use the token ID in the quest_params_data
    quest_params_data = {
        'questId': int(quest['id']),
        'inputs': [
            {
                'tokenType': 2,
                'tokenContract': token_contract,
                'tokenId': token_id,
                'amount': 1
            }
        ]
    }

    quest_params_data['inputs'] = [
        (input_data['tokenType'], input_data['tokenContract'], input_data['tokenId'], input_data['amount']) for
        input_data in quest_params_data['inputs']]

    txn = contract.functions.startQuest((quest_params_data['questId'], quest_params_data['inputs'])).build_transaction({
        'chainId': 42170,
        'gas': 950000,
        'gasPrice': web3.eth.gas_price,
        'nonce': web3.eth.get_transaction_count(address),
    })

    signed_txn = web3.eth.account.sign_transaction(txn, private_key=key)
    txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
    time.sleep(1)
    txn_reciept = web3.eth.get_transaction_receipt(txn_hash)

    if txn_reciept is None:
        return txn_hash, "Pending"  # Transaction is still pending

    if txn_reciept["status"] == 1:
        return txn_hash, "Successful"  # Transaction was successful
    else:
        return txn_hash, "Failed"  # Transaction failed


def main_script():

    start_time = time.time()

    # Number of threads to use
    MAX_THREADS = 25

    with open(pn.data_path("addresses_with_pk.csv"), mode='r') as file:
        csv_reader = csv.DictReader(file)

        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            results = list(executor.map(handle_row, csv_reader))

    end_time = time.time()
    execution_time = end_time - start_time
    print(f"\n   Execution time: {execution_time:.2f} seconds")       
    

def handle_row(row):
    wallet_id = row['wallet']
    address = row['address']

    key = row['key']
    buffer = []

    buffer.append(f"{C_BLUE}---------------------- Wallet {wallet_id} ----------------------{C_END}")

    initial_energy_balance = pn.get_energy(address)
    buffer.append(f"Initial energy balance: {C_YELLOWLIGHT}{initial_energy_balance}{C_END}")

    for chosen_quest in chosen_quests:
        quest_energy_cost = chosen_quest['energy']
        if initial_energy_balance < quest_energy_cost:
            buffer.append(f"Energy insufficient for quest {chosen_quest['name']}. Moving to next quest or wallet.")
            continue

        buffer.append(f"    {quest_colors[chosen_quest['name']]}{chosen_quest['name']}{C_END}")
        txn_hash, status = start_quest(quest_contract, address, key, chosen_quest)
        if status == "Successful": 
            buffer.append(f"        Transaction {status}: {C_GREEN}:{txn_hash.hex()}{C_END}")
        else:
            buffer.append(f"        Transaction {status}: {C_RED}:{txn_hash.hex()}{C_END}")
            break # adding failsafe to break if a transaction fails

        initial_energy_balance -= quest_energy_cost
        buffer.append(f"        Remaining energy: {C_CYAN}{initial_energy_balance}{C_END}")

    buffer.append(f"\nTotal Remaining energy for wallet {wallet_id}: {C_CYAN}{initial_energy_balance}{C_END}")
    buffer.append(f"{C_BLUE}-------------------------------------------------------{C_END}")
    print("\n".join(buffer))


main_script()

