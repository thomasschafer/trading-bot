from pathlib import Path

def append_data(csv_path, col_names, row_to_append):
    
    path_obj = Path(csv_path)

    if not path_obj.is_file():
        with open(csv_path, 'w+') as csv_file:
            csv_file.write(col_names)

    with open(csv_path, 'a') as csv_file:
        csv_file.write("\n" + row_to_append)