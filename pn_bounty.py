import time
import pandas as pd
import traceback
from typing import Union
import pn_helper as pn
from ratelimit import limits, sleep_and_retry

MAX_PIRATE_ON_BOUNTY = 20

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

class BountyGroupMappings:
    """
    Singleton class to manage mappings of bounty names to associated group IDs.

    This class implements the Singleton design pattern to ensure that only one instance
    of the mappings is created and used throughout the application's lifecycle. It provides
    methods to initialize and retrieve the bounty name-to-group ID mappings.

    Usage:
    - To initialize the mappings, call the `initialize` method.
    - To get the mappings DataFrame, call the `get_mappings_df` method.

    Example:
    >>> _bounty_group_mappings = BountyGroupMappings()
    >>> mappings = _bounty_group_mappings.get_mappings_df()

    NOTE: We auto initialize this below this class definition
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BountyGroupMappings, cls).__new__(cls)
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
            self.df = pd.read_csv("bounty_group_mappings.csv")

    def get_mappings_df(self):
        """
        Get the DataFrame containing bounty name-to-group ID mappings.

        Returns:
        - pd.DataFrame: A DataFrame containing the mappings of bounty names to group IDs.
        """
        self.initialize()
        return self.df

# Automatically create an instance of BountyMappings and initialize it
_bounty_group_mappings = BountyGroupMappings()

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
        bounty_mappings_df = _bounty_group_mappings.get_mappings_df()

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
        bounty_mappings_df = _bounty_group_mappings.get_mappings_df()

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

        bounty_mappings_df = _bounty_group_mappings.get_mappings_df()

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

    pirate_bounty_df = pn._pirate_command_mappings.get_mappings_df()

    matching_row = pirate_bounty_df[(pirate_bounty_df['tokenId'] == token_id) & (pirate_bounty_df['Gen'] == generation)]
    
    if not matching_row.empty:
        bounty = matching_row.iloc[0]['Bounty']
        if isinstance(bounty, str):
            return bounty
        
    return None # Token ID and generation not found in the DataFrame or bounty is not a string


def get_bounty_name_and_id(data, group_id, entity_ids) -> Union[str, int]:
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
def rate_limited_start_bounty(web3, contract_to_write, address, private_key, bounty_name, bounty_id, pirates, buffer, verbose=False):
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

    if len(pirates) > 1:
        buffer.append(f"   Sending {pn.C_CYAN}{len(pirates)} pirate(s){pn.C_END} on {pn.C_CYAN}'{bounty_name}'{pn.C_END}")
        buffer.append(f"      -> entities: {pirates}")
        buffer.append(f"      -> bounty id: {bounty_id}")

        # Print out the pirates' addresses and token IDs
        for pirate in pirates:
            address_str, token_id = pn.entity_to_token(pirate)
            buffer.append(f"      -> {address_str}, Token ID: {pn.C_CYAN}{token_id}{pn.C_END}")
    else:
        for pirate in pirates:
            address_str, token_id = pn.entity_to_token(pirate)
            break

        if verbose:
            buffer.append(f"   Sending Pirate # {pn.C_CYAN}{token_id}{pn.C_END} {pirates} on {pn.C_CYAN}'{bounty_name}'{pn.C_END} - {bounty_id}")
        else:
            buffer.append(f"   Sending Pirate # {pn.C_CYAN}{token_id}{pn.C_END} on {pn.C_CYAN}'{bounty_name}'{pn.C_END}")

    status_msg, txn_receipt = start_bounty(web3, contract_to_write, address, private_key, bounty_id, pirates)

    if(txn_receipt is not None and status_msg == pn.WEB3_STATUS_SUCCESS):
        buffer.append(f'      -> {pn.C_GREEN}startBounty {status_msg}{pn.C_END}: {txn_receipt.transactionHash.hex()}\n')
        return 1
    
    else:
        buffer.append(f"      -> {pn.C_RED}**Error startBounty{pn.C_END}: {status_msg}\n")
        return 0


def start_bounty(web3, contract_to_write, address, private_key, bounty_id, pirates):

    try:
        txn_dict = {
            'from': address,
            'to': contract_to_write.address,
            'value': 0,
            'nonce': web3.eth.get_transaction_count(address),
            'gasPrice': web3.eth.gas_price,
            'data': contract_to_write.encodeABI(fn_name='startBounty', args=[bounty_id, pirates])
        }

        print(f"bounty_id: {bounty_id} pirates: {pirates}")

        txn_receipt = pn.send_web3_transaction(web3, private_key, txn_dict, max_transaction_cost_usd=0.08, retries=4, retry_delay=15)

        if txn_receipt is not None:
            status_message = pn.get_status_message(txn_receipt)
            return status_message, txn_receipt
        else:
            # Handle the case where txn_receipt is None
            return None, "Transaction failed or was not sent"
    
    except ValueError as ve:
        # Handle ValueError specifically without printing traceback
        return f"{ve}", None

    except Exception as e:
        
        # Print the error type and traceback
        print(f"Error type: {type(e).__name__}")
        traceback.print_exc()  # This prints the traceback
        print(f"Error with transaction: {e}")

    return "failed due to error", None    

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
        txn_receipt = pn.send_web3_transaction(web3, private_key, txn_dict, retries=4, max_transaction_cost_usd=0.05, retry_delay=15)
        status_message = pn.get_status_message(txn_receipt)

        if status_message == "failed":
            raise Exception(f"Bounty failed: {txn_receipt.transactionHash.hex()}")

        buffer.append(f'      -> {pn.C_GREEN}endBounty {status_message}{pn.C_END}: {txn_receipt.transactionHash.hex()}')
        return 1
    except Exception as e:
        error_message = str(e)
        if "0xaf68984f" in error_message:
            # Handle the specific contract error
            buffer.append(f"      -> {pn.C_RED}**Contract Error{pn.C_END}: {error_message}")
        else:
            # Handle other exceptions, including gas estimation failures
            error_type = type(e).__name__
            buffer.append(f"      -> {pn.C_RED}**Error endBounty - {error_type}{pn.C_END}: {error_message}")
        return 0


def get_bounties_to_execute(entity_ids):
    """
    Determine which bounties to execute based on a list of entity IDs.

    Args:
        entity_ids (list): A list of entity IDs to assign to bounties.

    Returns:
        dict: A dictionary where keys are group IDs and values are lists of pirates to execute for each bounty.
        list: A list of entity Ids (pirates) that have no specific bounty and are considered unallocated
    """
    bounties_to_execute = {}  # Initialize a dictionary of bounties and pirates to execute
    unallocated_entities = [] # Initialize a dictionary of pirates that don't have bounty commands

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

        # if we don't have a match on the group_id or bounty_name we add the pirate to unallocated pirate entities
        else:
            unallocated_entities.append(pirate_entity)

    return bounties_to_execute, unallocated_entities