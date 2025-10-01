from datetime import datetime, time
import pytz
import logging
from common.utilis import day_start, day_end

# Specify the Europe/London timezone
my_tz = pytz.timezone('Europe/London')

def is_daytime():
    """
    Returns True if the current time in Europe/London timezone is between 8:00 AM and 4:00 PM, False otherwise.
    """
    # Get the current time in the Europe/London timezone
    now = datetime.now(my_tz).time()

    # If the current time is between day_start and day_end, return True
    if day_start <= now <= day_end:
        return True
    else:
        return False

# Example usage:
if __name__ == "__main__":
    if is_daytime():
        logging.info("It's daytime: Public IP should be assigned to VM1.")
    else:
        logging("It's nighttime: Public IP should be assigned to VM2.")