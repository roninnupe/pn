import argparse
import time
import functools
import traceback
import pandas as pd
import pn_helper as pn
import pn_quest as PNQ
import questionary
import random
from questionary import Choice
from pygments.token import Token
from prompt_toolkit.styles import Style
from termcolor import colored
from concurrent.futures import ThreadPoolExecutor

# Number of threads to use
MAX_THREADS = 2
_pirate_ids_dict = {}

custom_style = Style.from_dict({
    'questionmark': '#E91E63 bold',
    'selected': '#673AB7 bold',
    'pointer': '#673AB7 bold',
    'answer': '#2196F3 bold',
    'question': 'cyan bold',
})

# Load data from quest_name_mapping.csv
quest_name_mapping_df = pd.read_csv("quest_name_mapping.csv")

# Initialize quest_menu and quest_colors dictionaries
quest_menu = {}
quest_colors = {}

# Iterate through the rows of the DataFrame to populate the dictionaries
for index, row in quest_name_mapping_df.iterrows():
    symbol = row['symbol']
    quest_name = row['quest_name']
    quest_id = int(row['quest_id'])
    color = row['color']
    full_quest_name = symbol + " " + quest_name

    quest_menu[quest_id] = full_quest_name
    quest_colors[full_quest_name] = color

# Add the "Exit" option to quest_menu
quest_menu[99] = "🚪 Exit"

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

    buffer.append(f"{pn.COLOR['BLUE']}---------------------- Wallet {wallet_id} ----------------------{pn.COLOR['END']}")

    initial_energy_balance = pn.get_energy(address)
    buffer.append(f"Initial energy balance: {pn.COLOR['YELLOWLIGHT']}{initial_energy_balance}{pn.COLOR['END']}")

    # Create a copy of chosen_quests
    shuffled_quests = list(chosen_quests)

    # Shuffle the copy of the list
    random.shuffle(shuffled_quests)

    for chosen_quest in shuffled_quests:
        quest_energy_cost = chosen_quest['energy']
        if initial_energy_balance < quest_energy_cost:
            buffer.append(f"Energy insufficient for quest {chosen_quest['name']}. Moving to next quest or wallet.")
            continue

        color_name = quest_colors[chosen_quest['name']]
        color_constant = pn.COLOR[color_name.upper()]

        buffer.append(f"    {color_constant}{chosen_quest['name']}{pn.COLOR['END']}")

        # load up all the pirate IDs per address
        pirate_ids = _pirate_ids_dict.get(address.lower())
        # grab the first pirate ID - the base code has been made smarter where the first pirate id is the captain if one is set
        pirate_id = pirate_ids[0]

        txn_hash_hex, status = PNQ.start_quest(address, key, pirate_id, chosen_quest)
        if status == "Successful": 
            buffer.append(f"        {pn.formatted_time_str()} Transaction {status}: {pn.COLOR['GREEN']}{txn_hash_hex}{pn.COLOR['END']}")

            # Random delay between 7 to 12 seconds
            pn.handle_delay(random.randint(7, 12), time_period="second")           
        else:
            buffer.append(f"        {pn.formatted_time_str()} Transaction {status}: {pn.COLOR['RED']}{txn_hash_hex}{pn.COLOR['END']}")
            break # adding failsafe to break if a transaction fails

        initial_energy_balance -= quest_energy_cost
        buffer.append(f"        Remaining energy: {pn.COLOR['CYAN']}{initial_energy_balance}{pn.COLOR['END']}")

    buffer.append(f"\nTotal Remaining energy for wallet {wallet_id}: {pn.COLOR['CYAN']}{initial_energy_balance}{pn.COLOR['END']}")
    buffer.append(f"{pn.COLOR['BLUE']}-------------------------------------------------------{pn.COLOR['END']}")
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

    global _pirate_ids_dict   

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

    addresses_list = df_addresses['address'].tolist()
    _pirate_ids_dict = pn.get_pirate_ids_dictionary(addresses_list)    

    try:
        body_logic(args, chosen_quests, df_addresses)
    except Exception as e:
        print(f"Final exception: {e}")    

def retry(max_retries=3, delay_seconds=300):
    def decorator_retry(func):
        @functools.wraps(func)
        def wrapper_retry(*args, **kwargs):
            for _ in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    return result  # If successful, return the result
                except Exception as e:
                    error_type = type(e).__name__
                    print(f"Error Type: {error_type}")
                    print(f"Error Message: {str(e)}")
                    traceback.print_exc()  # Print the traceback
                    if _ < max_retries:
                        pn.visual_delay_for(delay_seconds, prefix="Retrying in ")
                    else:
                        print("Maximum retry attempts reached. Exiting...")
                        raise e  # Re-raise the exception after max retries

        return wrapper_retry

    return decorator_retry

@retry(max_retries=100000, delay_seconds=300)
def body_logic(args, chosen_quests, df_addresses):
    while True:
        start_time = time.time()

        if args.max_threads > 1:
            with ThreadPoolExecutor(max_workers=args.max_threads) as executor:
                # Create a list of tuples, each containing the row and chosen_quests
                args_list = [(row, chosen_quests) for _, row in df_addresses.iterrows()]
                results = list(executor.map(lambda args: handle_row(*args), args_list))

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

