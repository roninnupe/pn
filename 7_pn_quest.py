import argparse
import time
import traceback
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
    54: "🔍 Finding the Lost",
    99: "🚪 Exit"
}

quest_colors = {
    "📦 Load Cargo": "\033[93m",          # Light Blue
    "🪓 Chop More Wood": "\033[95m",     # Light Purple
    "🌾 Harvest More Cotton": "\033[96m", # Light Cyan
    "⛏️ Mine More Iron": "\033[97m",     # White
    "🔍 Finding the Lost": "\033[96m"          # Light Cyan (or choose another color)
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
    token_contract, token_id = pn.graph_id_to_address_and_tokenId(graph_id)

    # 3. Fetch comprehensive quest data
    quests_data = pn.fetch_quest_data()

    # 4. Extract input details for the specified quest ID
    quest_inputs = None
    for q in quests_data['data']['quests']:
        if q['id'] == quest['id']:
            quest_inputs = q['inputs']
            break

    if not quest_inputs:
        print(f"Error: No quest inputs found for quest ID: {quest['id']}")
        return None, "Failed due to missing quest inputs"

    # Token type mapping
    token_type_mapping = {'ERC721': 2,'ERC20': 1}

    # 5. Construct the input tuples for the quest
    quest_inputs_list = []

    # 6. Append required game items for the quest
    for input_data in quest_inputs:
        token_type_str = input_data['tokenPointer']['tokenType']
        token_type_int = token_type_mapping.get(token_type_str, 0)  # Default to 0 if not found

        # Check if this is the pirate data and replace the placeholder token ID
        if token_type_int == 2 and int(input_data['tokenPointer']['tokenId']) == 0:
            input_data['tokenPointer']['tokenId'] = str(token_id)

        quest_inputs_list.append((
            token_type_int,
            Web3.to_checksum_address(input_data['tokenPointer']['tokenContract']['address']),
            int(input_data['tokenPointer']['tokenId']),
            int(input_data['tokenPointer']['amount'])
        ))

    # 7. Construct the quest_params_data using the input list
    quest_params_data = (
        int(quest['id']),  # questId
        # Code to replace the Pirate NFT contract address with whatever the NFT token address we get it, to support the starter pirates
        [(quest_input[0], Web3.to_checksum_address(token_contract) if quest_input[1] == pn._contract_PirateNFT_addr else quest_input[1], quest_input[2], quest_input[3]) for quest_input in quest_inputs_list]
        #quest_inputs_list  # List of input tuples - this is old code that only supports pirate, not starter pirates
    )

    # 8. Create transaction
    try:
        txn = contract.functions.startQuest(quest_params_data).build_transaction({
            'chainId': 42170,
            'gas': 1400000,
            'gasPrice': web3.eth.gas_price,
            'nonce': web3.eth.get_transaction_count(address),
        })

        signed_txn = web3.eth.account.sign_transaction(txn, private_key=key)
        txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        txn_reciept = web3.eth.wait_for_transaction_receipt(txn_hash)

        return txn_hash, pn.get_status_message(txn_reciept)        
    except Exception as e:
        
        # Print the error type and traceback
        print(f"Error type: {type(e).__name__}")
        traceback.print_exc()  # This prints the traceback
        print(f"Error with transaction: {e}")
    
    return None, "Failed to execute transaction"
    

def handle_row(row, is_multi_threaded=True):
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


# Number of threads to use
MAX_THREADS = 3

def parse_arguments():
    parser = argparse.ArgumentParser(description="This is a script to automate bounties")
    
    parser.add_argument("--max_threads", type=int, default=MAX_THREADS, help="Maximum number of threads (default: 2)")

    parser.add_argument("--delay_start", type=int, default=0, help="Delay in minutes before executing logic of the code (default: 0)")    
    
    parser.add_argument("--delay_loop", type=int, default=0, help="Delay in minutes before executing the code again code (default: 0)")


    parser.add_argument("--csv_file", type=str, default=None, help="Specify the csv file of addresses (default: None)") 

    args = parser.parse_args()
    
    return args


def main_script():

    # Pull arguments out for start, end, and delay
    args = parse_arguments()
    print("max_threads:", args.max_threads)
    print("delay_start:", args.delay_start)
    print("delay_loop:", args.delay_loop)
    print("csv_file:", args.csv_file)

    # Load data from csv file
    if args.csv_file: 
        selected_file = pn.data_path(args.csv_file)
    else:
        selected_file = pn.select_file(prefix="addresses_pk", file_extension=".csv")    

    # put in an initial starting delay
    if args.delay_start:
        pn.handle_delay(args.delay_start)

    with open(selected_file, mode='r') as file:
        csv_reader = csv.DictReader(file)

        while True:

            start_time = time.time()

            if args.max_threads > 1 :

                with ThreadPoolExecutor(max_workers=args.max_threads) as executor:
                    results = list(executor.map(handle_row, csv_reader))

                # end the loop if we don't have looping speified
                if args.delay_loop == 0:
                    break
                else:
                    # continue looping with necessary delay
                     pn.handle_delay(args.delay_loop)
            
            else:
                for row in csv_reader:
                    handle_row(row, is_multi_threaded=False)


            end_time = time.time()
            execution_time = end_time - start_time
            print(f"Quest xecution time: {execution_time:.2f} seconds")     

            # end the loop if we don't have looping speified
            if args.delay_loop == 0:
                break
            else:
                # continue looping with necessary delay
                pn.handle_delay(args.delay_loop)

                
main_script()

