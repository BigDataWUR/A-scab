import numpy as np
import datetime
from typing import Optional, Union


def items_since_last_true(array):
    last_true_index = -1
    result = np.zeros_like(array, dtype=int)

    for i, value in enumerate(array):
        if value:
            last_true_index = i
        result[i] = i - last_true_index

    return result


def fill_gaps(arr, max_gap: int = 2):
    # Initialize an array to store lengths of false series
    false_series_lengths = np.zeros_like(arr, dtype=int)

    # Initialize a counter to keep track of the length of the current false series
    current_length = 0

    # Loop through the array to determine false series lengths
    for i in range(len(arr)):
        if arr[i] == False:
            # If the element is False, increment the current length
            current_length += 1
        else:
            # If the element is True, store the current length and reset the counter
            false_series_lengths[i - current_length:i] = current_length
            current_length = 0

    # If the last series ends with False values, store its length
    if current_length > 0:
        false_series_lengths[-current_length:] = current_length
    return false_series_lengths <= max_gap


def parse_date(input_date: Optional[Union[str, int]]) -> Optional[int]:
    """
    Parses input_date, which can be:
    - None
    - A day of the year as an integer (e.g., "69")
    - A date string in the format "%B %d" (e.g., "March 10")

    Returns:
    - None if input_date is None
    - An integer representing the day of the year.
    """
    if input_date is None:
        return None
    elif isinstance(input_date, int) or input_date.isdigit():
        return int(input_date)  # If input_date is a day of the year (e.g., "69")
    else:
        return (
            datetime.datetime.strptime(input_date, "%B %d").timetuple().tm_yday
        )  # If it's a date string (e.g., "March 10")
