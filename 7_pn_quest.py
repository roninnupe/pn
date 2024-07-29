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
MAX_THREADS = 1
EXPLORE_LOW = 1
EXPLORE_HIGH = 1
_pirate_dict = {}

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
quest_level_required = {}

# Iterate through the rows of the DataFrame to populate the dictionaries
for index, row in quest_name_mapping_df.iterrows():
    symbol = row['symbol']
    quest_name = row['quest_name']
    quest_id = int(row['quest_id'])
    color = row['color']
    full_quest_name = symbol + " " + quest_name

    quest_menu[quest_id] = full_quest_name
    quest_colors[full_quest_name] = color
    level_required = int(row['level_required'])
    quest_level_required[quest_id] = level_required


# Add the "Exit" option to quest_menu
quest_menu[999] = "🚪 Exit"

def get_level_required_by_quest_name(quest_name):
    quest_row = quest_name_mapping_df[quest_name_mapping_df['quest_name'] == quest_name]
    if not quest_row.empty:
        return quest_row.iloc[0]['level_required']
    else:
        return None  # or an appropriate default value or error handling

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

        if chosen_quest_id == 999:  # Check for the exit condition
            break

        # Extract chosen quest details and enrich with additional information
        quest_name = quest_menu.get(chosen_quest_id, "Quest Not Found")
        chosen_quest = next((quest for quest in quest_data["data"]["quests"] if quest["id"] == str(chosen_quest_id)), None)
        if chosen_quest:  # Ensure the quest was found before proceeding
            chosen_quest['name'] = quest_name
            energy_required = int(chosen_quest['inputs'][0]['energyRequired'])
            chosen_quest['energy'] = round((energy_required / 10 ** 18), 0)
            chosen_quest['count'] = 0
            chosen_quest['level_required'] = quest_level_required[chosen_quest_id]

            # Ask how many times the user wants to do this quest
            repeat_count = questionary.text(f"How many times do you want to do {quest_name}?").ask()

            # Validate and convert the input to an integer
            try:
                repeat_count = int(repeat_count)
                # Append the chosen quest 'repeat_count' times
                for _ in range(repeat_count):
                    chosen_quests_local.append(chosen_quest.copy())  # Use copy to ensure separate instances if needed
            except ValueError:
                print("Invalid input. Please enter a valid number.")
                # Optionally, you could ask again or skip adding this quest

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


