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