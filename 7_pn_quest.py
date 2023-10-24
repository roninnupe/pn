import argparse
import time
import pandas as pd
import pn_helper as pn
import pn_quest as PNQ
from web3 import Web3, HTTPProvider
from eth_utils import to_checksum_address
from termcolor import colored
import questionary
from questionary import Choice
from pygments.token import Token
from prompt_toolkit.styles import Style
from termcolor import colored
from itertools import cycle
from concurrent.futures import ThreadPoolExecutor

# Number of threads to use
MAX_THREADS = 2

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


# Grabs the first pirate ID for an NFT in the address... this isn't smart.
def get_pirate_id(address):
    global id_value

    query = pn.make_pirate_query(address)
    json_data = pn.get_data(query)

    for account in json_data['data']['accounts']:
        for nft in account['nfts']:
            id_value = nft['id']

    return id_value


def handle_row(row, chosen_quests, is_multi_threaded=True):

    wallet_id = row['identifier']
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
        pirate_id = get_pirate_id(address)
        txn_hash_hex, status = PNQ.start_quest(address, key, pirate_id, chosen_quest)
        if status == "Successful": 
            buffer.append(f"        {pn.formatted_time_str()} Transaction {status}: {C_GREEN}{txn_hash_hex}{C_END}")
        else:
            buffer.append(f"        {pn.formatted_time_str()} Transaction {status}: {C_RED}{txn_hash_hex}{C_END}")
            break # adding failsafe to break if a transaction fails

        initial_energy_balance -= quest_energy_cost
        buffer.append(f"        Remaining energy: {C_CYAN}{initial_energy_balance}{C_END}")

    buffer.append(f"\nTotal Remaining energy for wallet {wallet_id}: {C_CYAN}{initial_energy_balance}{C_END}")
    buffer.append(f"{C_BLUE}-------------------------------------------------------{C_END}")
    print("\n".join(buffer))


def parse_arguments():
    parser = argparse.ArgumentParser(description="This is a script to automate bounties")
    
    parser.add_argument("--max_threads", type=int, default=MAX_THREADS, help="Maximum number of threads (default: 2)")

    parser.add_argument("--delay_start", type=int, default=0, help="Delay in minutes before executing logic of the code (default: 0)")    
    
    parser.add_argument("--delay_loop", type=int, default=0, help="Delay in minutes before executing the code again code (default: 0)")

    parser.add_argument("--wallets", type=str, default=None, help="Specify the wallet range you'd like (e.g., 1-10,15,88-92) (default: None)") 

    args = parser.parse_args()
    
    return args


def main_script():

    # Pull arguments out for start, end, and delay
    args = parse_arguments()
    print("max_threads:", args.max_threads)
    print("delay_start:", args.delay_start)
    print("delay_loop:", args.delay_loop)
    print("wallets:", args.wallets)

    # Fetch the quest data using fetch_quest_data() from pn_helper
    chosen_quests = display_quest_menu()

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

    # Load data from csv file
    if args.wallets: 

        walletlist = args.wallets

    else:

        # Prompt the user for a wallet range
        while True:
            range_input = input("Input the wallet range you'd like (e.g., 1-10,15,88-92): ")
            walletlist = pn.parse_number_ranges(range_input)
    
            if walletlist:
                break
            else:
                print("Invalid input. Please enter a valid wallet range.")

    # put in an initial starting delay
    if args.delay_start:
        pn.handle_delay(args.delay_start)

    df_addresses = pn.get_full_wallet_data(walletlist)

    while True:

        start_time = time.time()

        if args.max_threads > 1:

            with ThreadPoolExecutor(max_workers=args.max_threads) as executor:
                # Create a list of tuples, each containing the row and chosen_quests
                args_list = [(row, chosen_quests) for _, row in df_addresses.iterrows()]
                results = list(executor.map(lambda args: handle_row(*args), args_list))

            # end the loop if we don't have looping specified
            if args.delay_loop == 0:
                break
            else:
                # continue looping with necessary delay
                pn.handle_delay(args.delay_loop)
        
        else:
            for index, row in df_addresses.iterrows():
                handle_row(row, chosen_quests, is_multi_threaded=False)

        end_time = time.time()
        execution_time = end_time - start_time
        print(f"Quest execution time: {execution_time:.2f} seconds")

        # end the loop if we don't have looping specified
        if args.delay_loop == 0:
            break
        else:
            # continue looping with necessary delay
            pn.handle_delay(args.delay_loop)


main_script()

