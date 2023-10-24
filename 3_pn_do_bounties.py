import argparse
import math
import time
import functools
import traceback
import questionary
import pn_helper as pn
import pn_bounty as PNB
from concurrent.futures import ThreadPoolExecutor

MAX_THREADS = 2
SLOW_FACTOR = 0.5  
   
_pending_bounties = {}
_successfully_started_bounties = {}
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
    bounty_mappings_df = PNB._bounty_group_mappings.get_mappings_df()
    
    # Create a list of choices for questionary
    choices = [{"name": f"{index + 1}. {row['bounty_name']}", "value": (row['group_id'], row['bounty_name'])} for index, row in bounty_mappings_df.iterrows()]

    # Prompt the user to select a default bounty
    selected_group_id, selected_bounty_name = questionary.select(
        prompt,
        choices=choices
    ).ask()

    return selected_group_id, selected_bounty_name


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
    active_bounty_ids, execution_time = PNB.rate_limited_active_bounty_ids(bounty_contract, address)
    active_bounty_count = len(active_bounty_ids)
    
    #buffer.append(f"\n   Active Bounty IDs: {result}")
    #buffer.append(f"   fetched in {execution_time:.2f} seconds\n")

    # handle ending of bounties if we have the end flag set
    if args.end:
        for active_bounty_id in active_bounty_ids:
            end_bounty_result = PNB.rate_limited_end_bounty(web3, bounty_contract, address, private_key, active_bounty_id, buffer)
            active_bounty_count -= end_bounty_result
            num_ended_bounties += end_bounty_result     

    # if we don't have start bounties set then continue and skip all the remaining code below
    if not args.start:
        end_time = time.time()
        execution_time = end_time - start_time
        buffer.append(f"\n   {pn.C_CYAN}Execution time: {execution_time:.2f} seconds, ending @ {pn.formatted_time_str()}{pn.C_END}")
        buffer.append(f"{pn.C_GREEN}---------------------------------------------------------------------------{pn.C_END}")   
        print("\n".join(buffer))
        return buffer, num_ended_bounties, num_started_bounties

    # load up all the pirate IDs per address
    pirate_ids = pn.get_pirate_ids(address)

    # Assuming pirate_ids is a list of strings like ["123-456", "789-1011"]
    friendly_pirate_ids = [pirate_id.split('-')[1] for pirate_id in pirate_ids]

    # Now friendly_pirate_ids will contain the parts after the dash, e.g., ["456", "1011"]
    buffer.append(f"\n   Wallet {wallet} has the following pirates: {', '.join(friendly_pirate_ids)}\n")

    if active_bounty_count == len(pirate_ids) :
        buffer.append(f"   {pn.C_MAGENTA}All {active_bounty_count} pirate(s) are on active bounties. {pn.C_END}\n")
        end_time = time.time()
        execution_time = end_time - start_time
        buffer.append(f"\n   {pn.C_CYAN}Execution time: {execution_time:.2f} seconds, ending @ {pn.formatted_time_str()}{pn.C_END}")
        buffer.append(f"{pn.C_GREEN}---------------------------------------------------------------------------{pn.C_END}")   
        print("\n".join(buffer))

        pn.insert_address_into_dictionary(_pending_bounties,f"Wallets with {active_bounty_count} pirate(s) and Unknown active bounty",address)    

        return buffer, num_ended_bounties, num_started_bounties

    # do bounties to execute
    bounties_to_execute, fallback_bounty_pirates = PNB.get_bounties_to_execute(pirate_ids)

    # make a copy of the fall_back bounties to remove bounties out of it to prevent redundacy
    _fallback_bounties_copy = list(_fallback_bounties)  

    buffer.append(f"{pn.C_MAGENTA}   Excel Specified Bounties...{pn.C_END}\n")    
    if len(bounties_to_execute.items()) == 0:
        buffer.append("   None")

    # Now loop over bounties to execute and execute them
    for group_id, entity_ids in bounties_to_execute.items():   

        bounty_name, bounty_id = PNB.get_bounty_name_and_id(bounty_data, group_id, entity_ids)
        bounty_result = 0
        
        # start bounty if we find a valid bounty
        if bounty_id != 0:

            # check first if we have a pending bounty, because we will not try to send pirates on a bounty that's pending
            has_pending_bounty = PNB.rate_limited_has_pending_bounty(bounty_contract, address, group_id)    
            
            if has_pending_bounty:
                buffer.append(f"   {pn.C_YELLOW}{bounty_name} is still pending{pn.C_END}\n")
                pn.insert_address_into_dictionary(_pending_bounties,bounty_name,address) 
            else:
                bounty_result = PNB.rate_limited_start_bounty(web3, bounty_contract, address, private_key, bounty_name, bounty_id, entity_ids, buffer)

                # if the bounty was successfully executed
                if bounty_result > 0 :
                    # insert results into successfully started bounties
                    pn.insert_address_into_dictionary(_successfully_started_bounties, bounty_name, address)

                    # increment our number of started bounties
                    num_started_bounties += bounty_result

                    # since we started this bounty, check if it's in the fallback bounties and remove it if it is
                    if (group_id, bounty_name) in _fallback_bounties_copy:
                        _fallback_bounties_copy.remove((group_id, bounty_name))

                # Delay to allow the network to update the nonce
                time.sleep(SLOW_FACTOR) 

    buffer.append(f"\n{pn.C_MAGENTA}   Fallback Bounty Pirates...{pn.C_END}\n")

    # Loop over fallback_bounty_pirates (list of entity_ids)
    if len(_fallback_bounties) > 0 and len(fallback_bounty_pirates) > 0:

        for entity_id in fallback_bounty_pirates:

            # create a temporary list to store bounties we want to remove from the list for future pirates to fallback
            _fallback_bounties_to_remove = []
            
            # loop through fallback bounties to determine what to execute until you find one that works
            for fallback_bounty in _fallback_bounties_copy:

                bounty_result = 0
                group_id, bounty_name = fallback_bounty
                entity_ids = []
                entity_ids.append(entity_id)
                bounty_name, bounty_id = PNB.get_bounty_name_and_id(bounty_data, group_id, entity_ids)

                # check first if we have a pending bounty, because we will not try to send pirates on a bounty that's pending
                has_pending_bounty = PNB.rate_limited_has_pending_bounty(bounty_contract, address, group_id)      
                
                if has_pending_bounty:
                    _fallback_bounties_to_remove.append(fallback_bounty)

                    address_str, token_id = pn.entity_to_token(entity_id)

                    buffer.append(f"   Sending Pirate # {pn.C_CYAN}{token_id}{pn.C_END} on {pn.C_CYAN}'{bounty_name}'{pn.C_END}")                    
                    buffer.append(f"      -> {pn.C_YELLOW}'{bounty_name}' is still pending{pn.C_END}\n")

                    pn.insert_address_into_dictionary(_pending_bounties,bounty_name,address) 
                else:
                    bounty_result = PNB.rate_limited_start_bounty(web3, bounty_contract, address, private_key, bounty_name, bounty_id, entity_ids, buffer)
                    # Delay to allow the network to update the nonce
                    time.sleep(SLOW_FACTOR) 
                
                # If the fallback bounty was a success then increment the number of started bounties and break the fallback loop for this enity
                if bounty_result == 1:
                    _fallback_bounties_to_remove.append(fallback_bounty) 
                    pn.insert_address_into_dictionary(_successfully_started_bounties, bounty_name, address)
                    num_started_bounties += 1
                    break
            
            # remove any pending bounties from the fallback copy so that any future pirates won't need to try to start that bounty
            for fallback_bounty in _fallback_bounties_to_remove:
                _fallback_bounties_copy.remove(fallback_bounty)
    else:
        buffer.append("   None")

    end_time = time.time()
    execution_time = end_time - start_time
    buffer.append(f"\n   {pn.C_CYAN}Execution time: {execution_time:.2f} seconds, ending @ {pn.formatted_time_str()}{pn.C_END}")
    buffer.append(f"{pn.C_GREEN}---------------------------------------------------------------------------{pn.C_END}")    
    print("\n".join(buffer))
    return buffer, num_ended_bounties, num_started_bounties


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


