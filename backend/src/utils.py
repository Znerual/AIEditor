# src/utils.py
from delta import Delta
import logging

logger = logging.getLogger('eddy_logger')

def string_to_delta(content_string: str) -> Delta:
    """Converts a plain text string to a Quill Delta."""
    return Delta([{'insert': content_string}])

def delta_to_string(delta: Delta) -> str:
    """
    Converts a Quill Delta to a plain text string, handling insert, delete, and retain 
    correctly using the compose() method.
    """

    if isinstance(delta, list):
        delta = Delta(delta)

    composed_delta = Delta()  # Start with an empty Delta
    for op in delta.ops:
        composed_delta = Delta([op]).compose(composed_delta)  

    try:
        return composed_delta.document()
    except Exception as e:
        logger.warning(f"Error converting delta to string: {e}")
        text = ""
        for op in delta.ops:
            #print(op)
            if 'insert' in op:
                text += op['insert']


        return text
            
        

# Add the utility functions to the Delta class
Delta.to_plain_text = delta_to_string