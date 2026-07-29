"""
Coupon code generation utility.
Supports configurable length and character set combinations.
"""
import secrets
import string


CHAR_SETS = {
    'digits':       string.digits,
    'uppercase':    string.ascii_uppercase,
    'lowercase':    string.ascii_lowercase,
    'alphanumeric': string.ascii_uppercase + string.digits,
    'full':         string.ascii_uppercase + string.ascii_lowercase + string.digits,
}

# Characters that look similar — omit to reduce entry errors
AMBIGUOUS = set('0O1lI')


def generate_code(length=8, char_set='alphanumeric', exclude_ambiguous=True):
    """
    Generate a single coupon code.

    Args:
        length (int): Number of characters. Default 8.
        char_set (str): Key from CHAR_SETS. Default 'alphanumeric'.
        exclude_ambiguous (bool): Remove visually ambiguous chars. Default True.

    Returns:
        str: The generated code.
    """
    pool = CHAR_SETS.get(char_set, CHAR_SETS['alphanumeric'])
    if exclude_ambiguous:
        pool = ''.join(c for c in pool if c not in AMBIGUOUS)
    if not pool:
        raise ValueError('Character pool is empty after filtering.')
    return ''.join(secrets.choice(pool) for _ in range(length))


def generate_batch(quantity, length=8, char_set='alphanumeric',
                   exclude_ambiguous=True, existing_codes=None):
    """
    Generate a batch of unique coupon codes.

    Args:
        quantity (int): Number of codes to generate.
        length (int): Length of each code.
        char_set (str): Character set key.
        exclude_ambiguous (bool): Filter ambiguous chars.
        existing_codes (set|None): Already-used codes to avoid duplicates.

    Returns:
        list[str]: List of unique codes.

    Raises:
        ValueError: If it's impossible to generate enough unique codes.
    """
    pool = CHAR_SETS.get(char_set, CHAR_SETS['alphanumeric'])
    if exclude_ambiguous:
        pool = ''.join(c for c in pool if c not in AMBIGUOUS)

    max_possible = len(pool) ** length
    if quantity > max_possible * 0.8:
        raise ValueError(
            f'Cannot generate {quantity} unique codes with length={length} '
            f'and char_set={char_set}. Maximum is ~{int(max_possible * 0.8)}.'
        )

    seen = set(existing_codes or [])
    codes = []
    attempts = 0
    max_attempts = quantity * 10

    while len(codes) < quantity:
        attempts += 1
        if attempts > max_attempts:
            raise ValueError(
                f'Could not generate enough unique codes after {max_attempts} attempts.'
            )
        code = generate_code(length, char_set, exclude_ambiguous)
        if code not in seen:
            seen.add(code)
            codes.append(code)

    return codes
