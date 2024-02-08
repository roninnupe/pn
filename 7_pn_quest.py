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

        # Extract chosen quest details
        quest_name = quest_menu.get(chosen_quest_id, "Quest Not Found")
        chosen_quest = next((quest for quest in quest_data["data"]["quests"] if quest["id"] == str(chosen_quest_id)), None)
        chosen_quest['name'] = quest_name
        energy_required = int(chosen_quest['inputs'][0]['energyRequired'])
        chosen_quest['energy'] = round((energy_required / 10 ** 18), 0)
        chosen_quest['count'] = 0

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


def handle_row(row, chosen_quests, thread_counter, max_threads, shuffle_for_each_wallet, hide_energy_threshold):  

    start_time = time.time()

    wallet_id = row['identifier']
    address = row['address']
    key = row['key']
    buffer = []

    buffer.append(f"{pn.COLOR['BLUE']}---------------------- Wallet {wallet_id} ----------------------{pn.COLOR['END']}")

    initial_energy_balance = pn.get_energy(address)
    buffer.append(f"Initial energy balance: {pn.COLOR['YELLOWLIGHT']}{initial_energy_balance}{pn.COLOR['END']}")

    # Create a copy of chosen_quests
    copied_quests = list(chosen_quests)

    if shuffle_for_each_wallet:
        random.shuffle(copied_quests)

    prior_chosen_quest = None
    consecutive_quest_count = 0
    max_consecutive_quests = random.randint(1, 3)  # Randomly choose a new threshold

    for chosen_quest in copied_quests:

        is_hidden_quest = '🚫' in chosen_quest['name']

        quest_energy_cost = chosen_quest['energy']
        if initial_energy_balance is not None and quest_energy_cost is not None:
            if initial_energy_balance < quest_energy_cost:
                buffer.append(f"Energy insufficient for quest {chosen_quest['name']}. Moving to next quest or wallet.")
                continue
            elif is_hidden_quest and (initial_energy_balance - quest_energy_cost) < hide_energy_threshold : 
                buffer.append(f"Can't cross {hide_energy_threshold} energy threshold for quest {chosen_quest['name']}. Moving to next quest or wallet.")
                continue
        else:
            print(f"Error: Data Issue\n initial_energy_balance = {initial_energy_balance}\n quest_energy_cost = {quest_energy_cost}")
            # Handle the case where one of the variables is None, maybe set a default or skip the operation
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

            if is_hidden_quest:
                print("$PGLD cha-ching!")
                time.sleep(random.randint(1, 4))
            else:

                # Check if the current quest is the same as the prior one
                if chosen_quest['name'] == prior_chosen_quest:
                    if consecutive_quest_count < max_consecutive_quests:
                        # Shorter delay for same, consecutive quest
                        pn.handle_delay(random.randint(1, 2), time_period="second", desc_msg=f"[{thread_counter}] doing {prior_chosen_quest} again in")
                        consecutive_quest_count += 1  # Increment the consecutive count
                    else:
                        # If the maximum consecutive count is reached, reset and apply longer delay
                        max_consecutive_quests = random.randint(2, 4)  # Choose a new threshold for next time
                        pn.handle_delay(random.randint(5, 45), time_period="second", desc_msg=f"[{thread_counter}] finished {chosen_quest['name']} exploring for")
                        consecutive_quest_count = 1  # Reset the counter
                else:
                    # If a different quest is chosen, reset the counter and choose a new threshold
                    consecutive_quest_count = 1
                    max_consecutive_quests = random.randint(2, 4)
                    pn.handle_delay(random.randint(5, 45), time_period="second", desc_msg=f"[{thread_counter}] finished {chosen_quest['name']} exploring for")

            prior_chosen_quest = chosen_quest['name']  # Update the prior chosen quest
      
        else:
            buffer.append(f"        {pn.formatted_time_str()} Transaction {status}: {pn.COLOR['RED']}{txn_hash_hex}{pn.COLOR['END']}")
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

    df_addresses = pn.get_full_wallet_data(walletlist)

    addresses_list = df_addresses['address'].tolist()
    _pirate_ids_dict = pn.get_pirate_ids_dictionary(addresses_list)    

    # Ask the user if they want to shuffle quests for each wallet
    shuffle_for_each_wallet = questionary.confirm("Do you want to shuffle the quests for each wallet? (y/n)").ask()

    # Collect hide_energy_threshold input
    hide_energy_threshold_str = questionary.text("Enter hide energy threshold as a number:").ask()
        # Validate the input and convert to a number
    try:
        hide_energy_threshold = int(hide_energy_threshold_str)
    except ValueError:
        hide_energy_threshold = 0

    # put in an initial starting delay
    if args.delay_start:
        pn.handle_delay(args.delay_start)

    try:
        body_logic(args, chosen_quests, df_addresses, shuffle_for_each_wallet, hide_energy_threshold)  # Add shuffle_for_each_wallet as an argument
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


def body_logic(args, chosen_quests, df_addresses, shuffle_for_each_wallet, hide_energy_threshold):  # Add shuffle_for_each_wallet as an argument
    thread_counter = 0  # Initialize the thread counter

    while True:
        start_time = time.time()

        if args.max_threads > 1:

            # Instantiate the singletons before multithreading
            pn.Web3Singleton.get_EnergySystem()
            pn.Web3Singleton.get_QuestSystem()

            with ThreadPoolExecutor(max_workers=args.max_threads) as executor:
                # Create a list of arguments for handle_row, each containing the row and other required parameters
                args_list = [(row.to_dict(), chosen_quests, thread_counter + i, args.max_threads, shuffle_for_each_wallet, hide_energy_threshold) 
                             for i, (_, row) in enumerate(df_addresses.iterrows())]
                # Map handle_row over args_list using the executor
                results = list(executor.map(lambda x: handle_row(*x), args_list))
                thread_counter += len(args_list)  # Update the thread counter after the batch is submitted
        else:
            for index, row in df_addresses.iterrows():
                handle_row(row.to_dict(), chosen_quests, thread_counter, args.max_threads, shuffle_for_each_wallet, hide_energy_threshold)
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

