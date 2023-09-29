import argparse
import time
import questionary
import pandas as pd
import pn_helper as pn
from eth_utils import to_checksum_address
from concurrent.futures import ThreadPoolExecutor
from ratelimit import limits, sleep_and_retry

MAX_THREADS = 2

# The query used to get all bounties from the PN Grpah
bounty_query = """
    query GetComponentEntities{
      components(where: { id: "0x3ceb3cd6a633684f7095ec8b1842842250978ee3f4f137603421db15b59d137f"}) {
        id
        entities(first: 1000){
          id
          fields {
            name
            value
            worldEntity {
              id
            }
          }
        }
      }
    }
    """

class BountyMappings:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BountyMappings, cls).__new__(cls)
            cls._instance.__initialized = False
        return cls._instance

    def initialize(self):
        if not self.__initialized:
            self.__initialized = True
            self.df = pd.read_csv(pn.data_path("bounty_group_mappings.csv"))

    def get_mappings_df(self):
        self.initialize()
        return self.df
    
_bounty_mappings = BountyMappings()

def get_group_id_by_bounty_name(target_bounty_name, default_group_id):

    # on the rare case the target_bounty_name is blank return the default
    if target_bounty_name is None: return default_group_id

    try:
        bounty_mappings_df = _bounty_mappings.get_mappings_df()

        # Filter the DataFrame for the specified bounty_name
        result = bounty_mappings_df[bounty_mappings_df['bounty_name'].str.strip().str.lower() == target_bounty_name.strip().lower()]

        # Check if any rows match the specified bounty_name
        if not result.empty:
            # Get the group_id from the first matching row (assuming unique bounty names)
            group_id = result.iloc[0]['group_id']
            return group_id
        else:
            return default_group_id  # No matching bounty_name found return the defualt
    except FileNotFoundError as e:
        print(f"File not found: {str(e)}")
        return default_group_id
    except Exception as e:
        print(f"get_group_id_by_bounty_name({target_bounty_name}): An error occurred: {str(e)}")
        return default_group_id


def get_bounty_name_by_group_id(group_id, default_bounty_name=""):
    try:
        bounty_mappings_df = _bounty_mappings.get_mappings_df()

        # Filter the DataFrame for the specified group_id
        result = bounty_mappings_df[bounty_mappings_df['group_id'] == group_id]

        # Check if any rows match the specified group_id
        if not result.empty:
            # Get the bounty_name from the first matching row
            bounty_name = result.iloc[0]['bounty_name']
            return bounty_name
        else:
            return default_bounty_name  # No matching group_id found, return the default
    except FileNotFoundError as e:
        print(f"File not found: {str(e)}")
        return default_bounty_name
    except Exception as e:
        print(f"get_bounty_name_by_group_id({group_id}): An error occurred: {str(e)}")
        return default_bounty_name


class PirateBountyMappings:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PirateBountyMappings, cls).__new__(cls)
            cls._instance.__initialized = False
        return cls._instance

    def initialize(self):
        if not self.__initialized:
            self.__initialized = True
            self.df = pd.read_csv(pn.data_path("pn_pirates.csv"))

    def get_mappings_df(self):
        self.initialize()
        return self.df
    
_pirate_bounty_mappings = PirateBountyMappings()

def get_bounty_for_token_id(token_id):
    pirate_bounty_df = _pirate_bounty_mappings.get_mappings_df()

    matching_row = pirate_bounty_df[pirate_bounty_df['tokenId'] == token_id]
    
    if not matching_row.empty:
        bounty = matching_row.iloc[0]['Bounty']
        if isinstance(bounty, str):
            return bounty
        
    return None  # Token ID not found in the DataFrame or bounty is not a string


