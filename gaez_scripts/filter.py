
from gaez_scripts.metadata.codes import KEEP_CODES, DROP_MODEL_PARAMETERS
import tempfile
import shutil


def filter_tiff():
    input_file = "all_files.txt"
    output_file = "tif_files.txt"

    with open(input_file, "r", encoding="utf-8") as infile, \
        open(output_file, "w", encoding="utf-8") as outfile:
        
        for line in infile:
            line = line.strip()
            if line.endswith(".tif"):
                outfile.write(line + "\n")

    print("Done filtering .tif files.")

def get_urls_dimensions():
    input_file = "tif_files.txt"

    result = set()

    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split(".")
            # add all parts except the last (tif)
            for p in parts[:-1]:
                result.add(p)

    
def check_layers(input_path: str, layer_paths: list[str]) -> None:
    with open(input_path) as f:
        total = sum(1 for _ in f)

    layer_counts = []
    for path in layer_paths:
        with open(path) as f:
            count = sum(1 for _ in f)
        layer_counts.append((path, count))
        print(f"{path}: {count} lines")

    layer_total = sum(count for _, count in layer_counts)
    print(f"\nInput total : {total}")
    print(f"Layers sum  : {layer_total}")

    if total == layer_total:
        print("OK — all lines accounted for")
    else:
        print(f"MISMATCH — {abs(total - layer_total)} lines unaccounted for")

""" ======================================"""

def filter_lines_drop(input_path: str, output_path: str, words: list[str]) -> None:
    with open(input_path, "r") as infile, open(output_path, "w") as outfile:
        for line in infile:
            if not any(word in line for word in words):
                outfile.write(line)
                
def filter_lines_keep(input_path: str, output_path: str, words: list[str]) -> None:
    with open(input_path, "r") as infile, open(output_path, "w") as outfile:
        for line in infile:
            if any(word in line for word in words):
                outfile.write(line)

def filter_by_folder(input_path: str, output_path: str, folders: list[str]) -> None:
    with open(input_path, "r") as infile, open(output_path, "w") as outfile:
        for line in infile:
            if any(folder in line for folder in folders):
                outfile.write(line)


def filter_lines_inplace(path: str, words: list[str], keep: bool = True) -> None:
    with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
        with open(path, "r") as infile:
            for line in infile:
                match = any(word in line for word in words)
                if (keep and match) or (not keep and not match):
                    tmp.write(line)
    shutil.move(tmp.name, path)



INPUT_PATH = "gaez_data/links/tif_files.txt"
OUTPUT_PATH = "gaez_data/links/filtered_tiff_files.txt"


filter_lines_drop(INPUT_PATH, OUTPUT_PATH, DROP_MODEL_PARAMETERS)
filter_lines_inplace(OUTPUT_PATH, KEEP_CODES)
filter_lines_inplace(OUTPUT_PATH, [str(y) for y in range(1980, 2023)], False)