from pathlib import Path

def append_data(csv_path, col_names, row):
    
    col_names = [str(x) for x in col_names]
    row = [str(x) for x in row]

    col_names_str = ",".join(col_names)
    row_str = ",".join(row)
    
    path_obj = Path(csv_path)

    if not path_obj.is_file():
        with open(csv_path, 'w+') as csv_file:
            csv_file.write(col_names_str)

    with open(csv_path, 'a') as csv_file:
        csv_file.write("\n" + row_str)

# The nature of the web socket used means that variables regarding the current trading session
# cannot easily be passed around, so instead they are encapsulated in this class.
class CurrentTradingSession():
    def __init__(self):
        self.in_long_position = False
        self.last_buy_price = 0
        self.last_position_stop_triggered = -1000
        self.closes_dict = {}
        self.cur_closes_dict_len = len(self.closes_dict)

    def trading_results(self):
        return (self.in_long_position,
                self.last_buy_price,
                self.last_position_stop_triggered,
                self.closes_dict,
                self.cur_closes_dict_len)