# return the bounty hex from the bounty data, using the group_id specified, and fits the proper number of pirates
def get_bounty_hex(data, group_id, num_of_pirates):

    # Initialize a list to store matching entities
    matching_entities = []

    # Iterate through components
    for component in data['data']['components']:
        for entity in component['entities']:
            entity_group_id = None
            lower_bound = None
            upper_bound = None
            for field in entity['fields']:
                if field['name'] == 'group_id':
                    entity_group_id = field['value']
                elif field['name'] == 'lower_bound':
                    lower_bound = int(field['value'])
                elif field['name'] == 'upper_bound':
                    upper_bound = int(field['value'])

            if entity_group_id == group_id and lower_bound is not None and upper_bound is not None:
                if lower_bound <= num_of_pirates <= upper_bound:
                    matching_entities.append(entity)

    if matching_entities:
        first_entity_id = matching_entities[0]['id']
        hex_value = first_entity_id.split('-')[1]
        return hex_value
    else:
        return None


def parse_arguments():
    parser = argparse.ArgumentParser(description="This is a script to automate bounties")

    parser.add_argument("--skip_end", dest="end", action='store_false', default=True,
                        help="Flag to skip the endBounties")

    parser.add_argument("--skip_start", dest="start", action="store_false", default=True,
                        help="Flag to skip startBounty")
    
    parser.add_argument("--max_threads", type=int, default=MAX_THREADS, help=f"Maximum number of threads (default: {MAX_THREADS})")

    args = parser.parse_args()
    return args


class TokenIdExceedsMaxValue(Exception):
    def __init__(self, token_id):
        self.token_id = token_id
        super().__init__(f"Token ID {token_id} exceeds the maximum value")


def main():
    start_time = time.time()
    
    # pull arguments out for start and end
    args = parse_arguments()
    print("endBounty:", args.end)
    print("startBounty:", args.start)
    print("max_theads:", args.max_threads)

    # Load data from csv file
    csv_file = pn.select_file(prefix="addresses_pk", file_extension=".csv")
    df_addressses = pd.read_csv(csv_file) #replace with your file_path

    # Display available bounties to the user only if we have start flag set
    default_group_id = 0
    default_bounty_name = None
    if args.start:
        default_group_id, default_bounty_name = get_default_bounty()
        print(f"{pn.C_GREEN}default_group_id:{pn.C_CYAN} {default_group_id}{pn.C_END}\n\n")

    # Initialize web3 with the PN
    web3 = pn.Web3Singleton.get_web3_Nova()
    bounty_contract = pn.Web3Singleton.get_BountySystem()

    ended_bounties = 0
    started_bounties = 0

    # Load the JSON data from the file
    bounty_data = pn.get_data(bounty_query)

    # CODE if we are going to run bounties multithreaded 
    if args.max_threads > 0 :

        print("Initiating Multithreading")

        #pre initialize for thread safety
        _pirate_bounty_mappings.get_mappings_df()

        with ThreadPoolExecutor(max_workers=args.max_threads) as executor:
            # Submit jobs to the executor
            futures = [executor.submit(process_address, args, default_group_id, default_bounty_name, web3, bounty_contract, bounty_data, row, True) 
                for index, row in df_addressses.iterrows()]

            # Collect results as they come in
            for future in futures:
                buffer, num_ended_bounties, num_started_bounties = future.result()
                ended_bounties += num_ended_bounties
                started_bounties += num_started_bounties

    # if we are going to go in order sequentially
    else:

        for index, row in df_addressses.iterrows():
            buffer, num_ended_bounties, num_started_bounties = process_address(args, default_group_id, default_bounty_name, web3, bounty_contract, bounty_data, row, False)
            ended_bounties += num_ended_bounties
            started_bounties += num_started_bounties

    end_time = time.time()
    execution_time = end_time - start_time           

    print(f"\nclaimed {ended_bounties} bounties and started {started_bounties} bounties in {execution_time:.2f} seconds")


