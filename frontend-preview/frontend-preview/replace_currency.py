import re
import sys

def format_indian_currency(num_str):
    """Formats a number string into Indian numbering system (e.g., 1,50,000)."""
    # Remove commas first
    clean_num = num_str.replace(',', '')
    # Split decimal if any
    parts = clean_num.split('.')
    integer_part = parts[0]
    decimal_part = f".{parts[1]}" if len(parts) > 1 else ""
    
    if len(integer_part) <= 3:
        return integer_part + decimal_part
        
    last_three = integer_part[-3:]
    other_numbers = integer_part[:-3]
    
    # Add commas every two digits from the right for the rest of the numbers
    formatted_others = re.sub(r'(\d)(?=(\d{2})+$)', r'\1,', other_numbers)
    
    return f"{formatted_others},{last_three}{decimal_part}"

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all $ amounts and replace with ₹ and Indian formatting
    def replace_match(match):
        num_str = match.group(1)
        return "₹" + format_indian_currency(num_str)

    # Match $ followed by numbers, commas, and optional decimals
    new_content = re.sub(r'\$([\d,]+(?:\.\d{2})?)', replace_match, content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

if __name__ == "__main__":
    process_file(sys.argv[1])
