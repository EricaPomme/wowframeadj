from pathlib import Path
import argparse
import sys

VALID_KEYS = {"Frame", "FrameLevel", "Anchor", "X", "Y", "W", "H"}
VALID_KEYS_LOWER = {key.lower() for key in VALID_KEYS}

def auto_cast(value: str):
    """
    Automatically convert a string value to the most appropriate type.
    
    Attempts to convert the input string to an integer first, then to a float,
    and finally returns the stripped string if neither conversion succeeds.
    
    Args:
        value (str): The string value to convert
        
    Returns:
        int | float | str: The converted value as int, float, or stripped string
    """
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value.strip()

def parse_kv_line(line: str):
    """
    Parse a key-value line separated by a colon.
    
    Extracts key and value from a line in the format "key: value", automatically
    converting the value to the most appropriate type.
    
    Args:
        line (str): The line to parse in "key: value" format
        
    Returns:
        tuple[str | None, any]: A tuple containing the stripped key and auto-cast value,
                               or (None, None) if no colon is found in the line
    """
    if ':' not in line:
        return None, None
    key, value = line.split(":", 1)
    return key.strip(), auto_cast(value.strip())

def get_frames(path: Path):
    """
    Parse a layout-local.txt file and extract frame data.
    
    Reads the file and parses it into structured frame data. Each frame is expected
    to be a block of 7 lines containing key-value pairs. The first line of the file
    is treated as a version header.
    
    Args:
        path (Path): Path to the layout-local.txt file to parse
        
    Returns:
        tuple[list[dict], str]: A tuple containing:
            - list of frame dictionaries with parsed key-value data
            - version header string from the first line of the file
    """
    with open(path, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        return [], ""

    version_header = lines[0]
    frames = []
    index = 1  # Skip version header

    while index + 6 < len(lines):  # Expecting blocks of 7 lines
        frame_data = {}
        for offset in range(7):
            key, value = parse_kv_line(lines[index + offset])
            if key:
                frame_data[key] = value
        frames.append(frame_data)
        index += 7

    return frames, version_header

def serialize_frames(frames, version_header):
    """
    Convert frame data back to the layout-local.txt file format.
    
    Takes structured frame data and serializes it back to the original file format
    with the version header and frame blocks. Frame names are output first, followed
    by other keys in sorted order.
    
    Args:
        frames (list[dict]): List of frame dictionaries to serialize
        version_header (str): Version header to include at the top of the output
        
    Returns:
        str: Serialized file content as a single string with newline separators
    """
    output = [version_header]
    for frame in frames:
        keys = sorted(k for k in frame.keys() if k != "Frame")
        output.append(f"Frame: {frame.get('Frame', '')}")
        for key in keys:
            value = frame[key]
            output.append(f"{key}: {value}")
    return "\n".join(output)

def parse_overrides(pairs: list[str]) -> dict:
    """
    Parse command-line override arguments into a dictionary.
    
    Processes a list of "key=value" pairs from command-line arguments and validates
    that keys are in the VALID_KEYS set (case-insensitive). Values are automatically 
    cast to appropriate types. Keys are normalized to their proper case from VALID_KEYS.
    
    Args:
        pairs (list[str]): List of "key=value" strings from command-line arguments
        
    Returns:
        dict: Dictionary mapping valid keys (in proper case) to their auto-cast values
        
    Raises:
        SystemExit: If any pair is malformed or contains an invalid key
    """
    overrides = {}
    for pair in pairs:
        if '=' not in pair:
            print(f"Invalid --set argument: {pair}")
            sys.exit(1)
        key, value = pair.split("=", 1)
        key = key.strip()
        if key.lower() not in VALID_KEYS_LOWER:
            print(f"Invalid key in --set: {key}")
            sys.exit(1)
        
        # Find the proper case version of the key
        proper_key = next(vk for vk in VALID_KEYS if vk.lower() == key.lower())
        overrides[proper_key] = auto_cast(value.strip())
    return overrides

def print_frame_summary(frames):
    """
    Print a formatted table summary of all frames and their properties.
    
    Creates and displays a table with frame names and all their properties in columns.
    The table is automatically sized to fit the content and uses markdown-style formatting
    with pipes and dashes.
    
    Args:
        frames (list[dict]): List of frame dictionaries to display
    """
    # Get all keys across all frames (excluding 'Frame'), then sort
    keys = sorted({key for frame in frames for key in frame.keys() if key != "Frame"})
    header = ["Frame"] + keys

    # Build rows
    rows = []
    for frame in frames:
        row = [str(frame.get("Frame", ""))] + [str(frame.get(k, "")) for k in keys]
        rows.append(row)

    # Compute column widths
    col_widths = [max(len(row[i]) for row in [header] + rows) for i in range(len(header))]

    # Build output
    def format_row(row):
        return " | ".join(row[i].ljust(col_widths[i]) for i in range(len(row)))

    print(format_row(header))
    print("-|-".join("-" * w for w in col_widths))
    for row in rows:
        print(format_row(row))


def apply_overrides(frames, overrides):
    """
    Apply override values to a specific frame in the frames list.
    
    Finds the target frame by name and updates its properties with the provided
    override values. The frame name itself cannot be changed.
    
    Args:
        frames (list[dict]): List of frame dictionaries to modify in-place
        overrides (dict): Dictionary of key-value pairs to apply, must include "Frame" key
        
    Raises:
        SystemExit: If no Frame name is provided or if the target frame is not found
    """
    target_name = overrides.get("Frame")
    if not target_name:
        print("Error: --set requires at least Frame=<name>")
        sys.exit(1)

    for frame in frames:
        if frame.get("Frame") == target_name:
            for key, value in overrides.items():
                if key != "Frame":  # Don't change frame name itself
                    frame[key] = value
            return

    print(f"Error: Frame '{target_name}' not found in file.")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Parse and optionally update layout-local.txt.')
    parser.add_argument('path', type=str, help='Path to layout-local.txt file')
    parser.add_argument('--set', nargs='+', help='Update values for a specific frame. Requires Frame=<name> and optional key=value pairs.')
    args = parser.parse_args()

    file_path = Path(args.path)

    if not (file_path.is_file() and file_path.name == 'layout-local.txt'):
        print(f"Error: {args.path} is not a valid layout-local.txt file.")
        sys.exit(1)

    frames, version_header = get_frames(file_path)

    if args.set:
        overrides = parse_overrides(args.set)
        apply_overrides(frames, overrides)
        output = serialize_frames(frames, version_header)

        with open(file_path, 'w') as f:
            f.write(output + '\n')
    else:
        print_frame_summary(frames)

if __name__ == '__main__':
    main()