def process_address(args, default_group_id, default_bounty_name, web3, bounty_contract, bounty_data, row, is_multi_threaded):

    start_time = time.time()

    num_ended_bounties = 0
    num_started_bounties = 0

    buffer = []

    wallet = row['wallet']
    address = row['address']
    private_key = row['key']

    if is_multi_threaded: print(f"{pn.C_YELLOWLIGHT}starting thread {wallet}{pn.C_END}")

    buffer.append(f"{pn.C_GREEN}---------------------------------------------------------------------------")
    buffer.append(f"--------------{pn.C_END} {wallet} - {address}")
    buffer.append(f"{pn.C_GREEN}---------------------------------------------------------------------------{pn.C_END}")

    # read the activeBounties for the address
    result, execution_time = rate_limited_active_bounty_ids(bounty_contract, address)
    
    buffer.append(f"\n   Active Bounty IDs: {result}")
    buffer.append(f"   fetched in {execution_time:.2f} seconds\n")

    # handle ending of bounties if we have the end flag set
    if args.end:
        for active_bounty_id in result:
            num_ended_bounties += rate_limited_end_bounty(web3, bounty_contract, address, private_key, active_bounty_id, buffer)        


    # if we don't have start bounties set then continue and skip all the remaining code below
    if not args.start:
        end_time = time.time()
        execution_time = end_time - start_time
        buffer.append(f"\n   {pn.C_CYAN}Execution time: {execution_time:.2f} seconds{pn.C_END}")
        buffer.append(f"{pn.C_GREEN}---------------------------------------------------------------------------{pn.C_END}")   
        print("\n".join(buffer))
        return buffer, num_ended_bounties, num_started_bounties

    # load up all the pirate IDs per address
    pirate_ids = pn.get_pirate_ids(address)

    buffer.append(f"\n   Wallet {wallet} has the following pirates: {pirate_ids}")

    MAX_PIRATE_ON_BOUNTY = 20  
    bounties_to_execute = {default_group_id: []} # initialize a dictionary of bounties and pirates we want to execute

    # Loop through the pirate_ids and load up bounties_to_execute
    for pirate_id in pirate_ids:
        bounty_name = get_bounty_for_token_id(pirate_id)
        bounty_group_id = get_group_id_by_bounty_name(bounty_name, default_group_id)
            
        # Check if the bounty_group_id is already in the dictionary, if not, create an empty list
        if bounty_group_id not in bounties_to_execute:
            bounties_to_execute[bounty_group_id] = []

        # Reconfirm its less than max pirate on the bounty and append it, fall back on the default if the main is full
        if len(bounties_to_execute[bounty_group_id]) < MAX_PIRATE_ON_BOUNTY:
            bounties_to_execute[bounty_group_id].append(pn.pirate_token_id_to_entity(pirate_id))
        elif len(bounties_to_execute[default_group_id]) < MAX_PIRATE_ON_BOUNTY:
            bounties_to_execute[default_group_id].append(pn.pirate_token_id_to_entity(pirate_id))
        else:
            buffer.append(f"{pn.C_RED}Rare edge case: skipping adding {pirate_id} to any bounties{pn.C_END}")

        #buffer.append(f"Pirate ID: {pirate_id}, Bounty Name: {bounty_name}, Group ID: {bounty_group_id}")

    # Now loop over bounties to execute and execute them
    for group_id, entity_ids in bounties_to_execute.items():   
        # if no pirates to send, don't continue on with the remaining logic in this part of the loop
        num_of_pirates = len(entity_ids)
        if num_of_pirates == 0: 
            continue

        hex_value = get_bounty_hex(bounty_data, group_id, num_of_pirates)
            
        # Convert hexadecimal string to base 10 integer
        # FYI, This is the bounty ID for the user-selected bounty_name  
        bounty_id = int(hex_value, 16)   
        bounty_name = get_bounty_name_by_group_id(group_id)

        num_started_bounties += rate_limited_start_bounty(web3, bounty_contract, address, private_key, bounty_name, bounty_id, entity_ids, buffer)
        # Delay to allow the network to update the nonce
        if len(bounties_to_execute) > 1: time.sleep(1)              

    end_time = time.time()
    execution_time = end_time - start_time
    buffer.append(f"\n   {pn.C_CYAN}Execution time: {execution_time:.2f} seconds{pn.C_END}")
    buffer.append(f"{pn.C_GREEN}---------------------------------------------------------------------------{pn.C_END}")    
    print("\n".join(buffer))
    return buffer, num_ended_bounties, num_started_bounties

