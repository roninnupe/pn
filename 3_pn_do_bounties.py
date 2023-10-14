import argparse
import requests
import math
import time
import questionary
import pandas as pd
import pn_helper as pn
from eth_utils import to_checksum_address
from concurrent.futures import ThreadPoolExecutor
from ratelimit import limits, sleep_and_retry

MAX_THREADS = 2
MAX_PIRATE_ON_BOUNTY = 20
SLOW_FACTOR = 0.5  

_successfully_started_bounties = {}
_pending_bounties = {}

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
    """
    Singleton class to manage mappings of bounty names to associated group IDs.

    This class implements the Singleton design pattern to ensure that only one instance
    of the mappings is created and used throughout the application's lifecycle. It provides
    methods to initialize and retrieve the bounty name-to-group ID mappings.

    Usage:
    - To initialize the mappings, call the `initialize` method.
    - To get the mappings DataFrame, call the `get_mappings_df` method.

    Example:
    >>> _bounty_mappings = BountyMappings()
    >>> mappings = _bounty_mappings.get_mappings_df()

    NOTE: We auto initialize this below this class definition
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BountyMappings, cls).__new__(cls)
            cls._instance.__initialized = False
        return cls._instance

    def initialize(self):
        """
        Initialize the bounty mappings if not already initialized.

        This method reads the bounty name-to-group ID mappings from a CSV file and
        initializes the DataFrame. It should be called before using `get_mappings_df`.

        Note:
        - The initialization is performed only once per instance.
        """
        if not self.__initialized:
            self.__initialized = True
            self.df = pd.read_csv(pn.data_path("bounty_group_mappings.csv"))

    def get_mappings_df(self):
        """
        Get the DataFrame containing bounty name-to-group ID mappings.

        Returns:
        - pd.DataFrame: A DataFrame containing the mappings of bounty names to group IDs.
        """
        self.initialize()
        return self.df

# Automatically create an instance of BountyMappings and initialize it
_bounty_mappings = BountyMappings()

def get_group_id_by_bounty_name(target_bounty_name):
    """
    Looks up and returns the group ID associated with a specified "target_bounty_name" by searching in a mappings DataFrame.

    Parameters:
    - target_bounty_name (str): The bounty name to search for.
    - default_group_id (int): The default group ID to return if no matching bounty name is found.

    Returns:
    - int: The group ID associated with the specified bounty name if found; otherwise, the default_group_id.

    Description:
    This function performs a lookup in a mappings DataFrame to find the group ID associated with a given bounty name.
    - If the target_bounty_name is blank or None, it returns None.
    - It filters the DataFrame for the specified bounty_name, ignoring case and leading/trailing spaces.
    - If a matching bounty name is found in the DataFrame, it returns the associated group_id.
    - If no matching bounty_name is found, it returns None.
    
    Exceptions:
    - If the mappings DataFrame file is not found, a FileNotFoundError is caught, and the function returns the default_group_id.
    - If any other unexpected error occurs during execution, it prints an error message and returns the default_group_id.
    """

    # on the rare case the target_bounty_name is blank return the default
    if target_bounty_name is None: return None

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
            return None # No matching bounty_name found return the default
    except FileNotFoundError as e:
        print(f"File not found: {str(e)}")
        return None
    except Exception as e:
        print(f"get_group_id_by_bounty_name({target_bounty_name}): An error occurred: {str(e)}")
        return None

def get_bounty_name_by_group_id(group_id):
    """
    Get the bounty name associated with a given group ID from a mappings DataFrame.

    This function looks up and returns the bounty name associated with a specified group ID
    by searching a mappings DataFrame. If no match is found, it returns None

    Parameters:
    - group_id (str): The group ID to search for in the mappings DataFrame.

    Returns:
    - str: The bounty name associated with the specified group ID, or the default bounty name if not found.

    Raises:
    - FileNotFoundError: If the mappings DataFrame file is not found.
    - Exception: If an error occurs during the lookup process.

    Example:
    >>> get_bounty_name_by_group_id("64852995522241079254955103336038394316923813690904545645769373840517472839164", "Default Bounty")
    'Ore Galore'
    """

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
            return None  # No matching group_id found, return the default
    except FileNotFoundError as e:
        print(f"File not found: {str(e)}")
        return None
    except Exception as e:
        print(f"get_bounty_name_by_group_id({group_id}): An error occurred: {str(e)}")
        return None

# Initialize a dictionary to store cached results
bounty_limit_cache = {}

def get_bounty_limit_by_group_id(group_id):
    """
    Retrieves the bounty limit (maximum number of pirates allowed on a bounty)
    associated with a specified group ID. Caches the result for performance
    to avoid redundant lookups during the script's execution.

    Parameters:
        group_id (str): The group ID for which to retrieve the bounty limit.

    Returns:
        int: The bounty limit for the specified group ID.
             If not found, returns the default maximum pirate count.

    Caching:
        The function caches results to avoid redundant lookups for the same group ID,
        improving performance.
        Cached results are stored in the 'bounty_limit_cache' dictionary.
    """

    try:

        if group_id in bounty_limit_cache:
            return int(bounty_limit_cache[group_id])

        bounty_mappings_df = _bounty_mappings.get_mappings_df()

        #print("Columns in bounty_mappings_df:", bounty_mappings_df.columns)  # Print column names

        result = bounty_mappings_df[bounty_mappings_df['group_id'] == group_id]

        #print("Resulting DataFrame for group_id:", group_id)
        #print(result)  # Print the result DataFrame to see its structure

        if not result.empty:
            bounty_limit = result.iloc[0]['limit']
            bounty_limit_cache[group_id] = bounty_limit
            return bounty_limit
        else:
            bounty_limit_cache[group_id] = MAX_PIRATE_ON_BOUNTY
            return MAX_PIRATE_ON_BOUNTY
    except FileNotFoundError as e:
        print(f"File not found: {str(e)}")
        return MAX_PIRATE_ON_BOUNTY
    except Exception as e:
        print(f"get_bounty_name_by_group_id({group_id}): An error occurred: {str(e)}")
        #traceback.print_exc()  # Print the full traceback for the exception
        return MAX_PIRATE_ON_BOUNTY


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
            self.reload_data()  # Initialize by loading data from the CSV file

    def reload_data(self):
        self.df = pd.read_csv(pn.data_path("pn_pirates.csv"), low_memory=False)

    def get_mappings_df(self):
        self.initialize()
        return self.df

_pirate_bounty_mappings = PirateBountyMappings()


def get_bounty_name_for_token_id(token_id, generation):
    """
    Get the bounty name associated with a specific Pirate NFT token ID and generation.

    This function retrieves the bounty name linked to a given Pirate NFT token ID
    and generation from a loaded DataFrame of pirate-to-bounty mappings. If a matching
    token ID and generation is found, it returns the associated bounty name. If the
    token ID and generation are not found or the associated bounty is not a string,
    it returns the provided default bounty name.

    Parameters:
    - token_id (int): The Pirate NFT token ID to look up.
    - generation (int): The Generation of the Pirate ID.

    Returns:
    - str: The bounty name associated with the specified token ID and generation or the default bounty name.

    Example:
    >>> get_bounty_name_for_token_id(12345, 2, "Default Bounty")
    'Ore Galore'
    """

    pirate_bounty_df = _pirate_bounty_mappings.get_mappings_df()

    matching_row = pirate_bounty_df[(pirate_bounty_df['tokenId'] == token_id) & (pirate_bounty_df['Gen'] == generation)]
    
    if not matching_row.empty:
        bounty = matching_row.iloc[0]['Bounty']
        if isinstance(bounty, str):
            return bounty
        
    return None # Token ID and generation not found in the DataFrame or bounty is not a string


def get_bounty_name_and_id(data, group_id, entity_ids) -> (str, int):
    """
    Get the bounty name and ID for a specified group ID and the number of entity pirates.

    This function calculates the bounty name and ID based on the provided group ID and the number
    of entity IDs (pirates) intended for the bounty. It uses these parameters to determine
    the appropriate bounty based on the number of pirates.

    Parameters:
    - data (DataFrame): The bounty data frame used to determine the correct bounty ID.
    - group_id (str): The group ID associated with the bounty.
    - entity_ids (List[int]): The list of entity IDs (pirates) intended for the bounty.

    Returns:
    - Tuple[str, int]: A tuple containing the bounty name and its corresponding ID.

    Note:
    - If the group ID is "0" (string), indicating no valid group, it returns "None (No groupId)" and 0 as the bounty ID.
    - If there are no pirates (empty entity_ids), it returns "None (0 pirates)" and 0 as the bounty ID.
    - If an exception occurs during the conversion, it returns "None (Exception hex_value: {bounty_hex_value})" and 0 as the bounty ID.

    Example:
    >>> get_bounty_name_and_id(bounty_data_df, "1A", [1, 2, 3])
    ('Bounty Name 1A', 12345)
    """
    
    # If the group_id is effectively 0 (string), return "None (No groupId)" and 0
    if group_id == "0":
        return "None (No groupId)", 0

    # Get the length of entity_ids to determine the appropriate bounty
    num_of_pirates = len(entity_ids)

    # If there are no pirates, return "None (0 pirates)" and 0
    if num_of_pirates == 0:
        return "None (0 pirates)", 0

    # Calculate the bounty_hex_value based on group_id and the number of pirates
    bounty_hex_value = get_bounty_hex(data, group_id, num_of_pirates)
    
    try:
        # Perform a reverse lookup to get the bounty name by group ID
        bounty_name = get_bounty_name_by_group_id(group_id)

        # Convert hexadecimal string to base 10 integer (bounty ID)
        bounty_id = int(bounty_hex_value, 16)

        return bounty_name, bounty_id
        
    except Exception as e:
        # Handle exceptions by returning an appropriate message and 0 as the bounty ID
        return f"None (Exception hex_value: {bounty_hex_value})", 0



def get_bounty_hex(data, group_id, num_of_pirates):
    """
    Get the bounty hexadecimal value from the bounty data based on the specified group ID and the number of pirates.

    This function searches the provided bounty data for the matching group ID and the appropriate number of pirates.
    It extracts and returns the hexadecimal value of the bounty associated with the provided parameters.

    Parameters:
    - data (dict): The bounty data dictionary containing components and entities.
    - group_id (str): The group ID for which to find the bounty.
    - num_of_pirates (int): The number of pirates to determine the appropriate bounty.

    Returns:
    - str: The hexadecimal value of the bounty associated with the group ID and pirate count.
    
    Note:
    - The function iterates through components and entities in the bounty data to find a matching group ID.
    - It checks the range of pirates specified by the 'lower_bound' and 'upper_bound' fields in each entity.
    - If a matching entity is found, the function returns the hexadecimal value of its ID.
    - If no matching entity is found, it returns None.

    Example:
    >>> get_bounty_hex(bounty_data, "1A", 5)
    '0xABCDEF0123456789'
    """
    
    # Initialize a list to store matching entities
    matching_entities = []

    # Iterate through components in the bounty data
    for component in data['data']['components']:
        for entity in component['entities']:
            entity_group_id = None
            lower_bound = None
            upper_bound = None
            
            # Extract relevant fields from the entity
            for field in entity['fields']:
                if field['name'] == 'group_id':
                    entity_group_id = field['value']
                elif field['name'] == 'lower_bound':
                    lower_bound = int(field['value'])
                elif field['name'] == 'upper_bound':
                    upper_bound = int(field['value'])

            # Check if the entity matches the specified group ID and pirate count
            if entity_group_id == group_id and lower_bound is not None and upper_bound is not None:
                if lower_bound <= num_of_pirates <= upper_bound:
                    matching_entities.append(entity)

    # If matching entities are found, return the hexadecimal value of the bounty
    if matching_entities:
        first_entity_id = matching_entities[0]['id']
        # Extract the hex_value of the bounty from the entity ID
        hex_value = first_entity_id.split('-')[1]
        return hex_value
    else:
        # Return None if no matching entity is found
        return None


class TokenIdExceedsMaxValue(Exception):
    """
    Custom exception to represent an error when a token ID exceeds the maximum allowed value.

    Attributes:
    - token_id (int): The token ID that exceeds the maximum value.

    Example:
    >>> raise TokenIdExceedsMaxValue(10000)
    TokenIdExceedsMaxValue: Token ID 10000 exceeds the maximum value
    """

    def __init__(self, token_id):
        """
        Initialize the exception with the provided token ID.

        Args:
        - token_id (int): The token ID that exceeds the maximum value.
        """
        self.token_id = token_id
        super().__init__(f"Token ID {token_id} exceeds the maximum value")

def insert_address_into_dictionary(dictionary, key, address):
    """
    Insert an address into a dictionary of lists associated with keys, ensuring uniqueness.

    Parameters:
        dictionary (dict): The dictionary to insert the address into.
        key (hashable): The key to associate with the address in the dictionary.
        address: The address to insert into the list associated with the key.

    Explanation:
        This function is used to maintain a dictionary where each key is associated with a list of addresses.
        It ensures that addresses are unique within each list.

        - If the key is not already in the dictionary, a new key is created with a list containing the address.
        - If the key is already in the dictionary, the function checks if the address is already in the list.
          - If the address is not in the list, it's appended to the list.
          - If the address is already in the list, it won't be added again to maintain uniqueness.
    """
    if key not in dictionary:
        # If the key is not in the dictionary, create a new key with a list containing the address.
        dictionary[key] = [address]
    elif address not in dictionary[key]:
        # If the key is in the dictionary and the address is not in the list, append the address to the list.
        dictionary[key].append(address)


# A list of fallback bounties #NEW
_fallback_bounties = []

def input_choose_bounty(prompt="Please select the default bounty you're interested in:"):
    """
    Prompts the user to choose a bounty and returns the respective group ID and bounty name.

    This function displays a list of available bounties to the user, allowing them to select one.
    It retrieves the bounty data from the mapping file and presents it to the user for selection.

    Returns:
    - selected_group_id (str): The group ID of the selected default bounty.
    - selected_bounty_name (str): The name of the selected default bounty.

    Example:
    >>> group_id, bounty_name = get_default_bounty()
    Please select the default bounty you're interested in:
    1. Bounty 1
    2. Bounty 2
    ...
    Selected: 1
    >>> print(group_id)
    '12345'
    >>> print(bounty_name)
    'Bounty 1'
    """
    
    print("Available bounties:")
    
    # Retrieve the bounty mappings DataFrame
    bounty_mappings_df = _bounty_mappings.get_mappings_df()
    
    # Create a list of choices for questionary
    choices = [{"name": f"{index + 1}. {row['bounty_name']}", "value": (row['group_id'], row['bounty_name'])} for index, row in bounty_mappings_df.iterrows()]

    # Prompt the user to select a default bounty
    selected_group_id, selected_bounty_name = questionary.select(
        prompt,
        choices=choices
    ).ask()

    return selected_group_id, selected_bounty_name


@limits(calls=10, period=1)
def rate_limited_active_bounty_ids(bounty_contract, address):
    """
    Fetches active bounty IDs for a specific account from a bounty contract.

    Args:
        bounty_contract (object): The bounty contract instance.
        address (str): The account address to query.

    Returns:
        result (list): List of active bounty IDs.
        execution_time (float): The execution time in seconds.

    Example:
    >>> active_bounty_ids, execution_time = rate_limited_active_bounty_ids(bounty_contract_instance, '0xAddress')
    >>> print(active_bounty_ids)
    ['0x123', '0x456']
    >>> print(execution_time)
    0.123
    """
    start_time = time.time()

    # Your code here
    function_name = 'activeBountyIdsForAccount'
    function_args = [address]
    result = bounty_contract.functions[function_name](*function_args).call()

    end_time = time.time()
    execution_time = end_time - start_time

    return result, execution_time


@limits(calls=10, period=1)
def rate_limited_has_pending_bounty(contract, address, group_id):
    """
    Checks if an account has a pending bounty for a specific group ID.

    Args:
        contract (object): The contract instance.
        address (str): The account address to check.
        group_id (str): The group ID of the bounty to check.

    Returns:
        result (bool): True if a pending bounty exists, False otherwise.

    Example:
    >>> has_pending = rate_limited_has_pending_bounty(contract_instance, '0xAddress', '12345')
    >>> print(has_pending)
    True
    """
    try:
        function_name = 'hasPendingBounty'
        function_args = [address, int(group_id)]
        result = contract.functions[function_name](*function_args).call()
        return result
    except Exception as e:
        error_type = type(e).__name__
        print(f"   {pn.C_RED}**has_pending_bounty -> Exception: {e} - {error_type}{pn.C_END}")
        return False


@limits(calls=10, period=1)
def rate_limited_is_bounty_available(contract, address, bounty_id):
    """
    Check if a bounty is available for a given address and bounty ID using rate limiting.

    This function uses rate limiting to avoid making too many calls to the blockchain in a short time.

    Args:
        contract: The smart contract instance.
        address (str): The Ethereum address to check.
        bounty_id (int): The ID of the bounty to check.

    Returns:
        bool: True if the bounty is available, False otherwise.
    """
    try:
        function_name = 'isBountyAvailable'
        function_args = [address, int(bounty_id)]
        result = contract.functions[function_name](*function_args).call()
        return result
    except Exception as e:
        error_type = type(e).__name__
        print(f"{pn.C_RED}**is_bounty_available -> Exception: {e} - {error_type}{pn.C_END}")
        return False


@limits(calls=10, period=1)
def rate_limited_start_bounty(web3, contract_to_write, address, private_key, bounty_name, bounty_id, pirates, buffer):
    """
    Starts a bounty with rate limiting.

    Args:
        web3 (object): The Web3 instance.
        contract_to_write (object): The contract instance for writing.
        address (str): The sender's address.
        private_key (str): The sender's private key.
        bounty_name (str): The name of the bounty.
        bounty_id (str): The ID of the bounty.
        pirates (list): List of pirates to send on the bounty.
        buffer (list): Buffer to store output messages.

    Returns:
        success (int): 1 if the bounty was started successfully, 0 if there was an error.

    Example:
    >>> success = rate_limited_start_bounty(web3_instance, contract_instance, '0xSenderAddress', '0xPrivateKey', 'BountyName', '12345', ['0xPirate1', '0xPirate2'], [])
    >>> print(success)
    1
    """

    buffer.append(f"   Sending {pn.C_CYAN}{len(pirates)} pirate(s){pn.C_END} on {pn.C_CYAN}'{bounty_name}'{pn.C_END}")
    buffer.append(f"      -> entities: {pirates}")
    buffer.append(f"      -> bounty id: {bounty_id}")

    # Print out the pirates' addresses and token IDs
    for pirate in pirates:
        address_str, token_id = pn.entity_to_token(pirate)
        buffer.append(f"      -> {address_str}, Token ID: {pn.C_CYAN}{token_id}{pn.C_END}")

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
        buffer.append(f'      -> {pn.C_GREEN}startBounty {status_message}{pn.C_END}: {txn_receipt.transactionHash.hex()}\n')
        insert_address_into_dictionary(_successfully_started_bounties, bounty_name, address)
        return 1
    except Exception as e:
        error_type = type(e).__name__
        buffer.append(f"      -> {pn.C_RED}**Error startBounty{pn.C_END}: {e} - {error_type}\n")
        return 0


# Custom exception class for status message "failed"
class BountyFailedError(Exception):
    def __init__(self, message="Bounty failed"):
        self.message = message
        super().__init__(self.message)

@limits(calls=10, period=1)
def rate_limited_end_bounty(web3, contract_to_write, address, private_key, bounty_id, buffer):
    """
    Ends an active bounty with rate limiting.

    Args:
        web3 (object): The Web3 instance.
        contract_to_write (object): The contract instance for writing.
        address (str): The sender's address.
        private_key (str): The sender's private key.
        bounty_id (str): The ID of the bounty to end.
        buffer (list): Buffer to store output messages.

    Returns:
        success (int): 1 if the bounty was ended successfully, 0 if there was an error.

    Example:
    >>> success = rate_limited_end_bounty(web3_instance, contract_instance, '0xSenderAddress', '0xPrivateKey', '12345', [])
    >>> print(success)
    1
    """
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
        
        if status_message == "failed":
            raise BountyFailedError(f"Bounty failed: {txn_receipt.transactionHash.hex()}")
        
        buffer.append(f'      -> {pn.C_GREEN}endBounty {status_message}{pn.C_END}: {txn_receipt.transactionHash.hex()}')
        return 1
    except BountyFailedError as e:
        buffer.append(f"      -> {pn.C_RED}**Error endBounty{pn.C_END}: {e}")
        return 0
    except Exception as e:
        error_type = type(e).__name__
        buffer.append(f"      -> {pn.C_RED}**Error endBounty{pn.C_END}: {e} - {error_type}")
        return 0


def get_bounties_to_execute(buffer, entity_ids):
    """
    Determine which bounties to execute based on a list of entity IDs.

    Args:
        default_group_id (int): The default group ID to use if a specific bounty is not found.
        default_bounty_name (str): The default bounty name to use if a specific bounty is not found.
        buffer (list): A list for storing informational messages.
        entity_ids (list): A list of entity IDs to assign to bounties.

    Returns:
        dict: A dictionary where keys are group IDs and values are lists of pirates to execute for each bounty.
        list: A list of entity Ids (pirates) that have no specific bounty and should be tried on fallback bounties
    """
    bounties_to_execute = {}  # Initialize a dictionary of bounties and pirates to execute
    fallback_bounty_entities = [] # Initialize a dictionary of pirates that are going to be tried to send on default bounties

    for entity_id in entity_ids:
        pirate_contract_addr, pirate_token_id = entity_id.split('-')
        pirate_token_id = int(pirate_token_id)

        #set the appropriate generation for the to make sure we look the proper pirate up
        generation = 1 if pirate_contract_addr != pn._contract_PirateNFT_addr else 0
        bounty_name = get_bounty_name_for_token_id(pirate_token_id, generation)
        bounty_group_id = get_group_id_by_bounty_name(bounty_name)
        pirate_entity = pn.pirate_token_id_to_entity(pirate_token_id, address=pirate_contract_addr)

        if bounty_group_id is not None and bounty_name is not None:
            if bounty_group_id not in bounties_to_execute:
                bounties_to_execute[bounty_group_id] = []

            bounty_limit = get_bounty_limit_by_group_id(bounty_group_id)
            if len(bounties_to_execute[bounty_group_id]) < bounty_limit:
                bounties_to_execute[bounty_group_id].append(pirate_entity)

        # if we don't have a match on the group_id or bounty_name we add the pirate to default_bounty_pirates
        else:
            fallback_bounty_entities.append(pirate_entity)

    return bounties_to_execute, fallback_bounty_entities



def process_address(args, web3, bounty_contract, bounty_data, row, is_multi_threaded):

    global _pending_bounties
    global _successfully_started_bounties

    start_time = time.time()

    num_ended_bounties = 0
    num_started_bounties = 0

    buffer = []

    wallet = row['identifier']
    address = row['address']
    private_key = row['key']

    if is_multi_threaded: print(f"{pn.C_YELLOWLIGHT}starting thread for wallet {wallet}{pn.C_END}")

    buffer.append(f"{pn.C_GREEN}---------------------------------------------------------------------------")
    buffer.append(f"--------------{pn.C_END} {wallet} - {address}")
    buffer.append(f"{pn.C_GREEN}---------------------------------------------------------------------------{pn.C_END}")

    # read the activeBounties for the address
    result, execution_time = rate_limited_active_bounty_ids(bounty_contract, address)
    
    #buffer.append(f"\n   Active Bounty IDs: {result}")
    #buffer.append(f"   fetched in {execution_time:.2f} seconds\n")

    # handle ending of bounties if we have the end flag set
    if args.end:
        for active_bounty_id in result:
            #buffer.append(f"   {pn.entity_to_token(active_bounty_id)}")
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

    # Assuming pirate_ids is a list of strings like ["123-456", "789-1011"]
    friendly_pirate_ids = [pirate_id.split('-')[1] for pirate_id in pirate_ids]

    # Now friendly_pirate_ids will contain the parts after the dash, e.g., ["456", "1011"]
    buffer.append(f"\n   Wallet {wallet} has the following pirates: {', '.join(friendly_pirate_ids)}")

    # do bounties to execute
    bounties_to_execute, fallback_bounty_pirates = get_bounties_to_execute(buffer, pirate_ids)

    # Now loop over bounties to execute and execute them
    for group_id, entity_ids in bounties_to_execute.items():   

        bounty_name, bounty_id = get_bounty_name_and_id(bounty_data, group_id, entity_ids)

        # start bounty if we find a valid bounty
        if bounty_id != 0:

            # check first if we have a pending bounty, because we will not try to send pirates on a bounty that's pending
            has_pending_bounty = rate_limited_has_pending_bounty(bounty_contract, address, group_id)    
            
            if has_pending_bounty:
                buffer.append(f"   {pn.C_YELLOW}'{bounty_name}' is still pending{pn.C_END}")
                insert_address_into_dictionary(_pending_bounties,bounty_name,address) 
            else:
                num_started_bounties += rate_limited_start_bounty(web3, bounty_contract, address, private_key, bounty_name, bounty_id, entity_ids, buffer)
                 # Delay to allow the network to update the nonce
                time.sleep(SLOW_FACTOR) 

           
            

    # Loop over fallback_bounty_pirates (list of entity_ids)
    _fallback_bounties_copy = list(_fallback_bounties)

    if len(_fallback_bounties) > 0:
            
        for entity_id in fallback_bounty_pirates:

            for fallback_bounty in _fallback_bounties_copy:

                bounty_result = 0
                group_id, bounty_name = fallback_bounty
                entity_ids = []
                entity_ids.append(entity_id)
                bounty_name, bounty_id = get_bounty_name_and_id(bounty_data, group_id, entity_ids)

                # check first if we have a pending bounty, because we will not try to send pirates on a bounty that's pending
                has_pending_bounty = rate_limited_has_pending_bounty(bounty_contract, address, group_id)      
                
                if has_pending_bounty:
                    _fallback_bounties_copy.remove(fallback_bounty)
                    buffer.append(f"   {pn.C_YELLOW}'{bounty_name}' is still pending{pn.C_END}")
                    insert_address_into_dictionary(_pending_bounties,bounty_name,address) 
                else:
                    bounty_result = rate_limited_start_bounty(web3, bounty_contract, address, private_key, bounty_name, bounty_id, entity_ids, buffer)
                    # Delay to allow the network to update the nonce
                    time.sleep(SLOW_FACTOR) 
                
                # If the fallback bounty was a success then increment the number of started bounties and break the fallback loop for this enity
                if bounty_result == 1: 
                    num_started_bounties += 1
                    break


    end_time = time.time()
    execution_time = end_time - start_time
    buffer.append(f"\n   {pn.C_CYAN}Execution time: {execution_time:.2f} seconds{pn.C_END}")
    buffer.append(f"{pn.C_GREEN}---------------------------------------------------------------------------{pn.C_END}")    
    print("\n".join(buffer))
    return buffer, num_ended_bounties, num_started_bounties


def parse_arguments():
    parser = argparse.ArgumentParser(description="This is a script to automate bounties")

    parser.add_argument("--skip_end", dest="end", action='store_false', default=True,
                        help="Flag to skip the endBounties")

    parser.add_argument("--skip_start", dest="start", action="store_false", default=True,
                        help="Flag to skip startBounty")
    
    parser.add_argument("--max_threads", type=int, default=MAX_THREADS, help="Maximum number of threads (default: 2)")

    parser.add_argument("--delay_start", type=int, default=0, help="Delay in minutes before executing logic of the code (default: 0)")    
    
    parser.add_argument("--delay_loop", type=int, default=0, help="Delay in minutes before executing the code again code (default: 0)")

    parser.add_argument("--loop_limit", type=int, help="Number of times to loop")

    parser.add_argument("--loop_buffer", type=int, default=150, help="Number of seconds for the loop buffer (default: 150)")

    parser.add_argument("--fallback_group_ids", type=str, default=None, help="Specify the fallback bounty groups id (default: None)") 

    parser.add_argument("--wallets", type=str, default=None, help="Specify the wallet range you'd like (e.g., 1-10,15,88-92) (default: None)") 

    args = parser.parse_args()
    
    return args


def main():

    global _pending_bounties
    global _successfully_started_bounties    
    
    # Pull arguments out for start, end, and delay
    args = parse_arguments()
    print("endBounty:", args.end)
    print("startBounty:", args.start)
    print("max_threads:", args.max_threads)
    print("delay_start:", args.delay_start)
    print("delay_loop:", args.delay_loop)
    print("fallback_group_ids:", args.fallback_group_ids)
    print("loop limit: ", args.loop_limit)
    print("loop_buffer:", args.loop_buffer)
    print("wallets:", args.wallets)

    # Set the times left to loop to the loop limit, if the arg is specified
    # This just helps create a limit on how many times we can loop
    if args.loop_limit: times_left_to_loop = args.loop_limit

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

    # Call the function with the user's input
    df_addressses = pn.get_full_wallet_data(walletlist)

    if args.start:

        if args.fallback_group_ids:

            fallback_group_ids = args.fallback_group_ids.split(',')
            for args_group_id in fallback_group_ids:
                fb_group_id = args_group_id.strip()
                fb_bounty_name = get_bounty_name_by_group_id(group_id)

                if fb_bounty_name is not None:
                    _fallback_bounties.append((fb_group_id, fb_bounty_name))

        else:
            fallback_count = 1
            # Keep iterating creating a list of fallback bounties until the user select none
            while True:
                fb_group_id, fb_bounty_name = input_choose_bounty(f"Please choose fallback bounty #{fallback_count}")
                if fb_group_id == "0":
                    break
                _fallback_bounties.append((fb_group_id, fb_bounty_name))
                fallback_count += 1

            print("Fallback Bounties:")
            for i, (group_id, bounty_name) in enumerate(_fallback_bounties, start=1):
                print(f"{pn.C_CYAN}Fallback Bounty #{i}:{pn.C_END}")
                print(f"Group ID: {group_id}")
                print(f"Bounty Name: {bounty_name}\n")

    # put in an initial starting delay
    if args.delay_start:
        pn.handle_delay(args.delay_start)

    #pre initialize for thread safety
    _pirate_bounty_mappings.get_mappings_df()

    while True:

        start_time = time.time()

        # Initialize web3 with the PN
        web3 = pn.Web3Singleton.get_web3_Nova()
        bounty_contract = pn.Web3Singleton.get_BountySystem()

        ended_bounties = 0
        started_bounties = 0

        # Load the JSON data from the file
        bounty_data = pn.get_data(bounty_query)

        # reload the pirate bounty mappings, because this could change between loop iterations and we want to reflect changes
        _pirate_bounty_mappings.reload_data()

        # CODE if we are going to run bounties multithreaded 
        if args.max_threads > 1 :

            print("Initiating Multithreading")

            with ThreadPoolExecutor(max_workers=args.max_threads) as executor:
                # Submit jobs to the executor
                futures = [executor.submit(process_address, args, web3, bounty_contract, bounty_data, row, True) 
                    for index, row in df_addressses.iterrows()]

                # Collect results as they come in
                for future in futures:
                    buffer, num_ended_bounties, num_started_bounties = future.result()
                    ended_bounties += num_ended_bounties
                    started_bounties += num_started_bounties

        # if we are going to go in order sequentially
        else:

            for index, row in df_addressses.iterrows():
                buffer, num_ended_bounties, num_started_bounties = process_address(args, web3, bounty_contract, bounty_data, row, False)
                ended_bounties += num_ended_bounties
                started_bounties += num_started_bounties

        end_time = time.time()
        execution_time = end_time - start_time    
        number_of_wallets = len(df_addressses)
        average_execution_time = execution_time / number_of_wallets 

        print(f"\nclaimed {ended_bounties} bounties and started {started_bounties} bounties in {execution_time:.2f} seconds (avg of {average_execution_time:.2f} s for {number_of_wallets} wallet(s))")        
        
        # Now we try to print out the pending bounties and the started bounty summary
        print(f"\n{pn.C_YELLOW}Pending Bounties:{pn.C_END}")
        if not _pending_bounties:
            print("   None")
        else:
            for key, value in _pending_bounties.items():
                print(f"   {key}: {len(value)}")

        print(f"\n{pn.C_GREEN}Successfully Started Bounties:{pn.C_END}")
        if not _successfully_started_bounties:
            print("   None")
        else:
            for key, value in _successfully_started_bounties.items():
                print(f"   {key}: {len(value)}")
        print("")

        # Clear these out once we print out the summary
        _pending_bounties = {}
        _successfully_started_bounties = {}            

        # end the loop if we don't have looping speified
        if args.delay_loop == 0:
            break
        else:

            # Calculate the seconds_to_shave_off: use the actual execution time minus a 120 second buffer to give some breathing room
            # Example if the exeution time takes 4 minute, we will take (360-120) = 240 seconds and shave it off the delay_loop 
            # The purpose of this is to try to make functions land more precisely closer to when they wrap up 
            seconds_to_shave_off = math.floor(execution_time - args.loop_buffer)
            print(f"We are trying to otimize by shaving off {seconds_to_shave_off} seconds")

            # Check if time_adjustment is negative and set it to 0 if it is
            if seconds_to_shave_off < 0:
                seconds_to_shave_off = 0  

            # continue looping with necessary delay
            delay_in_seconds = (args.delay_loop * 60) - seconds_to_shave_off 
            pn.handle_delay(delay_in_seconds, time_period="second")

        if args.loop_limit:
            times_left_to_loop -= 1
            print(f"We have {times_left_to_loop} times left to loop")
            if times_left_to_loop < 1: break


if __name__ == "__main__":
    main()