@retry(max_retries=12, delay_seconds=300)
def body_logic(args, df_addressses):

    global _pending_bounties
    global _successfully_started_bounties    

    # Set the times left to loop to the loop limit, if the arg is specified
    # This just helps create a limit on how many times we can loop
    times_left_to_loop = 0
    if args.loop_limit: times_left_to_loop = args.loop_limit

    # put in an initial starting delay
    if args.delay_start:
        pn.handle_delay(args.delay_start)

    #pre initialize for thread safety
    PNB._pirate_bounty_mappings.get_mappings_df()

    while True:
        start_time = time.time()

        # Initialize web3 with the PN
        web3 = pn.Web3Singleton.get_web3_Nova()
        bounty_contract = pn.Web3Singleton.get_BountySystem()

        ended_bounties = 0
        started_bounties = 0

        # Load the JSON data from the file
        bounty_data = pn.get_data(PNB.bounty_query)

        # reload the pirate bounty mappings, because this could change between loop iterations and we want to reflect changes
        PNB._pirate_bounty_mappings.reload_data()

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

        # Clear these out once we print out the summary--
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

    global _fallback_bounties
    
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
    print("Time:", pn.formatted_time_str())

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
                fb_bounty_name = PNB.get_bounty_name_by_group_id(group_id)

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

    try:
        body_logic(args, df_addressses)
    except Exception as e:
        print(f"Final exception: {e}")        


if __name__ == "__main__":
    main()