#Prompts the user to choose a bounty, and returns the respective group id
def get_default_bounty():

    print("Available bounties:")
    
    bounty_mappings_df = _bounty_mappings.get_mappings_df()
    
    # Create a list of choices for questionary
    choices = [{"name": f"{index + 1}. {row['bounty_name']}", "value": (row['group_id'], row['bounty_name'])} for index, row in bounty_mappings_df.iterrows()]

    # Prompt the user to select a default bounty
    selected_group_id, selected_bounty_name = questionary.select(
        "Please select the default bounty you're interested in:",
        choices=choices
    ).ask()

    return selected_group_id, selected_bounty_name


# Define rate limits (e.g., 5 calls per second)
@limits(calls=10, period=1)
def rate_limited_active_bounty_ids(bounty_contract, address):
    start_time = time.time()

    # Your code here
    function_name = 'activeBountyIdsForAccount'
    function_args = [address]
    result = bounty_contract.functions[function_name](*function_args).call()

    end_time = time.time()
    execution_time = end_time - start_time

    return result, execution_time



# Define rate limits (e.g., 2 calls per second)
@limits(calls=10, period=1)
def rate_limited_start_bounty(web3, contract_to_write, address, private_key, bounty_name, bounty_id, pirates, buffer):
    buffer.append(f"   Sending {pn.C_CYAN}{len(pirates)}{pn.C_END} pirate(s) on {pn.C_CYAN}'{bounty_name}'{pn.C_END}: {bounty_id}")
    txn_dict = {
        'from': address,
        'to': contract_to_write.address,
        'value': 0,
        'nonce': web3.eth.get_transaction_count(address),
        'gasPrice': web3.eth.gas_price,
        'data': contract_to_write.encodeABI(fn_name='startBounty', args=[bounty_id, pirates])
    }

    try:
        txn_receipt = pn.send_web3_transaction(web3, private_key, txn_dict)
        status_message = pn.get_status_message(txn_receipt)
        buffer.append(f'   -> {pn.C_GREEN}startBounty {status_message}{pn.C_END}: {txn_receipt.transactionHash.hex()}')
        return 1
    except Exception as e:
        error_type = type(e).__name__
        buffer.append(f"   -> {pn.C_RED}**Error startBounty{pn.C_END}: {e} - {error_type}")
        return 0

# Define rate limits (e.g., 2 calls per second)
@limits(calls=10, period=1)
def rate_limited_end_bounty(web3, contract_to_write, address, private_key, bounty_id, buffer):
    buffer.append(f"   Ending active_bounty_id: {bounty_id}")
    txn_dict = {
        'from': address,
        'to': contract_to_write.address,
        'value': 0,
        'nonce': web3.eth.get_transaction_count(address),
        'gasPrice': web3.eth.gas_price,
        'data': contract_to_write.encodeABI(fn_name='endBounty', args=[bounty_id])
    }

    try:
        # Estimate the gas for this specific transaction
        txn_receipt = pn.send_web3_transaction(web3, private_key, txn_dict)
        status_message = pn.get_status_message(txn_receipt)
        buffer.append(f'   -> {pn.C_GREEN}endBounty {status_message}{pn.C_END}: {txn_receipt.transactionHash.hex()}')
        return 1
    except Exception as e:
        error_type = type(e).__name__
        buffer.append(f"   -> {pn.C_RED}**Error endBounty{pn.C_END}: {e} - {error_type}")
        return 0


if __name__ == "__main__":
    main()