def handle_row(row, chosen_quests, thread_counter, args):
    start_time = time.time()

    wallet_id = row['identifier']
    address = row['address']
    key = row['key']
    buffer = []
    printed_messages = set()  # Set to track unique insufficient energy messages    

    buffer.append(f"{pn.COLOR['BLUE']}---------------------- Wallet {wallet_id} ----------------------{pn.COLOR['END']}")

    initial_energy_balance = pn.get_energy(address)
    buffer.append(f"Initial energy balance: {pn.COLOR['YELLOWLIGHT']}{initial_energy_balance}{pn.COLOR['END']}")

    pirate_nfts = _pirate_dict.get(address.lower(), [])
    if not pirate_nfts:
        buffer.append(f"No pirate NFTs found for address {address.lower()}")
        print("\n".join(buffer))
        return
    
    # Check only the first pirate if captain_only is true, else iterate through all suitable pirates
    pirate_nfts_to_check = pirate_nfts[:1] if args.captain_only else pirate_nfts

    # if low level priority set then sort by lowest level to highest
    if args.low_level_priority:
        pirate_nfts_to_check = sorted(pirate_nfts_to_check, key=lambda x: int(x.get('level') or 0))

    # handle removing certain levels from pirate NFTs
    if args.skip_level:
        skip_levels = [int(level.strip()) for level in args.skip_level.split(',')]
        suitable_pirates_filtered = [pirate for pirate in pirate_nfts_to_check if int(pirate.get('level') or 0) not in skip_levels]
        pirate_nfts_to_check = suitable_pirates_filtered

    # determine if we need to shuffle
    copied_quests = list(chosen_quests)
    if args.shuffle:
        random.shuffle(copied_quests)

    # set local variables for quest exploration simulation
    prior_chosen_quest = None
    consecutive_quest_count = 0
    max_consecutive_quests = random.randint(1, 4)

    for chosen_quest in copied_quests:
        level_required = int(chosen_quest.get('level_required', 1))
        suitable_pirate = None

        # loop through to find a suitable pirate for the quest
        for pirate in pirate_nfts_to_check:
            pirate_level = int(pirate.get('level') or 0)
            if pirate_level >= level_required:
                suitable_pirate = pirate
                break

        # if there is no suitable pirate
        if not suitable_pirate:
            pirate_message = f"No suitable pirate found for quest {chosen_quest['name']}. Moving to next quest."
            if pirate_message not in printed_messages:
                buffer.append(pirate_message)
                printed_messages.add(pirate_message)
            continue

        # Proceed with the quest using suitable_pirate...
        pirate_id = suitable_pirate.get('id')
        pirate_level = int(suitable_pirate.get('level') or 0)
        pirate_message = f"Using pirate with ID {pirate_id} at level {pirate_level} for quest {chosen_quest['name']}."
        if pirate_message not in printed_messages:
            buffer.append(pirate_message)
            printed_messages.add(pirate_message)

        is_menu_quest = '🔰' in chosen_quest['name']

        quest_energy_cost = chosen_quest['energy']
        if initial_energy_balance is not None and quest_energy_cost is not None:
            if initial_energy_balance < quest_energy_cost:
                energy_message = f"Energy insufficient for quest {chosen_quest['name']}."
                if energy_message not in printed_messages:
                    buffer.append(f"{energy_message} Moving to next quest or wallet.")
                    printed_messages.add(energy_message)  # Add the message to the set to avoid repetition
                continue
        else:
            print(f"Error: Data Issue\n initial_energy_balance = {initial_energy_balance}\n quest_energy_cost = {quest_energy_cost}")
            continue

        color_name = quest_colors[chosen_quest['name']]
        color_constant = pn.COLOR[color_name.upper()]

        buffer.append(f"    {color_constant}{chosen_quest['name']}{pn.COLOR['END']}")

        txn_hash_hex, status = PNQ.start_quest(address, key, pirate_id, chosen_quest, txn_cap=args.txn_cap)
        if status == "Successful":
            buffer.append(f"        {pn.formatted_time_str()} Transaction {status}: {pn.COLOR['GREEN']}{txn_hash_hex}{pn.COLOR['END']}")

            if is_menu_quest:
                time.sleep(2)
            else:
                # Check if the current quest is the same as the prior one
                if chosen_quest['name'] == prior_chosen_quest:
                    if consecutive_quest_count < max_consecutive_quests:
                        # Shorter delay for same, consecutive quest
                        pn.handle_delay(1, time_period="second", desc_msg=f"[{thread_counter}] doing {prior_chosen_quest} again in")
                        consecutive_quest_count += 1  # Increment the consecutive count
                    else:
                        # If the maximum consecutive count is reached, reset and apply longer delay
                        max_consecutive_quests = random.randint(1, 4)  # Choose a new threshold for next time
                        pn.handle_delay(random.randint(EXPLORE_LOW, EXPLORE_HIGH), time_period="second", desc_msg=f"[{thread_counter}] finished {chosen_quest['name']} exploring for")
                        consecutive_quest_count = 1  # Reset the counter
                else:
                    # If a different quest is chosen, reset the counter and choose a new threshold
                    consecutive_quest_count = 1
                    max_consecutive_quests = random.randint(1, 4)
                    pn.handle_delay(random.randint(EXPLORE_LOW, EXPLORE_HIGH), time_period="second", desc_msg=f"[{thread_counter}] finished {chosen_quest['name']} exploring for")

            prior_chosen_quest = chosen_quest['name']  # Update the prior chosen quest
      
        else:
            buffer.append(f"        {pn.formatted_time_str()} Transaction {status}: {pn.COLOR['RED']}{txn_hash_hex}{pn.COLOR['END']}")
            time.sleep(2)
            break # adding failsafe to break if a transaction fails

        initial_energy_balance -= quest_energy_cost
        buffer.append(f"        Remaining energy: {pn.COLOR['CYAN']}{initial_energy_balance}{pn.COLOR['END']}")

    buffer.append(f"\nTotal Remaining energy for wallet {wallet_id}: {pn.COLOR['CYAN']}{initial_energy_balance}{pn.COLOR['END']}")

    # End the timer
    end_time = time.time()
    execution_time = end_time - start_time
    # Calculate minutes and seconds
    minutes = int(execution_time // 60)
    seconds = int(execution_time % 60)   

    # Add the execution time to the buffer
    buffer.append(f"        Quest execution time: {minutes} minutes and {seconds} seconds.")

    buffer.append(f"{pn.COLOR['BLUE']}-------------------------------------------------------{pn.COLOR['END']}")
    print("\n".join(buffer))


def parse_arguments():
    parser = argparse.ArgumentParser(description="This script automates quest assignment considering pirate levels and preferences.")

    # Existing arguments
    parser.add_argument("--threads", type=int, default=1, help="Maximum number of threads.")
    parser.add_argument("--delay_start", type=int, default=0, help="Delay in minutes before start.")
    parser.add_argument("--delay_loop", type=int, default=0, help="Delay in minutes before each loop iteration.")
    parser.add_argument("--wallets", type=str, help="Specify wallets range (e.g., 1-5,10).")
    parser.add_argument("--shuffle", action='store_true', help="Enable shuffling of quests for each wallet (default: False)")
    parser.add_argument("--skip_level", type=str, default=None, help="Levels of pirates to skip (e.g., '30' or '29,30').")
    parser.add_argument("--txn_cap", type=float, default=0.0369, help="Transaction cost cap in USD (default: 0.0369).")

    # New arguments for captain only and low level priority
    parser.add_argument("--captain_only", action='store_true', help="Only use the captain NFT for each wallet.")
    parser.add_argument("--low_level_priority", action='store_true', help="Prioritize lower level pirates for quests.")

    args = parser.parse_args()

    # Check if both --captain_only and --low_level_priority are set
    if args.captain_only and args.low_level_priority:
        parser.error("--captain_only and --low_level_priority cannot be used together.")

    return args

def main_script():

    global _pirate_dict   

    # Pull arguments out for start, end, and delay
    args = parse_arguments()
    print("threads:", args.threads)
    print("delay_start:", args.delay_start)
    print("delay_loop:", args.delay_loop)
    print("wallets:", args.wallets)
    print("shuffle:", args.shuffle)
    print("captain_only:", args.captain_only)
    print("low_level_priority", args.low_level_priority)
    print("txn_cap", args.txn_cap)


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

    df_addresses = pn.get_full_wallet_data(walletlist)

    addresses_list = df_addresses['address'].tolist()
    _pirate_dict = pn.get_pirate_nfts_dictionary(addresses_list)    

    # put in an initial starting delay
    if args.delay_start:
        pn.handle_delay(args.delay_start)

    try:
        body_logic(args, chosen_quests, df_addresses)
    except Exception as e:
        error_type = type(e).__name__
        print(f"Error Type: {error_type}")
        print(f"Error Message: {str(e)}")
        traceback.print_exc()  # Print the traceback
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


def body_logic(args, chosen_quests, df_addresses):  # Add shuffle_for_each_wallet as an argument
    thread_counter = 0  # Initialize the thread counter

    while True:
        start_time = time.time()

        if args.threads > 1:

            # Instantiate the singletons before multithreading
            pn.Web3Singleton.get_EnergySystem()
            pn.Web3Singleton.get_QuestSystem()

            with ThreadPoolExecutor(max_workers=args.threads) as executor:
                # Create a list of arguments for handle_row, each containing the row and other required parameters
                args_list = [(row.to_dict(), chosen_quests, thread_counter + i, args) 
                             for i, (_, row) in enumerate(df_addresses.iterrows())]
                # Map handle_row over args_list using the executor
                results = list(executor.map(lambda x: handle_row(*x), args_list))
                thread_counter += len(args_list)  # Update the thread counter after the batch is submitted
        else:
            for index, row in df_addresses.iterrows():
                handle_row(row.to_dict(), chosen_quests, thread_counter, args)
                thread_counter += 1  # Update the thread counter for each single thread

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

