from pathlib import Path
from typing import List, Any, Tuple, Dict

def append_data(csv_path: str, col_names: List[Any], row: List[Any]) -> None:
    """Function used to add data to a CSV. Either appends to a CSV if the file
    already exists, or creates a new CSV if not.

    Parameters
    ----------
    csv_path : str
        The path to the CSV which is to be either created or appended to.
    col_names : List[Any]
        The name of the fields in the CSV, used if the CSV is to be created.
    row : List[Any]
        The entries entered into the fields in the CSV.

    Returns
    -------
    None
    """
    col_names = [str(x) for x in col_names]
    col_names_str = ",".join(col_names)
    row = [str(x) for x in row]
    row_str = ",".join(row)
    
    path_obj = Path(csv_path)
    if not path_obj.is_file():
        with open(csv_path, 'w+') as csv_file:
            csv_file.write(col_names_str)

    with open(csv_path, 'a') as csv_file:
        csv_file.write("\n" + row_str)

class CurrentTradingSession():
    """The nature of the web socket used means that variables regarding the
    current trading session cannot easily be passed around, so instead they are
    encapsulated in this class.
    """
    def __init__(self) -> None:
        self.in_long_position = False
        self.max_price_since_buy = 0
        self.last_position_stop_triggered = -1000
        self.closes_dict = {}
        self.cur_closes_dict_len = len(self.closes_dict)

    def trading_results(self) -> Tuple[bool, float, float, Dict[str, float], int]:
        """Returns all current attributes of the object.
        """
        return (self.in_long_position,
                self.max_price_since_buy,
                self.last_position_stop_triggered,
                self.closes_dict,
                self.cur_closes_dict_len)